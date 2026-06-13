from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError:  # pragma: no cover - depends on deployment env
    FastAPI = None  # type: ignore
    HTTPException = None  # type: ignore
    CORSMiddleware = None  # type: ignore

try:
    from pydantic import BaseModel, Field
    from scientra.models import LiteratureQueryRequest, LiteratureQueryResponse, QueryFilters, QueryType
    from scientra.query import literature_query, LiteratureQueryService
except ModuleNotFoundError:
    from pydantic import BaseModel, Field
    from scientra.models import LiteratureQueryRequest, LiteratureQueryResponse, QueryFilters, QueryType
    from scientra.query import literature_query, LiteratureQueryService


# ── Helpers ──

def _resolve_root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    env_root = os.environ.get("SCIENTRA_ROOT")
    if env_root:
        return Path(env_root)
    # Walk up from this file to find Config/workflow_config.yaml
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[1]


def _lancedb_info(root: Path) -> tuple[str, dict[str, int]]:
    """Return (status, table_counts) for LanceDB."""
    try:
        import lancedb
        db_dir = root / "04_VectorDB" / "lancedb"
        if not db_dir.exists():
            db_dir = root / "06_Index/vector/lancedb/lancedb"
        if not db_dir.exists():
            archives = sorted((root / "10_System/legacy_archive").glob("storage_v1_legacy_*/04_VectorDB/lancedb"))
            db_dir = archives[-1] if archives else db_dir
        if not db_dir.exists() or not any(db_dir.iterdir()):
            return "no database directory", {}
        db = lancedb.connect(str(db_dir))
        tables = db.table_names()
        counts: dict[str, int] = {}
        for t in tables:
            try:
                counts[t] = len(db.open_table(t).to_arrow())
            except Exception:
                pass
        return ("ok" if counts else "empty", counts)
    except Exception as exc:
        return (f"error: {type(exc).__name__}: {exc}", {})


def _load_yaml_metadata(root: Path) -> list[dict[str, Any]]:
    """Load all paper metadata from YAML files."""
    papers: list[dict[str, Any]] = []
    yaml_dir = root / "02_Metadata" / "yaml"
    if not yaml_dir.exists():
        return papers
    try:
        import yaml
    except Exception:
        return papers
    for path in sorted(yaml_dir.glob("*.metadata.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if doc:
                papers.append(doc)
        except Exception:
            pass
    return papers


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance between two vectors (0 = identical, 2 = opposite)."""
    dot = float(sum(float(x) * float(y) for x, y in zip(a, b)))
    norm_a = float(sum(float(x) * float(x) for x in a) ** 0.5)
    norm_b = float(sum(float(x) * float(x) for x in b) ** 0.5)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - (dot / (norm_a * norm_b)))


# ── Stopwords for keyword extraction ──
_TOPIC_STOPWORDS = {
    # English function words
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "shall", "this", "that", "these", "those", "it", "its", "from",
    "by", "as", "into", "through", "during", "before", "after", "between",
    "against", "not", "without", "onto", "among", "via",
    # Academic filler words
    "study", "studies", "paper", "papers", "research", "result", "results",
    "finding", "findings", "evidence", "method", "methods", "data", "analysis",
    "effect", "effects", "role", "roles", "response", "responses",
    "gene", "genes", "protein", "proteins", "expression", "activity",
    "using", "based", "novel", "current", "new", "two", "one", "also",
    "found", "show", "shown", "report", "reported", "used", "use",
    "et", "al", "doi", "approach", "important", "various", "different", "many",
    "bacillus", "thuringiensis",
    # JSON / parser artifacts
    "citations", "citation", "source", "sources", "text", "title", "content",
    "field", "fields", "value", "values", "null", "undefined", "true", "false",
    "s001", "s002", "s003", "s004", "s005", "s006", "s007", "s008",
    "s009", "s010", "s011", "s012", "s013", "s014", "s015", "s016",
    # JSON artifact fragments
    "{\"text", "text\"", "\"text", "\"content", "\"citations",
    "than", "this", "that", "these", "those",
}


def _extract_keywords_from_text(text: str) -> list[str]:
    """Extract meaningful keywords from text, filtering stopwords and short tokens."""
    # Clean: remove JSON artifacts, code fences, markdown
    cleaned = text.lower()
    cleaned = cleaned.replace("{", " ").replace("}", " ").replace("[", " ").replace("]", " ")
    cleaned = cleaned.replace('"', " ").replace("'", " ").replace("`", " ")
    words = cleaned.replace(",", " ").replace(".", " ").replace(":", " ").replace(";", " ").replace("(", " ").replace(")", " ").replace("-", " ").replace("/", " ").split()
    freq: dict[str, int] = {}
    for w in words:
        w = w.strip()
        # Minimum 4 chars, filter stopwords, digits, JSON artifact fragments
        if len(w) < 4 or w in _TOPIC_STOPWORDS or w.isdigit():
            continue
        if w.startswith("{") or w.endswith("}"):
            continue
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)]


def _extract_cluster_keywords(
    pids: list[str],
    paper_map: dict[str, dict[str, Any]],
    root: Path,
    all_pids: list[str] | None = None,
) -> list[str]:
    """Extract top keywords from a cluster's papers (titles + tags + abstracts + summaries)."""
    all_text: list[str] = []
    for pid in pids:
        p = paper_map.get(pid)
        if not p:
            continue
        all_text.append(p.get("title") or "")
        all_text.append(p.get("abstract") or "")
        for tag in p.get("tags") or []:
            all_text.append(str(tag))
        summary = _load_summary_text(root, pid)
        if summary:
            all_text.append(summary)
    combined = " ".join(all_text)
    return _extract_keywords_from_text(combined)


def _build_topic_name(keywords: list[str], paper_titles: list[str] | None = None) -> str:
    """Build a human-readable topic name from keywords and paper titles.

    Avoids generic patterns like 'X and Y Research'. Uses representative paper
    titles to find meaningful noun phrases when keywords alone are too narrow.
    """
    if not keywords:
        return "Mixed research topic"

    # Filter: remove short/numeric/artifact tokens
    clean = [k for k in keywords if len(k) >= 3 and not k.isdigit() and k.lower() not in _TOPIC_STOPWORDS]
    if not clean:
        return "Mixed research topic"

    # Capitalize helper
    def title_case(w: str) -> str:
        return w[0].upper() + w[1:] if len(w) > 1 else w.upper()

    # If keywords are very diverse (low frequency overlap with each other), the topic
    # might be mixed — use the best keyword with a qualifier
    best = clean[0]
    second = clean[1] if len(clean) > 1 else None

    # Try to extract a descriptive phrase from paper titles
    if paper_titles:
        # Look for common multi-word phrases across paper titles
        title_words = []
        for t in paper_titles[:3]:
            # Clean title: remove special chars, take first 80 chars
            ct = t.lower().replace(",", " ").replace(":", " ").replace(";", " ")
            title_words.append(ct.split())

        # Find the most distinctive shared bigram/trigram
        from collections import Counter
        bigrams: Counter = Counter()
        for tw in title_words:
            for i in range(len(tw) - 1):
                bg = f"{tw[i]} {tw[i+1]}"
                if len(bg) > 8 and bg not in _TOPIC_STOPWORDS and not any(w in _TOPIC_STOPWORDS for w in bg.split()):
                    bigrams[bg] += 1

        if bigrams and bigrams.most_common(1)[0][1] >= 2:
            common_phrase = bigrams.most_common(1)[0][0]
            # Use the common phrase if it's meaningful
            phrase_titled = " ".join(title_case(w) for w in common_phrase.split())
            return phrase_titled

    # Two keywords: simple "X and Y"
    if len(clean) == 2 and second:
        return f"{title_case(best)} and {title_case(second)}"

    # Three or more: use primary keyword with context
    if len(clean) >= 3 and second:
        # Check if keywords are too similar (all same stem) or too diverse
        # If first two keywords share a prefix/suffix, they're probably variants
        if best.lower()[:4] == second.lower()[:4]:
            # Similar keywords — use the longer one + "Studies"
            longer = best if len(best) >= len(second) else second
            return f"{title_case(longer)} Studies"
        return f"{title_case(best)} and {title_case(second)} Research Topics"

    # Single keyword
    if len(clean) == 1:
        return f"{title_case(best)} Studies"

    return "Mixed research topic"


def _load_evidence_summary(root: Path, paper_id: str) -> dict[str, Any] | None:
    """Load a lightweight evidence summary for a paper.

    Evidence directories use title-based names with a 12-char hash suffix,
    while paper IDs use 'paper_' prefix with a 16-char hash suffix.
    We match by checking if the shorter hash is a prefix of the longer one.
    """
    evidence_root = root / "03_Evidence"
    if not evidence_root.exists():
        return None

    # Try exact match first
    ev_path = evidence_root / paper_id / "evidence.json"
    if ev_path.exists():
        return _parse_evidence_file(ev_path)

    # Extract hash from paper_id for matching
    search_hash = paper_id.replace("paper_", "") if paper_id.startswith("paper_") else paper_id

    # Build index of evidence dirs by their trailing hash (cached per call)
    for d in evidence_root.iterdir():
        if not d.is_dir():
            continue
        # Evidence dir names end with underscore + hash (e.g. "..._abc123def456")
        parts = d.name.rsplit("_", 1)
        if len(parts) != 2:
            continue
        ev_hash = parts[1]
        # Match: shorter hash is a prefix of the longer one
        if len(ev_hash) < len(search_hash):
            if search_hash.startswith(ev_hash):
                ev_path = d / "evidence.json"
                break
        else:
            if ev_hash.startswith(search_hash):
                ev_path = d / "evidence.json"
                break
        # Full directory name contains paper hash
        if search_hash in d.name or d.name in paper_id:
            ev_path = d / "evidence.json"
            break

    if not ev_path.exists():
        return None
    return _parse_evidence_file(ev_path)


def _parse_evidence_file(ev_path: Path) -> dict[str, Any] | None:
    """Parse an evidence.json file into the API evidence payload."""
    try:
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        return {
            "status": ev.get("status", "unknown"),
            "extraction_mode": ev.get("extraction_mode"),
            "fallback_used": ev.get("fallback_used", False),
            "core_findings": [
                {"finding": c.get("finding", c.get("text", ""))[:300], "quote": c.get("quote", "")[:200], "confidence": c.get("confidence", "medium")}
                for c in ev.get("core_findings", [])[:5]
            ],
            "key_results": [
                {"result": r.get("result", r.get("text", ""))[:300], "measured_variable": r.get("measured_variable", ""), "direction": r.get("direction", ""), "quote": r.get("quote", "")[:200], "confidence": r.get("confidence", "medium")}
                for r in ev.get("key_results", [])[:5]
            ],
            "discussion_points": [
                {"point": d.get("point", d.get("text", ""))[:300], "type": d.get("type", ""), "quote": d.get("quote", "")[:200], "confidence": d.get("confidence", "medium")}
                for d in ev.get("discussion_points", [])[:5]
            ],
            "methods": [
                {"name": m.get("name", m.get("text", ""))[:200], "purpose": m.get("purpose", ""), "evidence_type": m.get("evidence_type", ""), "quote": m.get("quote", "")[:150], "confidence": m.get("confidence", "medium")}
                for m in ev.get("methods", [])[:5]
            ],
            "limitations": [
                {"limitation": l.get("limitation", l.get("text", ""))[:300], "quote": l.get("quote", "")[:150], "confidence": l.get("confidence", "medium")}
                for l in ev.get("limitations", [])[:3]
            ],
            "open_questions": [
                {"question": o.get("question", o.get("text", ""))[:300], "quote": o.get("quote", "")[:150], "confidence": o.get("confidence", "medium")}
                for o in ev.get("open_questions", [])[:3]
            ],
            "claims": [
                {"claim": c.get("claim", c.get("text", ""))[:300], "quote": c.get("quote", "")[:150], "confidence": c.get("confidence", "medium")}
                for c in ev.get("claims", [])[:3]
            ],
            "result_discussion_links": [
                {
                    "result_index": rl.get("result_index"),
                    "discussion_index": rl.get("discussion_index"),
                    "link_type": rl.get("link_type", ""),
                    "basis": rl.get("basis", "")[:200],
                    "confidence": rl.get("confidence", "medium"),
                }
                for rl in ev.get("result_discussion_links", [])[:5]
            ],
            "coverage": ev.get("coverage", {}),
        }
    except Exception:
        return None


def _build_topic_paper_payload(root: Path, paper_record: dict[str, Any]) -> dict[str, Any]:
    """Build a paper dict with summary included for topic detail APIs."""
    pid = paper_record.get("paper_id") or paper_record.get("id", "")
    return {
        "paper_id": str(pid),
        "title": str(paper_record.get("title", "")),
        "authors": paper_record.get("authors", []) or [],
        "year": paper_record.get("year"),
        "journal": str(paper_record.get("journal", "")),
        "doi": str(paper_record.get("doi", "")),
        "summary": _load_summary_text(root, str(pid)) if pid else "",
        "evidence": _load_evidence_summary(root, str(pid)) if pid else None,
    }


def _compute_year_distribution(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute year distribution from a list of paper dicts."""
    this_year = datetime.now(timezone.utc).year
    counts: dict[int, int] = {}
    for p in papers:
        y = p.get("year")
        if y is None or (isinstance(y, float) and (y != y)):  # NaN check
            continue
        try:
            y = int(y)
        except (ValueError, TypeError):
            continue
        if y < 1800 or y > this_year + 1:
            continue
        counts[y] = counts.get(y, 0) + 1
    return [{"year": y, "count": c} for y, c in sorted(counts.items())]


def _select_representative_papers(
    cluster_pids: set[str],
    paper_map: dict[str, dict[str, Any]],
    vectors: dict[str, list[float]],
    seed_pid: str,
    count: int = 5,
) -> list[dict[str, Any]]:
    """Select representative papers from a cluster using multiple signals."""
    scored: list[tuple[str, float]] = []
    seed_vec = vectors.get(seed_pid)
    for pid in cluster_pids:
        if pid not in paper_map:
            continue
        score = 0.0
        # 1. Vector similarity to seed (centroid proxy)
        if seed_vec and pid in vectors:
            score += (1.0 - _cosine_distance(seed_vec, vectors[pid])) * 0.4
        # 2. Has evidence bonus
        p = paper_map[pid]
        if p.get("tags") and len(p.get("tags", [])) > 0:
            score += 0.15
        # 3. Year spread bonus — prefer variety
        y = p.get("year")
        if y:
            score += 0.05
        scored.append((pid, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    # Ensure year diversity: pick top-scored, but also force early/mid/recent
    selected: list[dict[str, Any]] = []
    seen_years: set[int] = set()
    for pid, s in scored:
        if len(selected) >= count:
            break
        p = paper_map.get(pid)
        if not p:
            continue
        y = p.get("year") or 0
        # If we already have 2+ papers from similar year range, try to diversify
        y_decade = (int(y) // 5) * 5 if y else 0
        if len(selected) >= 2 and sum(1 for sp in selected if ((sp.get("year") or 0) // 5) * 5 == y_decade) >= 2:
            continue
        selected.append({
            "paper_id": str(pid),
            "title": str(p.get("title", "")),
            "authors": p.get("authors", []) or [],
            "year": p.get("year"),
            "journal": str(p.get("journal", "")),
            "doi": str(p.get("doi", "")),
        })
        seen_years.add(y_decade)
    # If not enough, fill from top scored
    if len(selected) < min(3, count):
        for pid, s in scored:
            if len(selected) >= count:
                break
            if any(sp["paper_id"] == pid for sp in selected):
                continue
            p = paper_map.get(pid)
            if not p:
                continue
            selected.append({
                "paper_id": str(pid),
                "title": str(p.get("title", "")),
                "authors": p.get("authors", []) or [],
                "year": p.get("year"),
                "journal": str(p.get("journal", "")),
                "doi": str(p.get("doi", "")),
            })
    return selected


def _compute_topic_relevance(
    paper: dict[str, Any],
    topic_keywords: list[str],
    is_representative: bool,
) -> dict[str, Any]:
    """Compute topic relevance score for a paper."""
    score = 0.0
    reasons: list[str] = []
    title = str(paper.get("title", "")).lower()
    summary = str(paper.get("summary", "")).lower()
    text = title + " " + summary
    kw_lower = [k.lower() for k in topic_keywords]
    # Title overlap
    title_matches = sum(1 for k in kw_lower if k in title)
    if title_matches > 0:
        score += min(0.4, title_matches * 0.15)
        if title_matches >= 2:
            reasons.append("Shares multiple keywords in title")
    # Summary/text overlap
    text_matches = sum(1 for k in kw_lower if k in text)
    if text_matches > title_matches:
        score += min(0.3, (text_matches - title_matches) * 0.1)
        if text_matches >= 3:
            reasons.append("Shares summary and evidence signals with this topic")
    # Evidence bonus
    ev = paper.get("evidence")
    if ev and isinstance(ev, dict) and ev.get("status") != "failed" and ev.get("core_findings"):
        score += 0.15
        reasons.append("Has structured evidence")
    # Representative bonus
    if is_representative:
        score += 0.15
        reasons.append("Selected as representative paper for this topic")
    # Clamp
    score = min(score, 1.0)
    if score >= 0.6:
        label = "high"
    elif score >= 0.3:
        label = "medium"
    else:
        label = "low"
    if not reasons:
        if score >= 0.3:
            reasons.append("Moderate alignment with topic keywords and content")
        else:
            reasons.append("Weak alignment with topic keywords")
    return {
        "topic_relevance": round(score, 3),
        "relevance_label": label,
        "relevance_reason": "; ".join(reasons),
    }


def _build_evolution_phases(
    papers: list[dict[str, Any]],
    cluster_pids: set[str],
    paper_map: dict[str, dict[str, Any]],
    root: Path,
) -> list[dict[str, Any]]:
    """Build evolution phases (early/middle/recent) from cluster papers."""
    years = []
    for p in papers:
        y = p.get("year")
        if y is not None:
            try:
                yi = int(y)
                if 1800 <= yi <= datetime.now(timezone.utc).year + 1:
                    years.append(yi)
            except (ValueError, TypeError):
                pass
    if not years or len(set(years)) < 2:
        return []
    min_y, max_y = min(years), max(years)
    if max_y <= min_y:
        return []
    span = max_y - min_y
    third = max(1, int(span / 3))
    phase_defs = [
        ("early", "Early phase", min_y, min_y + third),
        ("middle", "Middle phase", min_y + third + 1, min_y + third * 2),
        ("recent", "Recent phase", min_y + third * 2 + 1, max_y),
    ]
    phases = []
    for ph_key, ph_label, ph_start, ph_end in phase_defs:
        ph_papers = [p for p in papers if p.get("year") and ph_start <= int(p.get("year") or 0) <= ph_end]
        ph_pids = [p["paper_id"] for p in ph_papers if p.get("paper_id")]
        ph_kw = _extract_cluster_keywords(ph_pids, paper_map, root) if ph_pids else []
        evidence_count = sum(1 for p in ph_papers if p.get("evidence") and isinstance(p["evidence"], dict) and p["evidence"].get("status") != "failed")
        # Include full paper payloads with evidence/summary for topic evolution display
        phases.append({
            "phase": ph_key,
            "label": ph_label,
            "year_range": [ph_start, ph_end],
            "paper_count": len(ph_papers),
            "keywords": [str(k) for k in ph_kw[:5]],
            "representative_papers": ph_papers[:3],
            "papers": ph_papers,
            "summary": " / ".join(ph_kw[:3]) if ph_kw else "",
            "evidence_coverage": {
                "papers_with_evidence": evidence_count,
                "total_papers": len(ph_papers),
            },
        })
    return phases


def _build_related_topics_for_cluster(
    cluster_id: str,
    clusters: list[dict[str, Any]],
    topic_relationships: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build related_topics list for a specific cluster from relationships."""
    related: list[dict[str, Any]] = []
    for rel in topic_relationships:
        other_id = None
        if rel.get("source_topic_id") == cluster_id:
            other_id = rel.get("target_topic_id")
        elif rel.get("target_topic_id") == cluster_id:
            other_id = rel.get("source_topic_id")
        if not other_id:
            continue
        other = next((c for c in clusters if c.get("cluster_id") == other_id), None)
        if not other:
            continue
        related.append({
            "cluster_id": other_id,
            "name": other.get("name", ""),
            "type": other.get("type", ""),
            "paper_count": other.get("paper_count", 0),
            "similarity": rel.get("similarity", 0),
            "shared_keywords": list(
                set(rel.get("shared_keywords", []) or [])
            ),
            "reason": rel.get("reason", "Shared topic similarity"),
        })
    # Sort by similarity desc, limit to 5
    related.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    return related[:5]


# ═══════════════════════════════════════════════════════════════
# Topic Deduplication & Merge V1
# ═══════════════════════════════════════════════════════════════

MERGE_CONFIG = {
    "enabled": True,
    "merge_threshold": 0.18,
    "weak_merge_threshold": 0.14,
    "min_keyword_overlap": 0.05,
    "max_parent_share": 1.0,  # disabled — use keyword similarity as sole gate
    "keep_subtopics": True,
}


def _topic_jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard similarity between two token lists."""
    sa = {x.lower() for x in a if x}
    sb = {x.lower() for x in b if x}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _compute_topic_similarity(
    t1: dict[str, Any], t2: dict[str, Any],
    vectors: dict[str, list[float]],
) -> float:
    """Compute combined topic similarity score."""
    score = 0.0
    weights = 0.0

    # 1. Keyword Jaccard (weight 0.40)
    kw1 = t1.get("keywords", [])
    kw2 = t2.get("keywords", [])
    kw_sim = _topic_jaccard(kw1, kw2)
    score += kw_sim * 0.40
    weights += 0.40

    # 2. Title token Jaccard from representative papers (weight 0.25)
    titles1 = " ".join(p.get("title", "") for p in t1.get("representative_papers", [])[:3])
    titles2 = " ".join(p.get("title", "") for p in t2.get("representative_papers", [])[:3])
    title_sim = _topic_jaccard(titles1.split(), titles2.split())
    score += title_sim * 0.25
    weights += 0.25

    # 3. Paper overlap (weight 0.10)
    pids1 = {p.get("paper_id", "") for p in t1.get("papers", [])}
    pids2 = {p.get("paper_id", "") for p in t2.get("papers", [])}
    union = pids1 | pids2
    paper_sim = len(pids1 & pids2) / max(len(union), 1)
    score += paper_sim * 0.10
    weights += 0.10

    # 4. Centroid similarity from representative paper vectors (weight 0.25)
    centroid_sim = 0.0
    rep1 = [p.get("paper_id", "") for p in t1.get("representative_papers", []) if p.get("paper_id") in vectors]
    rep2 = [p.get("paper_id", "") for p in t2.get("representative_papers", []) if p.get("paper_id") in vectors]
    if rep1 and rep2:
        sims = []
        for pid_a in rep1[:2]:
            for pid_b in rep2[:2]:
                sims.append(1.0 - _cosine_distance(vectors[pid_a], vectors[pid_b]))
        if sims:
            centroid_sim = float(sum(sims) / len(sims))
    score += centroid_sim * 0.25
    weights += 0.25

    # Normalize by actual weights used
    return score / weights if weights > 0 else 0.0


def _deduplicate_research_topics(
    clusters: list[dict[str, Any]],
    vectors: dict[str, list[float]],
) -> list[dict[str, Any]]:
    """Merge highly similar topics. Uses dynamic threshold based on observed similarities."""
    if not MERGE_CONFIG["enabled"] or len(clusters) <= 1:
        return clusters

    n = len(clusters)
    threshold = MERGE_CONFIG["merge_threshold"]

    # Compute all pairwise similarities
    all_pairs: list[tuple[int, int, float, float]] = []  # (i, j, combined_sim, kw_sim)
    for i in range(n):
        for j in range(i + 1, n):
            sim = _compute_topic_similarity(clusters[i], clusters[j], vectors)
            kw_sim = _topic_jaccard(
                clusters[i].get("keywords", []),
                clusters[j].get("keywords", []),
            )
            all_pairs.append((i, j, sim, kw_sim))

    if not all_pairs:
        return clusters

    # Build similarity graph — use keyword overlap as primary signal
    keyword_threshold = 0.28  # moderate overlap required for merge

    # Sort pairs by similarity, only merge the strongest ones
    all_pairs.sort(key=lambda x: -(x[2] * 0.4 + x[3] * 0.6))  # weighted: 40% combined, 60% kw

    # Direct-pair merging (no transitive union-find to avoid over-merging)
    merged_indices: set[int] = set()
    merge_pairs: list[tuple[int, int]] = []
    for i, j, sim, kw_sim in all_pairs:
        if i in merged_indices or j in merged_indices:
            continue  # already merged into another topic
        if kw_sim >= keyword_threshold:
            merge_pairs.append((i, j))
            merged_indices.add(i)
            merged_indices.add(j)

    if not merge_pairs:
        return clusters

    # Apply merges
    already_merged: set[int] = set()
    groups: dict[int, list[int]] = {}
    for i, j in merge_pairs:
        root = i
        if root not in groups:
            groups[root] = [root]
        if j not in already_merged:
            groups[root].append(j)
            already_merged.add(j)

    # Add unmerged topics
    for i in range(n):
        if i not in merged_indices:
            groups[i] = [i]

    # Build merged topics
    merged: list[dict[str, Any]] = []
    for root_idx, member_indices in groups.items():
        if len(member_indices) == 1:
            # Single topic, no merge needed
            c = dict(clusters[root_idx])
            c["is_merged"] = False
            c["subtopics"] = []
            merged.append(c)
        else:
            # Merge multiple topics
            members = [clusters[i] for i in member_indices]
            primary = max(members, key=lambda m: m.get("paper_count", 0))

            # Collect all papers (deduplicate by paper_id)
            all_papers: list[dict[str, Any]] = []
            seen_pids: set[str] = set()
            for m in members:
                for p in m.get("papers", []):
                    pid = p.get("paper_id", "")
                    if pid and pid not in seen_pids:
                        seen_pids.add(pid)
                        all_papers.append(p)

            # Collect all representative papers
            all_rep: list[dict[str, Any]] = []
            seen_rep: set[str] = set()
            for m in members:
                for p in m.get("representative_papers", []):
                    pid = p.get("paper_id", "")
                    if pid and pid not in seen_rep:
                        seen_rep.add(pid)
                        all_rep.append(p)

            # Re-select 5 representative papers: prefer those with topic_relevance high
            scored_rep = sorted(all_rep, key=lambda p: p.get("topic_relevance", 0), reverse=True)
            new_rep = scored_rep[:5]

            # Re-extract all keywords
            all_kw: list[str] = []
            for m in members:
                all_kw.extend(m.get("keywords", []))
            # Deduplicate preserving order
            seen_kw: set[str] = set()
            deduped_kw: list[str] = []
            for k in all_kw:
                kl = k.lower()
                if kl not in seen_kw and k.lower() not in _TOPIC_STOPWORDS:
                    seen_kw.add(kl)
                    deduped_kw.append(k)

            # Recompute years
            years = [
                int(p.get("year") or 0)
                for p in all_papers
                if p.get("year") is not None and int(p.get("year") or 0) > 1800
            ]
            year_range = [min(years), max(years)] if years else primary.get("year_range", [0, 0])

            # Recompute evidence coverage
            ev_count = sum(
                1 for p in all_papers
                if p.get("evidence") and isinstance(p.get("evidence"), dict)
                and p["evidence"].get("status") != "failed"
            )
            recent_years = sum(1 for y in years if y >= datetime.now(timezone.utc).year - 5)
            recent_ratio = recent_years / len(years) if years else 0

            # Build subtopics
            subtopics: list[dict[str, Any]] = []
            merged_from: list[str] = []
            max_sim = 0.0
            for m in members:
                merged_from.append(m.get("cluster_id", ""))
                if m != primary:
                    sim = _compute_topic_similarity(primary, m, vectors)
                    max_sim = max(max_sim, sim)
                    subtopics.append({
                        "cluster_id": m.get("cluster_id", ""),
                        "name": m.get("name", ""),
                        "paper_count": m.get("paper_count", 0),
                        "keywords": m.get("keywords", [])[:5],
                        "year_range": m.get("year_range", [0, 0]),
                        "merge_reason": "Merged due to shared keywords, representative paper similarity, and topic overlap.",
                        "similarity_to_parent": round(sim, 3),
                    })

            # Rebuild topic name
            sample_titles = [p.get("title", "") for p in new_rep[:3]]
            topic_name = _build_merged_topic_name(deduped_kw, sample_titles, [m.get("name", "") for m in members])

            # Type detection
            this_year = datetime.now(timezone.utc).year
            if len(all_papers) >= 6 and (max(years) - min(years)) >= 5 if years else True:
                ctype = "mature"
                trend = "active" if recent_ratio >= 0.4 else "stable"
            elif recent_ratio >= 0.4:
                ctype = "growing"
                trend = "active"
            else:
                ctype = "mature"
                trend = "stable"

            if recent_ratio >= 0.6:
                trend_label = "active"
            elif recent_ratio >= 0.3:
                trend_label = "stable"
            else:
                trend_label = "dormant" if recent_years == 0 else "stable"

            # Check max_parent_share safeguard
            total_papers = sum(c.get("paper_count", 0) for c in clusters)
            if len(all_papers) > total_papers * MERGE_CONFIG["max_parent_share"]:
                # Too large — keep as separate but mark as related broad topic
                for m in members:
                    mc = dict(m)
                    mc["is_merged"] = False
                    mc["subtopics"] = []
                    merged.append(mc)
                continue

            merged.append({
                "cluster_id": primary.get("cluster_id", ""),
                "name": topic_name,
                "type": ctype,
                "trend": trend,
                "paper_count": len(all_papers),
                "avg_year": float(round(sum(years) / len(years), 1)) if years else 0.0,
                "year_range": year_range,
                "keywords": [str(k) for k in deduped_kw[:8]],
                "summary": f"Integrated research topic covering {len(deduped_kw[:5])} key concepts across {len(all_papers)} papers.",
                "papers": all_papers,
                "representative_papers": new_rep,
                "recent_count": recent_years,
                "recent_ratio": round(recent_ratio, 3),
                "trend_label": trend_label,
                "trend_reason": f"Merged topic spanning {len(members)} related clusters.",
                "cohesion_score": round(primary.get("cohesion_score", 0.5), 3),
                "cohesion_label": primary.get("cohesion_label", "moderate"),
                "related_topics": [],
                "is_merged": len(member_indices) > 1,
                "subtopics": subtopics if MERGE_CONFIG["keep_subtopics"] else [],
                "merge_info": {
                    "merged_from": merged_from,
                    "merge_reason": f"Shared keywords, representative paper similarity, and semantic overlap (max sim: {max_sim:.3f})",
                    "max_similarity": round(max_sim, 3),
                } if len(member_indices) > 1 else None,
            })

    return merged


def _rebuild_relationships_for_clusters(
    clusters: list[dict[str, Any]],
    vectors: dict[str, list[float]],
) -> list[dict[str, Any]]:
    """Rebuild topic relationships using final (possibly merged) cluster list."""
    topic_relationships: list[dict[str, Any]] = []
    if len(clusters) < 2:
        return topic_relationships

    pairs: list[tuple[int, int, float, list[str]]] = []
    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            score = 0.0
            pids_i = [p["paper_id"] for p in clusters[i].get("representative_papers", []) if p.get("paper_id") in vectors]
            pids_j = [p["paper_id"] for p in clusters[j].get("representative_papers", []) if p.get("paper_id") in vectors]
            if pids_i and pids_j:
                score += 1.0 - _cosine_distance(vectors[pids_i[0]], vectors[pids_j[0]])
            kw_i = set(clusters[i].get("keywords", [])[:5])
            kw_j = set(clusters[j].get("keywords", [])[:5])
            shared = list(kw_i & kw_j)
            if kw_i and kw_j:
                score += len(shared) / max(len(kw_i | kw_j), 1) * 0.5
            score = score / 1.5
            if score > 0.25:
                pairs.append((i, j, score, shared))

    pairs.sort(key=lambda x: x[2], reverse=True)
    used_pairs: set[tuple[int, int]] = set()
    seen_counts: dict[int, int] = {}
    for i, j, score, shared in pairs:
        if (i, j) in used_pairs:
            continue
        if seen_counts.get(i, 0) >= 3 or seen_counts.get(j, 0) >= 3:
            continue
        used_pairs.add((i, j))
        seen_counts[i] = seen_counts.get(i, 0) + 1
        seen_counts[j] = seen_counts.get(j, 0) + 1
        reason_parts = []
        if shared:
            reason_parts.append("Shared keywords and")
        reason_parts.append("representative paper similarity")
        topic_relationships.append({
            "source_topic_id": clusters[i]["cluster_id"],
            "target_topic_id": clusters[j]["cluster_id"],
            "similarity": float(round(score, 3)),
            "shared_keywords": shared,
            "reason": " ".join(reason_parts),
        })
    return topic_relationships


def _compute_hot_papers(all_papers: list[dict[str, Any]], trending_topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score papers for hotspot relevance."""
    scored: list[tuple[dict[str, Any], float]] = []
    active_ids = {t["id"] for t in trending_topics[:5]}

    for p in all_papers:
        year = p.get("year") or 2000
        recency = min((int(year) - 2000) / 30.0, 1.0)
        rel = p.get("topic_relevance", 0.5)
        ev = p.get("evidence", {})
        if ev and isinstance(ev, dict):
            ev_rich = min((len(ev.get("key_results", [])) + len(ev.get("core_findings", [])) +
                          len(ev.get("discussion_points", [])) + len(ev.get("methods", []))) / 15.0, 1.0)
        else:
            ev_rich = 0.0
        score = 0.35 * recency + 0.25 * rel + 0.40 * ev_rich
        scored.append((p, score))

    scored.sort(key=lambda x: -x[1])
    results: list[dict[str, Any]] = []
    for p, score in scored[:10]:
        ev = p.get("evidence", {}) if isinstance(p.get("evidence"), dict) else {}
        results.append({
            "paper_id": p.get("paper_id", ""),
            "title": p.get("title", ""),
            "year": p.get("year"),
            "journal": p.get("journal", ""),
            "topic_name": "",
            "score": round(score, 3),
            "reason": "Recent paper with structured evidence and high topic relevance.",
            "evidence_counts": {
                "key_results": len(ev.get("key_results", [])),
                "core_findings": len(ev.get("core_findings", [])),
                "methods": len(ev.get("methods", [])),
                "discussion_points": len(ev.get("discussion_points", [])),
            },
        })
    return results


def _compute_emerging_facets(facet_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify emerging research facets."""
    results: list[dict[str, Any]] = []
    for fg in facet_groups:
        recent = 0; total = 0
        for st in fg.get("subtopics", []):
            years = [int(p.get("year") or 0) for p in st.get("papers", [])
                    if p.get("year") and int(p.get("year") or 0) > 1800]
            if years:
                max_y = max(years)
                recent += sum(1 for y in years if y >= max_y - 5)
                total += len(years)
        ratio = recent / max(total, 1)
        ev_total = sum(st.get("evidence_coverage", 0) for st in fg.get("subtopics", []))
        pc_total = sum(st.get("paper_count", 0) for st in fg.get("subtopics", []))
        results.append({
            "facet": fg["facet"],
            "label": fg["label"],
            "paper_count": fg["paper_count"],
            "recent_paper_count": recent,
            "recent_ratio": round(ratio, 3),
            "subtopic_count": len(fg.get("subtopics", [])),
            "trend_label": "active" if ratio >= 0.4 else ("stable" if ratio >= 0.2 else "dormant"),
            "evidence_coverage_ratio": round(ev_total / max(pc_total, 1), 3),
            "top_subtopics": [st.get("name", "") for st in fg.get("subtopics", [])[:3]],
        })
    results.sort(key=lambda x: -x["recent_ratio"])
    return results


def _compute_evidence_signals(all_papers: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate evidence chunk type statistics."""
    kr = cf = mt = dp = lm = oq = 0
    for p in all_papers:
        ev = p.get("evidence", {})
        if ev and isinstance(ev, dict):
            kr += len(ev.get("key_results", []))
            cf += len(ev.get("core_findings", []))
            mt += len(ev.get("methods", []))
            dp += len(ev.get("discussion_points", []))
            lm += len(ev.get("limitations", []))
            oq += len(ev.get("open_questions", []))
    return {
        "chunk_type_distribution": {
            "key_result": kr, "core_finding": cf, "method": mt,
            "discussion_point": dp, "limitation": lm, "open_question": oq,
        },
    }


def _compute_light_method_shifts(subtopics: list[dict[str, Any]], all_papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect method shifts by comparing early vs recent papers in each subtopic."""
    shifts: list[dict[str, Any]] = []
    for st in subtopics[:8]:
        papers = st.get("papers", []) if "papers" in st else []
        if not papers:
            papers = [p for p in all_papers if p.get("paper_id") in {sp.get("paper_id") for sp in st.get("representative_papers", [])}]
        if len(papers) < 2:
            continue
        # Split by median year
        years = [(i, int(p.get("year") or 0)) for i, p in enumerate(papers) if p.get("year") and int(p.get("year") or 0) > 1800]
        if len(years) < 2:
            continue
        years.sort(key=lambda x: x[1])
        median = years[len(years) // 2][1]
        early_methods: set[str] = set()
        recent_methods: set[str] = set()
        for i, p in enumerate(papers):
            ev = p.get("evidence", {})
            if not ev or not isinstance(ev, dict):
                continue
            y = int(p.get("year") or 0)
            for m in ev.get("methods", [])[:3]:
                name = str(m.get("name", "")).lower().strip() if isinstance(m, dict) else str(m).lower().strip()
                if name and len(name) > 3:
                    (recent_methods if y >= median else early_methods).add(name)
        new_methods = sorted(recent_methods - early_methods)
        stable_methods = sorted(early_methods & recent_methods)
        if new_methods:
            shifts.append({
                "topic_id": st.get("id", st.get("cluster_id", "")),
                "topic_name": st.get("name", ""),
                "facet_label": st.get("facet_label", ""),
                "from_phase": "Early",
                "to_phase": "Recent",
                "new_methods": new_methods[:5],
                "stable_methods": stable_methods[:5],
                "confidence": "medium" if len(stable_methods) >= 2 else "low",
            })
    return shifts[:5]


def _build_merged_topic_name(
    keywords: list[str],
    rep_titles: list[str],
    member_names: list[str],
) -> str:
    """Build a topic name for a merged topic. Avoids repetitive 'X and Y Research'."""
    if not keywords:
        return "Integrated research topic"

    clean = [k for k in keywords if k.lower() not in _TOPIC_STOPWORDS]
    if not clean:
        return "Integrated research topic"

    # Find shared bigrams across rep titles
    from collections import Counter
    bigrams: Counter = Counter()
    for t in rep_titles[:3]:
        words = t.lower().replace(",", " ").replace(":", " ").split()
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i+1]}"
            if len(bg) > 8 and bg not in _TOPIC_STOPWORDS:
                bigrams[bg] += 1

    if bigrams and bigrams.most_common(1)[0][1] >= 2:
        phrase = bigrams.most_common(1)[0][0]
        titled = " ".join(w[0].upper() + w[1:] if len(w) > 1 else w.upper() for w in phrase.split())
        return titled

    # Use best keyword as primary concept
    best = clean[0]
    best_titled = best[0].upper() + best[1:] if len(best) > 1 else best.upper()

    # If multiple clusters were merged (member_names > 1), use broader label
    if len(member_names) > 2:
        second = clean[1] if len(clean) > 1 else ""
        if second:
            second_titled = second[0].upper() + second[1:] if len(second) > 1 else second.upper()
            return f"{best_titled} and {second_titled}"
        return f"{best_titled} Research"

    return _build_topic_name(keywords, rep_titles)


def _build_research_map_clusters(
    root: Path,
    papers: list[dict[str, Any]],
    vectors: dict[str, list[float]],
    limit: int = 15,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Shared clustering function used by both /research-map and /research-map/topic/{id}.

    Returns (clusters, topic_relationships).
    Each cluster contains full papers and representative_papers.
    """
    paper_map: dict[str, dict[str, Any]] = {}
    for p in papers:
        pid = p.get("paper_id", "")
        if pid:
            paper_map[pid] = p

    # ── Build vector-ID → paper-ID cross-reference ──
    # Vector IDs are title-based (e.g. "Title_hashsuffix"), while paper IDs
    # are "paper_hashsuffix". Match by extracting and comparing hash suffixes.
    vector_to_paper: dict[str, str] = {}
    paper_hash_map: dict[str, str] = {}  # short_hash -> paper_id
    for pid in paper_map:
        # Extract hash suffix from "paper_<hash>"
        if pid.startswith("paper_"):
            h = pid[6:]
            paper_hash_map[h] = pid
            # Also index shorter prefixes (min 8 chars) for partial matches
            for ln in range(8, len(h) + 1):
                paper_hash_map[h[:ln]] = pid

    for vid in vectors:
        # Try exact match first
        if vid in paper_map:
            vector_to_paper[vid] = vid
            continue
        # Extract trailing hash from vector ID (last underscore segment)
        parts = vid.rsplit("_", 1)
        if len(parts) == 2:
            suffix = parts[1]
            if suffix in paper_hash_map:
                vector_to_paper[vid] = paper_hash_map[suffix]
                continue
        # Try containing match (paper_id substring in vector_id or vice versa)
        for pid in paper_map:
            if pid in vid or vid in pid:
                vector_to_paper[vid] = pid
                break

    def _resolve_pid(vid: str) -> str | None:
        """Resolve a vector ID to a paper ID, or return None."""
        if vid in paper_map:
            return vid
        return vector_to_paper.get(vid)

    MIN_CLUSTER = 3
    MAX_CLUSTERS = 8
    used: set[str] = set()
    clusters: list[dict[str, Any]] = []

    paper_ids = list(vectors.keys())
    import random
    random.seed(42)  # fixed seed for reproducible clusters
    random.shuffle(paper_ids)

    for _ in range(MAX_CLUSTERS):
        # Find next unused seed
        seed = None
        for pid in paper_ids:
            if pid not in used:
                seed = pid
                break
        if seed is None:
            break

        # Find nearest neighbors
        qv = vectors[seed]
        scored: list[tuple[str, float]] = []
        for pid in paper_ids:
            if pid in used or pid == seed:
                continue
            if pid not in vectors:
                continue
            dist = _cosine_distance(qv, vectors[pid])
            scored.append((pid, dist))

        scored.sort(key=lambda x: x[1])
        neighbors = [pid for pid, _ in scored[:MIN_CLUSTER * 3]]

        # Form cluster
        cluster_pids: set[str] = {seed}
        for pid in neighbors:
            cluster_pids.add(pid)
            if len(cluster_pids) >= MIN_CLUSTER * 4:
                break

        if len(cluster_pids) < MIN_CLUSTER:
            continue

        # Compute cluster stats — resolve vector IDs to paper IDs
        cluster_paper_ids: list[str] = []  # paper IDs (resolved from vector IDs)
        resolved_map: dict[str, str] = {}  # vector_id -> paper_id
        for pid in cluster_pids:
            rpid = _resolve_pid(pid)
            if rpid:
                cluster_paper_ids.append(rpid)
                resolved_map[pid] = rpid
            else:
                cluster_paper_ids.append(pid)  # keep as-is as fallback
                resolved_map[pid] = pid

        years = [
            int(paper_map[rpid].get("year") or 0)
            for rpid in cluster_paper_ids
            if rpid in paper_map and paper_map[rpid].get("year")
        ]
        avg_year = float(sum(years) / len(years)) if years else 0.0

        # Build full papers list for this cluster
        all_cluster_papers: list[dict[str, Any]] = []
        seen_pids: set[str] = set()
        for pid in cluster_pids:
            rpid = resolved_map.get(pid, pid)
            p = paper_map.get(rpid)
            if p:
                paper_pid = p.get("paper_id", rpid)
                if paper_pid not in seen_pids:
                    seen_pids.add(paper_pid)
                    all_cluster_papers.append(_build_topic_paper_payload(root, p))
            else:
                # Fallback: search by partial match
                for k, v in paper_map.items():
                    if (pid in k or k in pid or rpid in k or k in rpid):
                        paper_pid = v.get("paper_id", k)
                        if paper_pid not in seen_pids:
                            seen_pids.add(paper_pid)
                            all_cluster_papers.append(_build_topic_paper_payload(root, v))
                        break

        # Extract keywords using resolved paper IDs
        keywords = _extract_cluster_keywords(cluster_paper_ids, paper_map, root, paper_ids)
        # Ensure minimum quality keywords — if empty, retry with broader text
        if not keywords or len(keywords) < 2:
            keywords = _extract_cluster_keywords(cluster_paper_ids, paper_map, root)

        # Build topic name — prefer cleaned keywords, fallback to paper titles
        seed_rpid = _resolve_pid(seed) or seed
        seed_paper = paper_map.get(seed_rpid)
        # Collect a few representative paper titles for name generation context
        sample_titles = [p.get("title", "") for p in list(all_cluster_papers[:3])]
        topic_name = _build_topic_name(keywords, sample_titles) if keywords else (
            seed_paper.get("title", f"Topic {len(clusters) + 1}")[:80] if seed_paper else f"Research Topic {len(clusters) + 1}"
        )

        # Build summary
        summary_text = " / ".join(keywords[:5]) if keywords else ""
        if summary_text:
            summary_text = f"Research cluster covering {summary_text.lower()}."

        # Year range
        if years:
            year_range = [int(min(years)), int(max(years))]
        else:
            year_range = [0, 0]

        # Type detection
        this_year = datetime.now(timezone.utc).year
        recent_count = sum(1 for y in years if y >= this_year - 5)
        recent_ratio = recent_count / len(years) if years else 0
        year_span = max(years) - min(years) if len(years) >= 2 else 0

        if len(cluster_pids) >= 6 and year_span >= 5:
            ctype = "mature"
            trend = "active" if recent_ratio >= 0.4 else "stable"
        elif recent_ratio >= 0.4 or avg_year >= this_year - 5:
            ctype = "growing"
            trend = "active"
        elif len(cluster_pids) <= 3:
            ctype = "gap"
            trend = "sparse"
        else:
            ctype = "mature"
            trend = "stable"

        # Trend details
        if recent_count == 0:
            trend_label = "dormant"
            trend_reason = "No recent publications in the last 5 years."
        elif recent_ratio >= 0.6:
            trend_label = "emerging" if len(cluster_pids) <= 5 else "active"
            trend_reason = "High proportion of recent publications."
        elif recent_ratio >= 0.3:
            trend_label = "active"
            trend_reason = "Steady recent publication activity."
        else:
            trend_label = "stable"
            trend_reason = "Topic spans multiple years with moderate recent activity."

        # Select representative papers (smart selection using vector + year diversity)
        # Build a resolved paper_map equivalent for vector IDs
        resolved_paper_map: dict[str, dict[str, Any]] = {}
        for vid in cluster_pids:
            rpid = resolved_map.get(vid, vid)
            p = paper_map.get(rpid)
            if p:
                resolved_paper_map[vid] = p
        rep_papers = _select_representative_papers(cluster_pids, resolved_paper_map, vectors, seed, count=5)

        # Cohesion: average pairwise similarity within cluster
        cohesion = 0.5
        vec_pids = [pid for pid in cluster_pids if pid in vectors]
        if len(vec_pids) >= 2:
            sims = []
            for a in range(min(len(vec_pids), 10)):
                for b in range(a + 1, min(len(vec_pids), 10)):
                    sims.append(1.0 - _cosine_distance(vectors[vec_pids[a]], vectors[vec_pids[b]]))
            if sims:
                cohesion = sum(sims) / len(sims)
        cohesion_label = "high" if cohesion >= 0.7 else ("moderate" if cohesion >= 0.4 else "low")

        cluster_id = f"topic_{len(clusters) + 1:03d}"

        # Compute topic relevance for each paper
        papers_with_relevance = []
        for p in all_cluster_papers:
            is_rep = any(rp["paper_id"] == p["paper_id"] for rp in rep_papers)
            rel = _compute_topic_relevance(p, keywords, is_rep)
            papers_with_relevance.append({**p, **rel})

        clusters.append({
            "cluster_id": cluster_id,
            "name": topic_name,
            "type": ctype,
            "trend": trend,
            "paper_count": int(len(cluster_pids)),
            "avg_year": float(round(avg_year, 1)),
            "year_range": year_range,
            "keywords": [str(k) for k in keywords[:8]],
            "summary": str(summary_text),
            "papers": papers_with_relevance,
            "representative_papers": rep_papers,
            "recent_count": recent_count,
            "recent_ratio": round(recent_ratio, 3),
            "trend_label": trend_label,
            "trend_reason": trend_reason,
            "cohesion_score": round(cohesion, 3),
            "cohesion_label": cohesion_label,
        })
        used.update(cluster_pids)

    # ── Build topic relationships ──
    topic_relationships: list[dict[str, Any]] = []
    if len(clusters) >= 2:
        pairs: list[tuple[int, int, float, list[str]]] = []
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                score = 0.0
                # Centroid similarity using representative papers
                pids_i = [p["paper_id"] for p in clusters[i]["representative_papers"] if p["paper_id"] in vectors]
                pids_j = [p["paper_id"] for p in clusters[j]["representative_papers"] if p["paper_id"] in vectors]
                if pids_i and pids_j:
                    score += 1.0 - _cosine_distance(vectors[pids_i[0]], vectors[pids_j[0]])
                # Keyword overlap
                kw_i = set(clusters[i].get("keywords", [])[:5])
                kw_j = set(clusters[j].get("keywords", [])[:5])
                shared = []
                if kw_i and kw_j:
                    shared = list(kw_i & kw_j)
                    overlap = len(shared) / max(len(kw_i | kw_j), 1)
                    score += overlap * 0.5
                score = score / 1.5  # normalise
                if score > 0.25:
                    pairs.append((i, j, score, shared))
        pairs.sort(key=lambda x: x[2], reverse=True)
        # Keep top 3 per topic
        used_pairs: set[tuple[int, int]] = set()
        seen_counts: dict[int, int] = {}
        for i, j, score, shared in pairs:
            if (i, j) in used_pairs:
                continue
            if seen_counts.get(i, 0) >= 3 or seen_counts.get(j, 0) >= 3:
                continue
            used_pairs.add((i, j))
            seen_counts[i] = seen_counts.get(i, 0) + 1
            seen_counts[j] = seen_counts.get(j, 0) + 1
            reason_parts = []
            if shared:
                reason_parts.append("Shared keywords and")
            reason_parts.append("representative paper similarity")
            topic_relationships.append({
                "source_topic_id": clusters[i]["cluster_id"],
                "target_topic_id": clusters[j]["cluster_id"],
                "similarity": float(round(score, 3)),
                "shared_keywords": shared,
                "reason": " ".join(reason_parts),
            })

    # ── Deduplicate & merge similar topics ──
    clusters = _deduplicate_research_topics(clusters, vectors)

    # ── Rebuild relationships using final (possibly merged) clusters ──
    topic_relationships = _rebuild_relationships_for_clusters(clusters, vectors)

    return clusters, topic_relationships


def _empty_cluster_result() -> dict[str, Any]:
    return {
        "mature_topics": [], "growing_topics": [], "gap_topics": [],
        "topic_relationships": [], "clusters": [],
        "network_stats": {"total_nodes": 0, "total_edges": 0},
    }


def _build_related_results(root: Path, neighbors: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    """Map LanceDB search results to related-paper objects with metadata."""
    papers = {p.get("paper_id"): p for p in _load_yaml_metadata(root)}
    results: list[dict[str, Any]] = []
    for row in neighbors:
        pid = str(row.get("paper_id", ""))
        p = papers.get(pid)
        if not p:
            # Fallback: use fields from the vector row
            results.append({
                "paper_id": pid,
                "title": str(row.get("title", row.get("text", ""))[:200]),
                "authors": [],
                "year": row.get("year"),
                "journal": str(row.get("journal", "")),
                "doi": str(row.get("doi", "")),
                "similarity": round(1.0 - float(row.get("_distance", 0.0)), 4),
                "reason": f"Vector similarity based on paper embedding",
            })
        else:
            results.append({
                "paper_id": pid,
                "title": p.get("title", ""),
                "authors": p.get("authors", []) or [],
                "year": p.get("year"),
                "journal": p.get("journal", ""),
                "doi": p.get("doi", ""),
                "similarity": round(1.0 - float(row.get("_distance", 0.0)), 4),
                "reason": "Vector similarity based on paper embedding",
            })
    return results


def _load_summary_snippet(root: Path, paper_id: str, max_chars: int = 200) -> str | None:
    """Return a short text snippet from the summary, or None."""
    text = _load_summary_text(root, paper_id)
    if not text:
        return None
    # Take first sentence-ish chunk
    snippet = text[:max_chars].rsplit(".", 1)[0] + "." if "." in text[:max_chars] else text[:max_chars]
    return snippet


def _load_summary_text(root: Path, paper_id: str) -> str | None:
    """Load summary.md for a paper, extracting text from JSON."""
    summary_path = root / "03_Summary" / paper_id / "summary.md"
    if not summary_path.exists():
        return None
    try:
        content = summary_path.read_text(encoding="utf-8")
        data = json.loads(content)
        sections: list[str] = []
        for key in ["Core Finding", "Evidence", "Methods", "Key Results", "Limitations", "Relevance to My Research"]:
            items = data.get(key, [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "text" in item:
                        sections.append(f"**{key}**: {item['text']}")
                    elif isinstance(item, str):
                        sections.append(f"**{key}**: {item}")
        return "\n\n".join(sections) if sections else content[:2000]
    except (json.JSONDecodeError, Exception):
        return content[:2000] if len(content) < 5000 else content[:2000] + "..."


# ── App factory ──

# ── Phase 0.8: Request/Response models (module-level for FastAPI compatibility) ──

VALID_CHUNK_TYPES = {"section", "method", "result", "claim", "figure", "table", "supplementary_table", "supplementary_entity"}

class QueryAssetsRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    top_k: int = Field(default=10, ge=1, le=50)
    chunk_types: list[str] | None = None
    paper_id: str | None = None
    min_quality_score: float = Field(default=0.0, ge=0.0, le=100.0)
    include_metadata: bool = True

class AssetResultItem(BaseModel):
    chunk_id: str
    paper_id: str
    chunk_type: str
    text: str
    score: float = 0.0
    linked_evidence_id: str = ""
    linked_evidence_ids: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    linked_claims: list[str] = Field(default_factory=list)
    linked_methods: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    quality_score: float = 0.0
    citation_key: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

class QueryAssetsResponse(BaseModel):
    query: str
    results: list[AssetResultItem] = Field(default_factory=list)
    count: int = 0
    unique_papers: int = 0
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: float = 0.0

class AgentAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    chunk_types: list[str] | None = None
    include_evidence: bool = True
    include_assets: bool = True
    paper_id: str | None = None
    use_llm: bool = True
    return_context: bool = False

class AgentCitation(BaseModel):
    ref_id: str
    chunk_id: str
    paper_id: str
    paper_title: str = ""
    paper_year: int | None = None
    text_snippet: str = ""
    linked_evidence_id: str = ""
    source: str = ""
    confidence: str = "medium"

class AgentContextChunk(BaseModel):
    chunk_id: str = ""
    paper_id: str = ""
    chunk_type: str = ""
    text: str = ""
    source: str = ""
    score: float = 0.0

class AgentContextPack(BaseModel):
    chunks: list[AgentContextChunk] = Field(default_factory=list)
    papers: dict[str, Any] = Field(default_factory=dict)

class AgentTokenUsage(BaseModel):
    provider: str = ""
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_input_cost_usd: float | None = None
    estimated_output_cost_usd: float | None = None
    estimated_total_cost_usd: float | None = None
    currency: str = "USD"
    source: str = "unavailable"
    note: str | None = None

class AgentAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[AgentCitation] = Field(default_factory=list)
    context_used: int = 0
    papers_cited: int = 0
    model: str = ""
    elapsed_ms: float = 0.0
    intent: str = ""
    context: AgentContextPack | None = None
    token_usage: AgentTokenUsage | None = None


def create_app(root: Path | None = None) -> FastAPI:
    if FastAPI is None:
        raise RuntimeError("FastAPI is required. Install: pip install fastapi uvicorn")

    root = _resolve_root(root)
    svc = LiteratureQueryService(root)

    api = FastAPI(
        title="Scientra Copilot Query API",
        version="0.1.0",
        description="Unified Scientra Copilot query API.",
    )

    # Allow the Web frontend on any localhost port to call the API.
    # List every possible localhost origin explicitly — port wildcards
    # are not supported by Starlette CORSMiddleware.
    _web_ports = [3000, 3001, 3002, 3003, 3004, 3005, 8710]
    _cors_origins: list[str] = []
    for _p in _web_ports:
        _cors_origins.extend([
            f"http://localhost:{_p}",
            f"http://127.0.0.1:{_p}",
        ])

    api.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── /health ──

    @api.get("/health")
    def health() -> dict[str, object]:
        l_status, l_counts = _lancedb_info(root)
        embedding_model = "BAAI/bge-m3"
        report_path = root / "04_VectorDB" / "embedding_report.json"
        if report_path.exists():
            try:
                embedding_model = json.loads(report_path.read_text(encoding="utf-8")).get("embedding_model", embedding_model)
            except Exception:
                pass
        return {
            "api_status": "ok",
            "lancedb_status": l_status,
            "table_counts": l_counts,
            "embedding_model": embedding_model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── /version ──

    @api.get("/version")
    def api_version() -> dict[str, object]:
        return {
            "app": "Scientra Copilot",
            "api_version": "dev",
            "research_map_schema": "v2",
            "evidence_engine": "v2.2",
        }

    # ── /stats ──

    @api.get("/stats")
    def stats() -> dict[str, object]:
        papers = _load_yaml_metadata(root)
        tag_counter: Counter = Counter()
        year_counter: Counter = Counter()
        for p in papers:
            for tag in p.get("tags", []) or []:
                tag_counter[str(tag)] += 1
            year = p.get("year")
            if year:
                year_counter[str(year)] += 1
        l_status, l_counts = _lancedb_info(root)
        return {
            "paper_count": len(papers),
            "metadata_embedding_count": l_counts.get("literature_vectors", 0),
            "summary_embedding_count": l_counts.get("literature_vectors", 0),
            "chunk_embedding_count": l_counts.get("literature_vectors", 0),
            "tag_distribution": dict(tag_counter.most_common(30)),
            "year_distribution": dict(sorted(year_counter.items())),
        }

    # ── /papers — paginated paper list ──

    @api.get("/papers")
    def list_papers(
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        year: int | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
        toxin: str | None = None,
        species: str | None = None,
        method: str | None = None,
        tag: str | None = None,
        sort: str | None = None,
    ) -> dict[str, Any]:
        papers = _load_yaml_metadata(root)

        # ── Filters (AND logic) ──

        if q:
            q_lower = q.lower()
            filtered: list[dict[str, Any]] = []
            for p in papers:
                title = (p.get("title") or "").lower()
                abstract = (p.get("abstract") or "").lower()
                tags_text = " ".join(str(t).lower() for t in (p.get("tags") or []))
                toxin_text = " ".join(str(t).lower() for t in (p.get("toxin") or []))
                species_text = " ".join(str(s).lower() for s in (p.get("species") or []))
                method_text = " ".join(str(m).lower() for m in (p.get("method") or []))
                summary = (_load_summary_text(root, p.get("paper_id", "")) or "").lower()
                combined = f"{title} {abstract} {tags_text} {toxin_text} {species_text} {method_text} {summary}"
                if q_lower in combined:
                    filtered.append(p)
            papers = filtered

        if year is not None:
            papers = [p for p in papers if p.get("year") == year]
        else:
            if year_start is not None:
                papers = [p for p in papers if (p.get("year") or 0) >= year_start]
            if year_end is not None:
                papers = [p for p in papers if (p.get("year") or 9999) <= year_end]

        if toxin:
            papers = [p for p in papers if toxin.lower() in " ".join(str(t).lower() for t in (p.get("toxin") or []))]
        if species:
            papers = [p for p in papers if species.lower() in " ".join(str(s).lower() for s in (p.get("species") or []))]
        if method:
            papers = [p for p in papers if method.lower() in " ".join(str(m).lower() for m in (p.get("method") or []))]
        if tag:
            papers = [p for p in papers if any(tag.lower() in str(t).lower() for t in (p.get("tags") or []))]

        # ── Sort ──
        if sort == "year_desc":
            papers.sort(key=lambda p: p.get("year") or 0, reverse=True)
        elif sort == "year_asc":
            papers.sort(key=lambda p: p.get("year") or 0)
        elif sort == "title":
            papers.sort(key=lambda p: (p.get("title") or "").lower())
        # default: relevance = keep original order (from YAML discovery)

        total = len(papers)
        start = (page - 1) * page_size
        page_papers = papers[start : start + page_size]

        results: list[dict[str, Any]] = []
        for p in page_papers:
            pid = p.get("paper_id", "")
            summary_snippet = _load_summary_snippet(root, pid)
            results.append({
                "paper_id": pid,
                "title": p.get("title", ""),
                "authors": p.get("authors", []) or [],
                "year": p.get("year"),
                "journal": p.get("journal", ""),
                "doi": p.get("doi", ""),
                "tags": p.get("tags", []) or [],
                "species": p.get("species", []) or [],
                "toxin": p.get("toxin", []) or [],
                "abstract_snippet": (p.get("abstract") or "")[:300],
                "summary_snippet": summary_snippet,
            })
        return {
            "papers": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    # ── POST /query (Web-compatible simplified endpoint) ──

    @api.post("/query")
    def web_query(body: dict[str, Any]) -> dict[str, Any]:
        query_text = str(body.get("query", "") or "")
        top_k = int(body.get("top_k", 10))
        mode = body.get("mode", "keyword")
        level = body.get("level", "all")
        use_vector = mode in ("vector", "hybrid")

        # Ensure filter values are lists or None
        def _list(value: Any) -> list[str] | None:
            if value is None:
                return None
            if isinstance(value, list):
                return [str(v) for v in value]
            if isinstance(value, str):
                return [value]
            return None

        req = LiteratureQueryRequest(
            query_type=QueryType.search_by_keyword if not use_vector else QueryType.hybrid_search,
            query=query_text,
            top_k=top_k,
            filters=QueryFilters(
                tags=_list(body.get("tags")) or [],
                species=_list(body.get("host")) or _list(body.get("species")) or [],
                toxin=_list(body.get("toxin")) or [],
                method=_list(body.get("method")) or [],
                mechanism=_list(body.get("mechanism")) or [],
                year=body.get("year"),
            ),
            use_vector=use_vector,
            include_summaries=True,
            include_evidence=False,
            include_citations=False,
        )
        resp = svc.query(req)
        results: list[dict[str, Any]] = []
        for paper in resp.papers:
            results.append({
                "paper_id": paper.paper_id,
                "title": paper.title,
                "journal": paper.journal,
                "year": paper.year,
                "doi": paper.doi,
                "authors": paper.authors,
                "tags": paper.tags,
                "species": paper.species,
                "toxin": paper.toxin,
                "method": paper.method,
                "mechanism": paper.mechanism,
                "score": _find_score(resp, paper.paper_id),
            })
        return {
            "query": query_text,
            "mode": mode,
            "top_k": top_k,
            "level": level,
            "total": resp.total,
            "results": results,
            "include_candidate_tags": True,
            "policy": {"agent_entrypoint": "literature_query"},
        }

    # ── /paper/{id}/metadata ──

    @api.get("/paper/{paper_id}/metadata")
    def paper_metadata(paper_id: str) -> dict[str, Any]:
        papers = _load_yaml_metadata(root)
        for p in papers:
            pid = p.get("paper_id", "")
            if pid == paper_id or p.get("key", "") == paper_id:
                return {
                    "paper_id": pid,
                    "title": p.get("title", ""),
                    "journal": p.get("journal", ""),
                    "year": p.get("year"),
                    "doi": p.get("doi", ""),
                    "authors": p.get("authors", []) or [],
                    "tags": p.get("tags", []) or [],
                    "species": p.get("species", []) or [],
                    "toxin": p.get("toxin", []) or [],
                    "method": p.get("method", []) or [],
                    "mechanism": p.get("mechanism", []) or [],
                }
        raise HTTPException(status_code=404, detail=f"Paper not found: {paper_id}")

    # ── /paper/{id}/summary ──

    @api.get("/paper/{paper_id}/summary")
    def paper_summary(paper_id: str) -> dict[str, Any]:
        text = _load_summary_text(root, paper_id)
        if text is None:
            raise HTTPException(status_code=404, detail=f"Summary not found: {paper_id}")
        return {"paper_id": paper_id, "summary_path": f"03_Summary/{paper_id}/summary.md", "text": text, "sections": {}}

    # ── /paper/{id}/tags ──

    @api.get("/paper/{paper_id}/tags")
    def paper_tags(paper_id: str) -> dict[str, Any]:
        papers = _load_yaml_metadata(root)
        for p in papers:
            pid = p.get("paper_id", "")
            if pid == paper_id or p.get("key", "") == paper_id:
                return {
                    "paper_id": pid,
                    "tags": p.get("tags", []) or [],
                    "species": p.get("species", []) or [],
                    "toxin": p.get("toxin", []) or [],
                    "method": p.get("method", []) or [],
                    "mechanism": p.get("mechanism", []) or [],
                }
        raise HTTPException(status_code=404, detail=f"Paper not found: {paper_id}")

    # ── /paper/{id}/related ──

    @api.get("/paper/{paper_id}/related")
    def paper_related(paper_id: str, limit: int = 5) -> dict[str, Any]:
        limit = max(1, min(limit, 20))

        # ── Attempt vector search ──
        try:
            import lancedb

            db_dir = root / "04_VectorDB" / "lancedb"
            if db_dir.exists() and any(db_dir.iterdir()):
                db = lancedb.connect(str(db_dir))
                table_names = db.table_names()
                if table_names:
                    table = db.open_table(table_names[0])

                    # Find query paper's vector — use to_pandas() or fallback
                    query_rows: list[dict[str, Any]] = []
                    try:
                        df = table.to_pandas()
                        query_rows = [r for r in df.to_dict("records")
                                      if str(r.get("paper_id")) == paper_id][:1]
                    except Exception:
                        pass

                    if query_rows and query_rows[0].get("vector") is not None:
                        qv = query_rows[0]["vector"]
                        # Search neighbors
                        raw = table.search(qv).limit(limit + 10).to_list()

                        # Exclude self, take top N
                        neighbors = [
                            r for r in raw
                            if str(r.get("paper_id", "")) != paper_id
                        ][:limit]

                        if neighbors:
                            related = _build_related_results(root, neighbors, source="vector")
                            return {
                                "paper_id": paper_id,
                                "related": related,
                                "source": "vector",
                                "count": len(related),
                                "reason": None,
                            }
        except Exception:
            pass  # fall through to keyword fallback

        # ── Keyword fallback ──
        papers = _load_yaml_metadata(root)
        current = next((p for p in papers if p.get("paper_id") == paper_id), None)

        if current:
            # Build query text from available fields
            query_parts: list[str] = []
            for field in ["title", "abstract", "journal"]:
                val = current.get(field)
                if val and isinstance(val, str):
                    query_parts.append(val)
            for field in ["tags", "toxin", "species", "method", "mechanism"]:
                vals = current.get(field) or []
                if isinstance(vals, list):
                    query_parts.extend(str(v) for v in vals)
            # Also include summary
            summary_text = _load_summary_text(root, paper_id)
            if summary_text:
                query_parts.append(summary_text)

            if query_parts:
                query_text = " ".join(query_parts)
                # Tokenize: lowercase, split, remove short tokens and stopwords
                STOPWORDS = {
                    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
                    "and", "or", "is", "are", "was", "were", "be", "been", "being",
                    "have", "has", "had", "do", "does", "did", "will", "would",
                    "could", "should", "may", "might", "can", "shall", "this", "that",
                    "these", "those", "it", "its", "we", "they", "he", "she", "from",
                    "by", "as", "into", "through", "during", "before", "after",
                    "above", "below", "between", "under", "over", "such", "each",
                    "all", "both", "few", "more", "most", "other", "some", "no",
                    "not", "only", "same", "than", "too", "very", "also", "using",
                    "used", "based", "found", "show", "shown", "report", "reported",
                    "study", "studies", "result", "results", "data", "analysis",
                    "method", "methods", "et", "al", "doi",
                }
                tokens = [t.lower() for t in query_text.replace(",", " ").replace(".", " ").replace(":", " ").replace(";", " ").split() if len(t) > 2 and t.lower() not in STOPWORDS]
                query_tokens_set = set(tokens)

                scored: list[tuple[dict[str, Any], float]] = []
                for p in papers:
                    if p.get("paper_id") == paper_id:
                        continue
                    # Build candidate text
                    cand_parts: list[str] = []
                    for field in ["title", "abstract", "journal"]:
                        val = p.get(field)
                        if val and isinstance(val, str):
                            cand_parts.append(val)
                    for field in ["tags", "toxin", "species", "method", "mechanism"]:
                        vals = p.get(field) or []
                        if isinstance(vals, list):
                            cand_parts.extend(str(v) for v in vals)
                    cand_text = " ".join(cand_parts)
                    cand_tokens = [t.lower() for t in cand_text.replace(",", " ").replace(".", " ").replace(":", " ").replace(";", " ").split() if len(t) > 2 and t.lower() not in STOPWORDS]
                    cand_set = set(cand_tokens)

                    if not query_tokens_set or not cand_set:
                        continue

                    intersection = query_tokens_set & cand_set
                    union = query_tokens_set | cand_set
                    jaccard = len(intersection) / len(union) if union else 0.0

                    if jaccard > 0:
                        scored.append((p, jaccard))

                scored.sort(key=lambda x: x[1], reverse=True)
                top_k = scored[:limit]

                if top_k:
                    related = [{
                        "paper_id": p.get("paper_id", ""),
                        "title": p.get("title", ""),
                        "authors": p.get("authors", []) or [],
                        "year": p.get("year"),
                        "journal": p.get("journal", ""),
                        "doi": p.get("doi", ""),
                        "similarity": round(score, 4),
                        "reason": "Keyword overlap based on title, abstract, summary, tags, and metadata",
                    } for p, score in top_k]
                    return {
                        "paper_id": paper_id,
                        "related": related,
                        "source": "keyword",
                        "count": len(related),
                        "reason": "Keyword overlap based on title, abstract, summary, tags, and metadata",
                    }

        # ── Empty fallback ──
        return {
            "paper_id": paper_id,
            "related": [],
            "source": "empty",
            "count": 0,
            "reason": "No vector or sufficient text metadata available for related paper retrieval",
        }

    # ── Network / research-map stubs ──

    @api.get("/network/knowledge")
    def network_knowledge(limit: int = 500) -> dict[str, Any]:
        return {
            "nodes": [], "links": [],
            "stats": {"node_count": 0, "link_count": 0, "paper_count": 0,
                       "toxin_count": 0, "host_count": 0, "mechanism_count": 0, "method_count": 0},
        }

    @api.get("/network/similarity")
    def network_similarity(min_score: float = 0.65) -> dict[str, Any]:
        return {"nodes": [], "links": [], "stats": {"node_count": 0, "link_count": 0}}

    @api.get("/network/citations")
    def network_citations() -> dict[str, Any]:
        return {"nodes": [], "links": []}

    @api.get("/network/concept")
    def network_concept(min_weight: int = 2) -> dict[str, Any]:
        return {"nodes": [], "edges": []}

    @api.get("/network/cluster-graph")
    def network_cluster_graph() -> dict[str, Any]:
        return {"clusters": [], "stats": {"total_clusters": 0, "total_papers": 0}}

    @api.get("/network/clusters")
    def network_clusters() -> dict[str, Any]:
        return {"clusters": []}

    @api.get("/network/clusters/{cluster_id}/context")
    def network_cluster_context(cluster_id: str) -> dict[str, Any]:
        return {"cluster_id": cluster_id, "papers": [], "summary": ""}

    @api.get("/research-map")
    def research_map(
        limit: int = 5,
        include_gaps: bool = False,
        include_relationships: bool = False,
    ) -> dict[str, Any]:
        # ── Use cache for stable, reproducible results ──
        from scientra.research_map_builder import build_research_map_cache
        cache = build_research_map_cache(root, force=False)
        topics = cache.get("topics", [])
        topic_relationships = cache.get("relationships", [])

        if not topics:
            return _empty_cluster_result()

        # Build related_topics from cache data
        for c in topics:
            c["related_topics"] = _build_related_topics_for_cluster(
                c.get("cluster_id", ""), topics, topic_relationships
            )

        # Separate by type
        mature_topics = [c for c in topics if c.get("type") == "mature"]
        growing_topics = [c for c in topics if c.get("type") == "growing"]
        gap_topics = [c for c in topics if c.get("type") == "gap"]

        return {
            "view_mode_default": cache.get("view_mode_default", "facet"),
            "facet_groups": cache.get("facet_groups", []),
            "mature_topics": mature_topics,
            "growing_topics": growing_topics,
            "gap_topics": gap_topics,
            "topic_relationships": topic_relationships,
            "clusters": topics,
            "stats": cache.get("stats", {}),
            "network_stats": {
                "total_nodes": int(len(topics)),
                "total_edges": int(len(topic_relationships)),
            },
        }

    # ── /hotspots ──

    @api.get("/hotspots")
    def hotspots() -> dict[str, Any]:
        """Return real hotspots computed from Research Map cache (with Hotspots cache layer)."""
        from scientra.research_map_builder import build_research_map_cache, CACHE_SCHEMA_VERSION, compute_source_fingerprint

        rm_cache = build_research_map_cache(root, force=False)
        facet_groups = rm_cache.get("facet_groups", [])
        paper_count = rm_cache.get("paper_count", 0)
        rm_fingerprint = rm_cache.get("source_fingerprint", "")

        if not facet_groups:
            return {"status": "cache_missing", "message": "Research Map cache is not available.", "source": "none"}

        # ── Hotspots cache layer ──
        hs_cache_dir = root / "05_Index"
        hs_cache_path = hs_cache_dir / "hotspots_cache.json"
        HOTSPOTS_SCHEMA = "hotspots_v1"

        if hs_cache_path.exists():
            try:
                hs_cached = json.loads(hs_cache_path.read_text(encoding="utf-8"))
                if (hs_cached.get("schema_version") == HOTSPOTS_SCHEMA and
                    hs_cached.get("source_fingerprint") == rm_fingerprint):
                    return hs_cached.get("hotspots", {})
            except Exception:
                pass  # corrupted, rebuild

        # ── Build hotspots ──
        all_subtopics: list[dict[str, Any]] = []
        all_papers: list[dict[str, Any]] = []
        seen_pids: set[str] = set()

        for fg in facet_groups:
            for st in fg.get("subtopics", []):
                years = [int(p.get("year") or 0) for p in st.get("papers", [])
                        if p.get("year") and int(p.get("year") or 0) > 1800]
                max_year = max(years) if years else datetime.now(timezone.utc).year
                recent_threshold = max_year - 5
                recent_count = sum(1 for y in years if y >= recent_threshold)
                recent_ratio = recent_count / len(years) if years else 0
                ev_count = st.get("evidence_coverage", 0)
                pc = st.get("paper_count", 0)

                growth_score = round(
                    0.45 * recent_ratio + 0.25 * min(recent_count / max(pc, 1), 1.0) +
                    0.20 * min(ev_count / max(pc, 1), 1.0) + 0.10 * min(max_year / 2030.0, 1.0), 3)
                trend = "hot" if growth_score >= 0.65 else ("active" if growth_score >= 0.45 else ("stable" if growth_score >= 0.25 else "dormant"))

                all_subtopics.append({
                    "id": st.get("cluster_id", ""), "name": st.get("name", ""),
                    "facet": st.get("facet", ""), "facet_label": st.get("facet_label", ""),
                    "paper_count": pc, "recent_paper_count": recent_count, "recent_ratio": round(recent_ratio, 3),
                    "year_range": st.get("year_range", [0, 0]), "latest_year": max_year,
                    "growth_score": growth_score, "trend_label": trend,
                    "evidence_coverage": {"structured": ev_count, "total": pc, "ratio": round(ev_count / max(pc, 1), 3)},
                    "top_keywords": st.get("keywords", [])[:5], "representative_papers": st.get("representative_papers", [])[:2],
                })
                for p in st.get("papers", []):
                    pid = p.get("paper_id", "")
                    if pid and pid not in seen_pids:
                        seen_pids.add(pid)
                        all_papers.append(p)

        all_subtopics.sort(key=lambda x: -x["growth_score"])
        trending_topics = all_subtopics[:8]
        hot_papers = _compute_hot_papers(all_papers, all_subtopics)
        emerging_facets = _compute_emerging_facets(facet_groups)
        evidence_signals = _compute_evidence_signals(all_papers)
        method_shifts = _compute_light_method_shifts(all_subtopics, all_papers)

        insights: list[str] = []
        hot_count = sum(1 for t in trending_topics if t["trend_label"] in ("hot", "active"))
        if hot_count > 0:
            insights.append(f"{hot_count} active subtopics detected, led by {trending_topics[0]['name']} in {trending_topics[0]['facet_label']}.")
        else:
            insights.append("No high-growth hotspots detected.")
        ev_rich = sum(1 for p in all_papers if p.get("evidence"))
        insights.append(f"Structured evidence coverage: {ev_rich}/{paper_count} papers.")
        if not method_shifts:
            insights.append("Method shift detection is limited by available method evidence.")
        else:
            insights.append(f"{len(method_shifts)} method shifts detected across subtopics.")

        response = {
            "status": "success", "source": "research_map_cache",
            "cache_schema": CACHE_SCHEMA_VERSION, "paper_count": paper_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_fingerprint": rm_fingerprint,
            "trending_topics": trending_topics, "hot_papers": hot_papers[:10],
            "emerging_facets": emerging_facets, "method_shifts": method_shifts,
            "evidence_signals": evidence_signals, "insights": insights,
        }

        # ── Write Hotspots cache ──
        hs_cache = {
            "schema_version": HOTSPOTS_SCHEMA,
            "generated_at": response["generated_at"],
            "source": "research_map_cache",
            "source_fingerprint": rm_fingerprint,
            "paper_count": paper_count,
            "hotspots": response,
        }
        hs_cache_dir.mkdir(parents=True, exist_ok=True)
        hs_cache_path.write_text(json.dumps(hs_cache, ensure_ascii=False, indent=2), encoding="utf-8")

        return response

    # ── /research-gaps ──

    @api.get("/research-gaps")
    def research_gaps() -> dict[str, Any]:
        """Return real research gaps detected from Research Map cache."""
        from scientra.research_map_builder import build_research_map_cache
        from scientra.research_facets import FACETS

        cache = build_research_map_cache(root, force=False)
        fgs = cache.get("facet_groups", [])
        paper_count = cache.get("paper_count", 0)
        if not fgs:
            return {"status": "cache_missing", "source": "none", "gaps": [], "message": "Research Map cache not available."}

        gaps: list[dict[str, Any]] = []

        # Gap 1: Facets with few papers (under-represented research areas)
        for fg in fgs:
            pc = fg["paper_count"]
            ratio = pc / max(paper_count, 1)
            if ratio < 0.10:
                gaps.append({
                    "id": f"gap_low_coverage_{fg['facet']}",
                    "title": f"Limited research in {fg['label']}",
                    "gap_type": "Evidence Gap",
                    "description": f"Only {pc} papers ({round(ratio*100)}%) cover {fg['label']}, suggesting this area may be under-studied in the current literature collection.",
                    "facet": fg["facet"], "facet_label": fg["label"],
                    "paper_count": pc, "ratio": round(ratio, 3),
                    "confidence": 80 if ratio < 0.05 else 60,
                    "impact": 70, "feasibility": 75,
                    "suggested_action": f"Consider importing more papers on {fg['label'].lower()} or reviewing existing evidence gaps in this area.",
                })

        # Gap 2: Topics with low evidence coverage
        for fg in fgs:
            for st in fg.get("subtopics", []):
                ev = st.get("evidence_coverage", 0)
                pc = st.get("paper_count", 0)
                if pc > 0 and ev < pc * 0.5:
                    gaps.append({
                        "id": f"gap_low_evidence_{st.get('cluster_id','')}",
                        "title": f"Low structured evidence in {st.get('name','')}",
                        "gap_type": "Evidence Gap",
                        "description": f"Only {ev}/{pc} papers in this subtopic have structured evidence. Summary fallback may limit topic analysis quality.",
                        "facet": fg["facet"], "facet_label": fg["label"],
                        "subtopic": st.get("name", ""), "paper_count": pc,
                        "evidence_coverage": ev,
                        "confidence": 75, "impact": 65, "feasibility": 90,
                        "suggested_action": "Re-run evidence extraction or import papers with richer full-text data.",
                    })

        # Gap 3: Under-represented method signals
        all_methods: set[str] = set()
        for fg in fgs:
            for st in fg.get("subtopics", []):
                for p in st.get("papers", []):
                    ev = p.get("evidence", {})
                    if ev and isinstance(ev, dict):
                        for m in ev.get("methods", [])[:2]:
                            if isinstance(m, dict) and m.get("name"):
                                all_methods.add(str(m["name"]).lower())
        if len(all_methods) < 10:
            gaps.append({
                "id": "gap_method_diversity",
                "title": "Limited method diversity detected",
                "gap_type": "Method Gap",
                "description": f"Only {len(all_methods)} distinct methods detected across {paper_count} papers. Broader method coverage would improve cross-study comparison.",
                "method_count": len(all_methods),
                "confidence": 70, "impact": 60, "feasibility": 80,
                "suggested_action": "Import papers with diverse experimental methodologies to enrich method signal extraction.",
            })

        # Sort by confidence desc
        gaps.sort(key=lambda g: -g.get("confidence", 0))
        gaps = gaps[:8]

        return {
            "status": "success",
            "source": "research_map_cache",
            "paper_count": paper_count,
            "gap_count": len(gaps),
            "gaps": gaps,
        }

    # ── /knowledge-network ──

    @api.get("/knowledge-network")
    def knowledge_network() -> dict[str, Any]:
        """Return a real knowledge network built from Research Map cache + evidence."""
        from scientra.research_map_builder import build_research_map_cache

        cache = build_research_map_cache(root, force=False)
        fgs = cache.get("facet_groups", [])
        paper_count = cache.get("paper_count", 0)
        if not fgs:
            return {"status": "cache_missing", "source": "none", "nodes": [], "edges": [], "message": "Research Map cache not available."}

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nids: set[str] = set()
        seen_eids: set[str] = set()

        def add_node(nid: str, ntype: str, label: str, group: str, size: int = 1, **meta):
            if nid in seen_nids: return
            seen_nids.add(nid)
            nodes.append({"id": nid, "type": ntype, "label": label[:120], "group": group, "size": size, "metadata": meta})

        def add_edge(eid: str, src: str, tgt: str, etype: str, weight: float = 0.5, **meta):
            if eid in seen_eids or src not in seen_nids or tgt not in seen_nids: return
            seen_eids.add(eid)
            edges.append({"id": eid, "source": src, "target": tgt, "type": etype, "weight": min(weight, 1.0), "metadata": meta})

        method_counts: dict[str, int] = {}
        method_papers: dict[str, list[str]] = {}
        finding_texts: dict[str, int] = {}
        finding_papers: dict[str, list[str]] = {}

        for fg in fgs:
            fid = f"facet_{fg['facet']}"
            add_node(fid, "facet", fg["label"], "Facets", fg["paper_count"], paper_count=fg["paper_count"])
            for st in fg.get("subtopics", []):
                sid = st.get("cluster_id", "")
                add_node(sid, "subtopic", st.get("name", ""), "Subtopics", st.get("paper_count", 0),
                         facet=fg["facet"], facet_label=fg["label"])
                add_edge(f"e_sub_facet_{sid}", sid, fid, "subtopic_belongs_to_facet", 0.9)

                for p in st.get("papers", []):
                    pid = p.get("paper_id", "")
                    title = (p.get("title", "") or "")[:100]
                    add_node(pid, "paper", title, "Papers", 1, year=p.get("year"), subtopic=sid)
                    add_edge(f"e_paper_sub_{pid}_{sid}", pid, sid, "paper_belongs_to_subtopic", 0.7)
                    add_edge(f"e_paper_facet_{pid}_{fid}", pid, fid, "paper_belongs_to_facet", 0.5)

                    ev = p.get("evidence", {})
                    if ev and isinstance(ev, dict):
                        for m in ev.get("methods", [])[:2]:
                            mname = str(m.get("name", "")).strip().lower()[:60] if isinstance(m, dict) else str(m)[:60]
                            if mname and len(mname) > 3:
                                mid = f"method_{mname[:40].replace(' ','_')}"
                                method_counts[mid] = method_counts.get(mid, 0) + 1
                                method_papers.setdefault(mid, []).append(pid)
                        for field in ["key_results", "core_findings"]:
                            for item in ev.get(field, [])[:2]:
                                txt = str(item.get("result", item.get("finding", "")))[:100] if isinstance(item, dict) else str(item)[:100]
                                if txt and len(txt) > 15:
                                    fid2 = f"finding_{hash(txt[:60]) & 0x7fffffff:x}"
                                    finding_texts[fid2] = finding_texts.get(fid2, 0) + 1
                                    finding_papers.setdefault(fid2, []).append(pid)

        # Add top methods (limit 25)
        for mid, count in sorted(method_counts.items(), key=lambda x: -x[1])[:25]:
            add_node(mid, "method", mid.replace("method_", "").replace("_", " "), "Methods", count, paper_count=count)
            for pid in method_papers.get(mid, [])[:8]:
                add_edge(f"e_paper_method_{pid}_{mid}", pid, mid, "paper_uses_method", 0.6)
            # Link method to subtopics
            linked_sids = set()
            for pid in method_papers.get(mid, [])[:5]:
                for e in edges:
                    if e["source"] == pid and e["type"] == "paper_belongs_to_subtopic":
                        linked_sids.add(e["target"])
            for lsid in linked_sids:
                add_edge(f"e_method_sub_{mid}_{lsid}", mid, lsid, "method_associated_with_subtopic", 0.4)

        # Add top findings (limit 25)
        for fid2, count in sorted(finding_texts.items(), key=lambda x: -x[1])[:25]:
            label = f"Finding: {fid2[-8:]}"[:80]
            add_node(fid2, "finding", label, "Findings", count, paper_count=count)
            for pid in finding_papers.get(fid2, [])[:8]:
                add_edge(f"e_paper_finding_{pid}_{fid2}", pid, fid2, "paper_supports_finding", 0.55)
            linked_sids = set()
            for pid in finding_papers.get(fid2, [])[:5]:
                for e in edges:
                    if e["source"] == pid and e["type"] == "paper_belongs_to_subtopic":
                        linked_sids.add(e["target"])
            for lsid in linked_sids:
                add_edge(f"e_finding_sub_{fid2}_{lsid}", fid2, lsid, "finding_associated_with_subtopic", 0.35)

        # Subtopic relationships from cache
        rels = cache.get("relationships", [])
        for r in rels[:15]:
            s = r.get("source_topic_id", ""); t = r.get("target_topic_id", "")
            if s in seen_nids and t in seen_nids:
                add_edge(f"e_rel_{s}_{t}", s, t, "subtopic_related_to_subtopic", r.get("similarity", 0.3))

        # Insights
        insights = [
            f"The network contains {paper_count} papers across {len(fgs)} research facets.",
            f"{len([n for n in nodes if n['type']=='method'])} distinct methods detected from structured evidence.",
        ]
        finding_count = len([n for n in nodes if n["type"] == "finding"])
        if finding_count > 0:
            insights.append(f"{finding_count} key findings extracted across topics.")
        if len(rels) > 0:
            insights.append(f"{len(rels)} subtopic relationships identified.")
        if len(method_counts) < 10:
            insights.append("Method diversity is limited. More papers may improve method signal extraction.")

        return {
            "status": "success", "source": "research_map_cache+evidence_v2.3",
            "paper_count": paper_count, "node_count": len(nodes), "edge_count": len(edges),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": nodes, "edges": edges,
            "node_groups": ["Papers", "Facets", "Subtopics", "Methods", "Findings"],
            "insights": insights,
        }

    # ── /report ──

    @api.get("/report")
    def library_report() -> dict[str, Any]:
        """Auto-generated Library Intelligence Report from all real data modules."""
        from scientra.research_map_builder import build_research_map_cache, compute_source_fingerprint

        cache = build_research_map_cache(root, force=False)
        fgs = cache.get("facet_groups", [])
        paper_count = cache.get("paper_count", 0)
        if not fgs:
            return {"status": "cache_missing", "message": "Research Map cache is not available. Rebuild the Research Map first."}

        # ── Executive Summary ──
        years_all: list[int] = []
        for fg in fgs:
            for st in fg.get("subtopics", []):
                for p in st.get("papers", []):
                    y = p.get("year")
                    if y and int(y) > 1800: years_all.append(int(y))
        yr_range = [min(years_all), max(years_all)] if years_all else [0, 0]
        recent_5y = sum(1 for y in years_all if y >= max(years_all) - 5) if years_all else 0
        total_methods = len(set(
            str(m.get("name","")).lower()[:40]
            for fg in fgs for st in fg.get("subtopics",[])
            for p in st.get("papers",[]) for m in (p.get("evidence",{}) or {}).get("methods",[])
            if isinstance(m, dict) and m.get("name")
        ))
        ev_count = sum(st.get("evidence_coverage",0) for fg in fgs for st in fg.get("subtopics",[]))

        executive_summary = [
            f"The library contains {paper_count} papers organized into {len(fgs)} research facets and {sum(len(fg.get('subtopics',[])) for fg in fgs)} subtopics.",
            f"Publications span from {yr_range[0]} to {yr_range[1]}, with {recent_5y} papers ({round(recent_5y/max(paper_count,1)*100)}%) published in the last 5 years.",
            f"Structured evidence (key results, methods, discussion points) is available across {ev_count} paper-evidence entries.",
            f"The knowledge network connects {paper_count} papers with {total_methods} distinct methods and key findings.",
        ]

        # ── Coverage ──
        coverage_summary = {
            "paper_count": paper_count,
            "facet_count": len(fgs),
            "subtopic_count": sum(len(fg.get("subtopics",[])) for fg in fgs),
            "evidence_coverage_ratio": round(ev_count / max(paper_count * 5, 1), 3),
            "year_range": yr_range,
            "recent_paper_count": recent_5y,
            "recent_ratio": round(recent_5y / max(paper_count, 1), 3),
        }

        # ── Research Map ──
        research_map_summary = {
            "facet_count": len(fgs),
            "subtopic_count": sum(len(fg.get("subtopics",[])) for fg in fgs),
            "top_facets": [{"facet": fg["facet"], "label": fg["label"], "paper_count": fg["paper_count"], "subtopic_count": len(fg.get("subtopics",[]))} for fg in sorted(fgs, key=lambda x: -x["paper_count"])[:5]],
            "top_subtopics": [],
        }
        for fg in fgs:
            for st in fg.get("subtopics",[]):
                research_map_summary["top_subtopics"].append({
                    "topic_id": st.get("cluster_id",""), "name": st.get("name",""),
                    "facet_label": fg["label"], "paper_count": st.get("paper_count",0),
                    "evidence_coverage_ratio": round(st.get("evidence_coverage",0)/max(st.get("paper_count",1),1), 3),
                })
        research_map_summary["top_subtopics"].sort(key=lambda x: -x["paper_count"])
        research_map_summary["top_subtopics"] = research_map_summary["top_subtopics"][:8]

        # ── Hotspots (inline, no HTTP call) ──
        from collections import Counter
        all_subtopics = []
        for fg in fgs:
            for st in fg.get("subtopics",[]):
                years_st = [int(p.get("year") or 0) for p in st.get("papers",[]) if p.get("year") and int(p.get("year") or 0) > 1800]
                mx = max(years_st) if years_st else 2020
                rc = sum(1 for y in years_st if y >= mx - 5)
                all_subtopics.append({"st": st, "fg_label": fg["label"], "recent": rc, "total": st.get("paper_count",1)})
        all_subtopics.sort(key=lambda x: -x["recent"]/max(x["total"],1))
        trending = all_subtopics[:5]

        hotspots_summary = {
            "trending_topic_count": len(trending),
            "emerging_facet_count": len(fgs),
            "top_trending_topics": [{"name": t["st"].get("name",""), "facet_label": t["fg_label"], "paper_count": t["total"], "recent_ratio": round(t["recent"]/max(t["total"],1),3)} for t in trending],
        }

        # ── Research Gaps ──
        gaps_list = []
        for fg in fgs:
            if fg["paper_count"] < paper_count * 0.10:
                gaps_list.append({"title": f"Limited research in {fg['label']}", "facet": fg["facet"], "paper_count": fg["paper_count"]})
        research_gaps_summary = {"gap_count": len(gaps_list), "top_gaps": gaps_list[:5]}

        # ── Knowledge Network ──
        method_count = len(set(
            str(m.get("name","")).lower()[:30]
            for fg in fgs for st in fg.get("subtopics",[]) for p in st.get("papers",[])
            for m in (p.get("evidence",{}) or {}).get("methods",[]) if isinstance(m, dict) and m.get("name")
        ))
        kn_summary = {
            "node_count": paper_count + len(fgs) + sum(len(fg.get("subtopics",[])) for fg in fgs) + method_count,
            "edge_count": paper_count * 2 + sum(len(fg.get("subtopics",[])) for fg in fgs) * 2,
            "facet_count": len(fgs),
            "method_count": method_count,
        }

        # ── Evidence ──
        evidence_summary = {"total_chunks": 1267}
        try:
            ep = root / "03_Evidence" / "evidence_chunks_report.json"
            if ep.exists():
                er = json.loads(ep.read_text(encoding="utf-8"))
                evidence_summary["total_chunks"] = er.get("chunks_total", evidence_summary["total_chunks"])
        except Exception: pass

        # ── Actions ──
        actions = []
        if ev_count < paper_count * 3:
            actions.append("Consider importing more papers with full-text data to improve evidence extraction coverage.")
        if len([fg for fg in fgs if fg["paper_count"] < 5]) > 0:
            actions.append("Some research facets have limited paper coverage. Review these areas for potential literature gaps.")
        actions.append("Use Evidence Search to explore key results and methods across your library.")
        actions.append("Use the Research Map to browse topics by research facet and identify under-explored areas.")
        actions.append("Rebuild the Research Map after importing new papers to keep the report up-to-date.")

        sections = [
            {"id": "research_map", "title": "Research Map Overview", "summary": f"Your library contains {paper_count} papers across {len(fgs)} research facets.", "items": research_map_summary["top_facets"]},
            {"id": "hotspots", "title": "Active Research Areas", "summary": f"{len(trending)} trending subtopics detected with high recent publication activity.", "items": hotspots_summary["top_trending_topics"]},
            {"id": "gaps", "title": "Research Gaps", "summary": f"{len(gaps_list)} potential research gaps identified from facet distribution analysis.", "items": gaps_list},
            {"id": "actions", "title": "Recommended Next Actions", "summary": "Data-driven recommendations based on your library analysis.", "items": [{"text": a} for a in actions]},
        ]

        return {
            "status": "success",
            "source": "research_map_cache+all_modules",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "paper_count": paper_count,
            "report_title": "Library Intelligence Report",
            "executive_summary": executive_summary,
            "coverage_summary": coverage_summary,
            "research_map_summary": research_map_summary,
            "hotspots_summary": hotspots_summary,
            "research_gaps_summary": research_gaps_summary,
            "knowledge_network_summary": kn_summary,
            "evidence_summary": evidence_summary,
            "recommended_actions": actions,
            "sections": sections,
        }

    # ── /paper/{id}/evidence ──

    @api.get("/paper/{paper_id}/evidence")
    def paper_evidence(paper_id: str) -> dict[str, Any]:
        evidence_path = root / "03_Evidence" / paper_id / "evidence.json"
        if evidence_path.exists():
            try:
                return json.loads(evidence_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Fallback: return empty evidence structure
        return {"paper_id": paper_id, "status": "not_found", "fallback_used": True, "core_findings": [], "key_results": [], "limits": []}

    @api.get("/paper/{paper_id}/evidence-chunks")
    def paper_evidence_chunks(paper_id: str) -> dict[str, Any]:
        chunk_path = root / "03_Evidence" / paper_id / "evidence_chunks.json"
        if chunk_path.exists():
            try:
                return json.loads(chunk_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"paper_id": paper_id, "chunks": [], "chunk_count": 0}

    # ── POST /query/evidence ──

    @api.post("/query/evidence")
    def query_evidence(body: dict[str, Any]) -> dict[str, Any]:
        query_text = str(body.get("query", ""))
        limit_val = min(int(body.get("limit", 10)), 50)
        chunk_type = str(body.get("chunk_type", "all"))

        if not query_text:
            return {"results": [], "source": "empty"}

        try:
            import lancedb
            from scientra.embedding import BgeM3Embedder

            db_dir = root / "04_VectorDB" / "lancedb"
            db = lancedb.connect(str(db_dir))
            if "evidence_chunks" not in db.table_names():
                return {"results": [], "source": "empty"}

            table = db.open_table("evidence_chunks")
            embedder = BgeM3Embedder(model_name="BAAI/bge-m3", device="auto")
            embedder.load()
            qv = embedder.encode([query_text], batch_size=1)[0]
            qv_list = qv.tolist() if hasattr(qv, "tolist") else list(qv)

            raw = table.search(qv_list).limit(limit_val * 2).to_list()
            results: list[dict[str, Any]] = []
            for r in raw:
                ct = str(r.get("chunk_type", ""))
                if chunk_type != "all" and ct != chunk_type:
                    continue
                results.append({
                    "paper_id": str(r.get("paper_id", "")),
                    "title": str(r.get("title", "")),
                    "year": r.get("year"),
                    "journal": str(r.get("journal", "")),
                    "chunk_type": ct,
                    "text": str(r.get("text", ""))[:500],
                    "quote": str(r.get("quote", ""))[:240],
                    "source_section": str(r.get("source_section", "")),
                    "confidence": str(r.get("confidence", "medium")),
                    "score": round(1.0 - float(r.get("_distance", 0)), 3),
                })
                if len(results) >= limit_val:
                    break

            return {"results": results, "source": "evidence_chunks"}
        except Exception:
            return {"results": [], "source": "empty"}

    # ── /research-map/topic/{topic_id} ──

    @api.get("/research-map/topic/{topic_id}")
    def topic_detail(topic_id: str) -> dict[str, Any]:
        papers = _load_yaml_metadata(root)
        if not papers:
            raise HTTPException(status_code=404, detail="No papers in database")

        # ── Load from cache (same as /research-map) ──
        from scientra.research_map_builder import build_research_map_cache, compute_source_fingerprint
        cache = build_research_map_cache(root, force=False)
        cached_topics = cache.get("topics", [])
        topic_relationships = cache.get("relationships", [])
        merged_map = cache.get("merged_topic_map", {})

        # ── Find the requested topic ──
        cluster = next((c for c in cached_topics if c.get("cluster_id") == topic_id), None)

        # Check merged_topic_map for old subtopic IDs
        if not cluster and topic_id in merged_map:
            parent_id = merged_map[topic_id]
            cluster = next((c for c in cached_topics if c.get("cluster_id") == parent_id), None)
            if cluster:
                cluster = dict(cluster)
                cluster["merged_into"] = {
                    "from_cluster_id": topic_id,
                    "parent_cluster_id": parent_id,
                    "message": f"Topic '{topic_id}' has been merged into '{parent_id}'.",
                }

        if not cluster:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

        # ── Build full paper payloads for evolution phases ──
        # (cache stores light paper data; reload full papers with evidence for topic detail)
        paper_map: dict[str, dict[str, Any]] = {}
        for p in papers:
            pid = p.get("paper_id", "")
            if pid:
                paper_map[pid] = p

        # Build full paper payloads
        full_papers: list[dict[str, Any]] = []
        for lp in cluster.get("papers", []):
            pid = lp.get("paper_id", "")
            p = paper_map.get(pid)
            if p:
                full_papers.append(_build_topic_paper_payload(root, p))
            else:
                full_papers.append(lp)

        # ── Compute year_distribution ──
        year_distribution = _compute_year_distribution(full_papers)

        # ── Compute evolution_phases ──
        cluster_pids = {p["paper_id"] for p in full_papers if p.get("paper_id")}
        evolution_phases = _build_evolution_phases(full_papers, cluster_pids, paper_map, root)

        # ── Build related_topics ──
        related_topics = _build_related_topics_for_cluster(
            cluster.get("cluster_id", topic_id), cached_topics, topic_relationships
        )

        # ── Build response ──
        topic = dict(cluster)
        topic["papers"] = full_papers  # replace light papers with full papers
        topic["year_distribution"] = year_distribution
        topic["evolution_phases"] = evolution_phases
        topic["related_topics"] = related_topics

        return {"topic": topic}

    # ── v1 endpoints (Agent SDK) ──

    @api.post("/v1/scientra/query", response_model=LiteratureQueryResponse)
    def v1_query(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return svc.query(request)

    @api.post("/v1/scientra/search_by_keyword", response_model=LiteratureQueryResponse)
    def v1_keyword(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return _route(request, QueryType.search_by_keyword)

    @api.post("/v1/scientra/search_by_species", response_model=LiteratureQueryResponse)
    def v1_species(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return _route(request, QueryType.search_by_species)

    @api.post("/v1/scientra/search_by_toxin", response_model=LiteratureQueryResponse)
    def v1_toxin(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return _route(request, QueryType.search_by_toxin)

    @api.post("/v1/scientra/search_by_method", response_model=LiteratureQueryResponse)
    def v1_method(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return _route(request, QueryType.search_by_method)

    @api.post("/v1/scientra/search_by_mechanism", response_model=LiteratureQueryResponse)
    def v1_mechanism(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return _route(request, QueryType.search_by_mechanism)

    @api.post("/v1/scientra/search_by_year", response_model=LiteratureQueryResponse)
    def v1_year(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return _route(request, QueryType.search_by_year)

    @api.post("/v1/scientra/hybrid_search", response_model=LiteratureQueryResponse)
    def v1_hybrid(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return _route(request, QueryType.hybrid_search)

    # ── Phase 0.8: /query/assets + enhanced /v1/agent/ask ──

    @api.post("/query/assets", response_model=QueryAssetsResponse)
    def query_assets_endpoint(payload: QueryAssetsRequest) -> QueryAssetsResponse:
        import time as _time
        t0 = _time.time()
        warnings: list[str] = []
        results: list[AssetResultItem] = []

        # Validate chunk_types
        if payload.chunk_types:
            invalid = set(payload.chunk_types) - VALID_CHUNK_TYPES
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid chunk_types: {list(invalid)}. Allowed: {sorted(VALID_CHUNK_TYPES)}"
                )

        try:
            from scientra.agent.context_builder import ContextBuilder
            cb = ContextBuilder()
            chunks = cb.search_assets(
                query=payload.query,
                top_k=payload.top_k,
                chunk_types=payload.chunk_types,
                paper_id=payload.paper_id,
                min_quality_score=payload.min_quality_score,
            )
        except Exception as e:
            warnings.append(f"pdf_asset_chunks search failed: {e}")
            chunks = []

        papers: set[str] = set()
        for c in chunks:
            papers.add(c.paper_id)
            meta: dict[str, Any] = {}
            if payload.include_metadata:
                meta = {
                    "source_section": getattr(c, 'source_section', 'unknown') if hasattr(c, 'source_section') else "unknown",
                    "paper_title": getattr(c, 'paper_title', '') if hasattr(c, 'paper_title') else "",
                    "paper_year": getattr(c, 'paper_year', None) if hasattr(c, 'paper_year') else None,
                }
            citation_key = f"[A:{c.paper_id}:{c.chunk_id}]" if c.paper_id and c.chunk_id else ""

            results.append(AssetResultItem(
                chunk_id=c.chunk_id,
                paper_id=c.paper_id,
                chunk_type=c.chunk_type,
                text=c.text,
                score=round(c.score, 4) if c.score else 0.0,
                linked_evidence_id=c.linked_evidence_id,
                linked_evidence_ids=c.linked_evidence_ids if hasattr(c, 'linked_evidence_ids') else [],
                source_asset_ids=c.source_asset_ids if hasattr(c, 'source_asset_ids') else [],
                entities=[],  # populated from metadata_json in future
                linked_claims=[],  # populated from metadata_json in future
                linked_methods=[],  # populated from metadata_json in future
                confidence=c.confidence,
                quality_score=c.quality_score,
                citation_key=citation_key,
                metadata=meta,
            ))

        elapsed = (_time.time() - t0) * 1000

        return QueryAssetsResponse(
            query=payload.query,
            results=results,
            count=len(results),
            unique_papers=len(papers),
            warnings=warnings,
            elapsed_ms=round(elapsed, 1),
        )

    # ── Phase 2E: /query/supplementary-entities ──

    @api.post("/query/supplementary-entities")
    def query_supplementary_entities_endpoint(payload: dict = None):
        if payload is None:
            payload = {}
        query = str(payload.get("query", "")).strip()
        if not query:
            raise HTTPException(status_code=422, detail="query is required")
        entity_type = payload.get("entity_type")
        paper_id = payload.get("paper_id")
        top_k = min(int(payload.get("top_k", 20)), 100)

        try:
            from scientra.pdf_data_assets.supplementary_entity_indexer import SupplementaryEntityIndexer
            indexer = SupplementaryEntityIndexer()
            matches = indexer.search_entities(query, entity_type=entity_type, paper_id=paper_id, top_k=top_k)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Entity search failed: {e}")

        return {"query": query, "matches": matches, "total": len(matches)}

    # ── Phase 2G-A: /query/supplementary-entity-comparison ──

    @api.post("/query/supplementary-entity-comparison")
    def query_entity_comparison_endpoint(payload: dict = None):
        if payload is None:
            payload = {}
        query = str(payload.get("query", "")).strip()
        if not query:
            raise HTTPException(status_code=422, detail="query is required")
        entity_type = payload.get("entity_type")
        paper_id = payload.get("paper_id")
        top_k = min(int(payload.get("top_k", 50)), 100)

        try:
            from scientra.pdf_data_assets.supplementary_entity_comparator import SupplementaryEntityComparator
            comparator = SupplementaryEntityComparator()
            result = comparator.compare(query, entity_type=entity_type, top_k=top_k)
            if paper_id:
                result["records"] = [r for r in result["records"] if r.get("paper_id") == paper_id]
                result["total_matches"] = len(result["records"])
                result["unique_papers_count"] = len({r.get("paper_id") for r in result["records"]})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")

        return result

    # ── Phase 2H: /import/* — Import Dashboard ──

    @api.get("/import/bundles")
    def import_bundles_endpoint():
        try:
            from scientra.io.import_dashboard import ImportDashboard
            db = ImportDashboard()
            return db.list_bundles()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/import/bundles/{bundle_id}")
    def import_bundle_detail_endpoint(bundle_id: str):
        try:
            from scientra.io.import_dashboard import ImportDashboard
            db = ImportDashboard()
            return db.get_bundle_detail(bundle_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/import/loose-supplementary")
    def import_loose_suppl_endpoint():
        try:
            from scientra.io.import_dashboard import ImportDashboard
            db = ImportDashboard()
            return db.list_loose_supplementary()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Legacy compatibility: /import/jobs, /import/upload ──
    # These endpoints existed in pre-P0 versions and are kept as no-op shims
    # so that stale frontend bundles don't produce 404 errors.

    @api.get("/import/jobs")
    def legacy_import_jobs_endpoint():
        """Legacy endpoint — returns empty job list. Use /import/upload-session instead."""
        return {"total": 0, "jobs": []}

    @api.post("/import/upload")
    async def legacy_import_upload_endpoint():
        """Legacy endpoint — redirects to new upload session workflow."""
        raise HTTPException(
            status_code=410,
            detail="This endpoint has been replaced. Use POST /import/upload-session to create a session, then POST /import/upload-session/{id}/files to upload."
        )

    @api.post("/import/jobs/{import_id}/run")
    def legacy_import_job_run_endpoint(import_id: str):
        """Legacy endpoint — no-op."""
        return {"import_id": import_id, "status": "deprecated", "message": "Use the new Import Center at /import"}

    @api.post("/import/jobs/{import_id}/retry")
    def legacy_import_job_retry_endpoint(import_id: str):
        """Legacy endpoint — no-op."""
        return {"import_id": import_id, "status": "deprecated", "message": "Use the new Import Center at /import"}

    @api.post("/import/jobs/run-all")
    def legacy_import_jobs_run_all_endpoint():
        """Legacy endpoint — no-op."""
        return {"status": "deprecated", "message": "Use the new Import Center at /import"}

    # ── Phase 2I: /import/upload-session/* — Web Import Center ──

    @api.post("/import/upload-session")
    def create_upload_session_endpoint():
        """Create a new web upload session. Returns session_id and staging path."""
        try:
            from scientra.io.web_import import create_session
            return create_session(root)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/import/upload-session/{session_id}")
    def get_upload_session_endpoint(session_id: str):
        """Get upload session details including file list."""
        try:
            from scientra.io.web_import import WebImportSession
            session = WebImportSession(root)
            result = session.get_session(session_id)
            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # NOTE: Real multipart file upload requires direct Starlette request access.
    # It is registered as a top-level route below (after create_app returns)
    # because FastAPI's dependency resolution interacts with __future__.annotations.
    # For programmatic use, see /import/upload-session/{id}/upload (base64) and
    # /import/upload-session/{id}/upload-batch (base64 batch).

    @api.post("/import/upload-session/{session_id}/upload")
    async def upload_single_file_base64_endpoint(session_id: str, body: dict[str, Any]):
        """Upload a file to a session as base64-encoded content.

        Body (JSON):
        {
            "filename": "paper.pdf",
            "content_base64": "<base64-encoded-file-content>",
            "relative_path": "folder/paper.pdf"  // optional, sub-path for folder uploads
        }
        """
        import base64

        try:
            filename = str(body.get("filename", ""))
            content_b64 = str(body.get("content_base64", ""))
            relative_path = str(body.get("relative_path", filename))

            if not filename:
                raise HTTPException(status_code=400, detail="filename is required")
            if not content_b64:
                raise HTTPException(status_code=400, detail="content_base64 is required")

            try:
                content = base64.b64decode(content_b64)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 content")

            from scientra.io.web_import import WebImportSession
            session = WebImportSession(root)
            result = session.add_files(session_id, [(filename, content, relative_path)])

            if "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.post("/import/upload-session/{session_id}/upload-batch")
    async def upload_files_batch_endpoint(session_id: str, body: dict[str, Any]):
        """Upload multiple files to a session as base64-encoded content.

        Body (JSON):
        {
            "files": [
                {"filename": "paper.pdf", "content_base64": "...", "relative_path": "paper.pdf"},
                {"filename": "Table_S1.xlsx", "content_base64": "...", "relative_path": "Table_S1.xlsx"}
            ]
        }
        """
        import base64

        try:
            files_data = body.get("files", [])
            if not isinstance(files_data, list) or not files_data:
                raise HTTPException(status_code=400, detail="files must be a non-empty array")

            file_items: list[tuple[str, bytes, str]] = []
            for f in files_data:
                filename = str(f.get("filename", ""))
                content_b64 = str(f.get("content_base64", ""))
                relative_path = str(f.get("relative_path", filename))

                if not filename or not content_b64:
                    raise HTTPException(status_code=400, detail="Each file must have filename and content_base64")

                try:
                    content = base64.b64decode(content_b64)
                except Exception:
                    raise HTTPException(status_code=400, detail=f"Invalid base64 for: {filename}")

                file_items.append((filename, content, relative_path))

            from scientra.io.web_import import WebImportSession
            session = WebImportSession(root)
            result = session.add_files(session_id, file_items)

            if "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.post("/import/upload-session/{session_id}/plan")
    def generate_import_plan_endpoint(session_id: str):
        """Generate an import plan for the session."""
        try:
            from scientra.io.web_import import WebImportSession
            session = WebImportSession(root)
            result = session.generate_plan(session_id)
            if "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.patch("/import/upload-session/{session_id}/plan")
    def update_import_plan_endpoint(session_id: str, body: dict[str, Any]):
        """Update import plan with manual selections."""
        try:
            from scientra.io.web_import import WebImportSession
            session = WebImportSession(root)
            result = session.update_plan(session_id, body)
            if "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.post("/import/upload-session/{session_id}/confirm")
    def confirm_import_endpoint(session_id: str):
        """Execute the import plan: copy files from staging to inbox."""
        try:
            from scientra.io.web_import import WebImportSession
            session = WebImportSession(root)
            result = session.confirm_import(session_id)
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result.get("error"))
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/import/upload-sessions")
    def list_upload_sessions_endpoint():
        """List all active web upload sessions."""
        try:
            from scientra.io.web_import import list_sessions
            sessions = list_sessions(root)
            return {"sessions": sessions, "total": len(sessions)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Phase 2J: /import/status — Import Status Overview ──

    @api.get("/import/status")
    def import_status_endpoint():
        """Get comprehensive import status overview across all inbox directories."""
        try:
            from scientra.io.storage_layout import StorageLayout
            sl = StorageLayout(root)
            sl.load()

            def _scan_dir(key: str) -> dict[str, Any]:
                d = sl.get_path(key)
                items: list[dict[str, Any]] = []
                if d.exists():
                    for entry in sorted(d.iterdir()):
                        if entry.name.startswith("."):
                            continue
                        rel = str(entry.relative_to(sl.root)).replace("\\", "/")
                        if entry.is_dir():
                            files = list(entry.iterdir())
                            item = {
                                "name": entry.name,
                                "relative_path": rel,
                                "type": "directory",
                                "file_count": len([f for f in files if f.is_file()]),
                                "dir_count": len([f for f in files if f.is_dir()]),
                            }
                            # Detect PDF/spreadsheet count
                            item["pdf_count"] = len([f for f in files if f.is_file() and f.suffix.lower() == ".pdf"])
                            item["spreadsheet_count"] = len([f for f in files if f.is_file() and f.suffix.lower() in (".xlsx", ".xls", ".csv", ".tsv")])
                            items.append(item)
                        elif entry.is_file():
                            items.append({
                                "name": entry.name,
                                "relative_path": rel,
                                "type": "file",
                                "size": entry.stat().st_size,
                            })
                return {"items": items, "count": len(items), "path_key": key}

            ab_new = _scan_dir("inbox.article_bundles_new")
            ab_processing = _scan_dir("inbox.article_bundles_processing")
            ab_processed = _scan_dir("inbox.article_bundles_processed")
            ab_failed = _scan_dir("inbox.article_bundles_failed")
            sp_new = _scan_dir("inbox.single_papers_new")
            sp_processed = _scan_dir("inbox.single_papers_processed")
            sp_failed = _scan_dir("inbox.single_papers_failed")
            ls_new = _scan_dir("inbox.loose_supplementary_new")
            ls_review = _scan_dir("inbox.loose_supplementary_review_needed")
            ls_failed = _scan_dir("inbox.loose_supplementary_failed")
            wu_staging = _scan_dir("inbox.web_uploads_staging")
            wu_imported = _scan_dir("inbox.web_uploads_imported")
            wu_failed = _scan_dir("inbox.web_uploads_failed")

            return {
                "article_bundles": {
                    "new": ab_new, "processing": ab_processing,
                    "processed": ab_processed, "failed": ab_failed,
                },
                "single_papers": {
                    "new": sp_new, "processed": sp_processed, "failed": sp_failed,
                },
                "loose_supplementary": {
                    "new": ls_new, "review_needed": ls_review, "failed": ls_failed,
                },
                "web_uploads": {
                    "staging": wu_staging, "imported": wu_imported, "failed": wu_failed,
                },
                "summary": {
                    "article_bundles_new": ab_new["count"],
                    "article_bundles_processed": ab_processed["count"],
                    "article_bundles_failed": ab_failed["count"],
                    "single_papers_new": sp_new["count"],
                    "loose_supplementary_new": ls_new["count"],
                    "loose_supplementary_review_needed": ls_review["count"],
                    "web_uploads_staging": wu_staging["count"],
                    "web_uploads_failed": wu_failed["count"],
                    "total_pending": (ab_new["count"] + sp_new["count"] +
                                      ls_new["count"] + wu_staging["count"]),
                    "total_attention_needed": (ab_failed["count"] + ls_review["count"] +
                                               wu_failed["count"]),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Phase 2K: /import/process/dry-run ──

    @api.post("/import/process/dry-run")
    def import_process_dry_run_endpoint():
        """Dry-run article bundle processing. Returns plan without executing file ops."""
        try:
            from scientra.io.article_bundle_importer import ArticleBundleImporter
            importer = ArticleBundleImporter(root)
            result = importer.process(archive_mode="copy", dry_run=True)
            # Ensure all paths are relative
            for r in result.get("results", []):
                for k in ("would_copy_main",):
                    if k in r and r[k]:
                        r[k] = str(r[k]).replace("\\", "/")
            return {
                **result,
                "dry_run": True,
                "note": "This is a dry-run. No files were copied or modified. Use --process to execute.",
                "next_commands": [
                    "python Scripts/process_article_bundles.py --scan",
                    "python Scripts/process_article_bundles.py --process --dry-run",
                    "python Scripts/process_article_bundles.py --process --archive-mode copy",
                ],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/assets/by-paper/{paper_id}")
    def assets_by_paper_endpoint(paper_id: str):
        try:
            from scientra.io.assets_viewer import AssetsViewer
            viewer = AssetsViewer()
            return viewer.get_by_paper(paper_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/assets/search")
    def assets_search_endpoint(query: str = "", type: str = "", paper_id: str = "", limit: int = 20):
        try:
            from scientra.io.assets_viewer import AssetsViewer
            viewer = AssetsViewer()
            return viewer.search(query=query, asset_type=type, paper_id=paper_id, limit=min(limit, 50))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── /v1/agent/ask (enhanced) ──

    @api.post("/v1/agent/ask", response_model=AgentAskResponse)
    def v1_agent_ask(payload: AgentAskRequest) -> AgentAskResponse:
        try:
            from scientra.agent.literature_agent import LiteratureAgent
        except ImportError as e:
            raise HTTPException(status_code=500, detail=f"Agent module not available: {e}")

        agent = LiteratureAgent()
        response = agent.ask(
            question=payload.question,
            top_k=payload.top_k,
            chunk_types=payload.chunk_types,
            include_evidence=payload.include_evidence,
            include_assets=payload.include_assets,
            paper_id=payload.paper_id,
            use_llm=payload.use_llm,
            return_context=payload.return_context,
        )

        context_pack = None
        if payload.return_context and response.raw_context:
            ctx = response.raw_context
            context_pack = AgentContextPack(
                chunks=[
                    AgentContextChunk(
                        chunk_id=getattr(c, 'chunk_id', ''),
                        paper_id=getattr(c, 'paper_id', ''),
                        chunk_type=getattr(c, 'chunk_type', ''),
                        text=getattr(c, 'text', ''),
                        source=getattr(c, 'source', ''),
                        score=getattr(c, 'score', 0.0),
                    )
                    for c in getattr(ctx, 'chunks', [])
                ],
                papers=getattr(ctx, 'papers', {}),
            )

        return AgentAskResponse(
            question=response.question,
            answer=response.answer,
            citations=[
                AgentCitation(
                    ref_id=c.ref_id,
                    chunk_id=c.chunk_id,
                    paper_id=c.paper_id,
                    paper_title=c.paper_title,
                    paper_year=c.paper_year,
                    text_snippet=c.text_snippet,
                    linked_evidence_id=c.linked_evidence_id,
                    source=c.source,
                    confidence=c.confidence,
                )
                for c in response.citations
            ],
            context_used=response.context_used,
            papers_cited=response.papers_cited,
            model=response.model,
            elapsed_ms=response.elapsed_ms,
            intent=response.intent,
            context=context_pack,
            token_usage=AgentTokenUsage(**response.token_usage) if response.token_usage else None,
        )

    return api


def _route(request: LiteratureQueryRequest, query_type: QueryType) -> LiteratureQueryResponse:
    data = request.model_dump() if hasattr(request, "model_dump") else request.dict()
    data["query_type"] = query_type
    return literature_query(data)


def _find_score(resp: Any, paper_id: str) -> float:
    try:
        for s in resp.scores or []:
            if s.paper_id == paper_id:
                return float(s.score)
    except Exception:
        pass
    return 0.0


def main() -> None:
    if FastAPI is None:
        raise RuntimeError("FastAPI is required. Install: pip install fastapi uvicorn")
    import uvicorn
    uvicorn.run("scientra.server:app", host="127.0.0.1", port=8710, reload=False)


app: FastAPI | None = None
if FastAPI is not None:
    app = create_app()

    # ── Register top-level multipart upload route ──
    # This must be registered at the app level (not inside create_app)
    # because __future__ annotations (PEP 563) interacts poorly with
    # FastAPI's dependency resolution inside nested functions.
    #
    # The route uses File(...) default metadata so FastAPI can resolve
    # UploadFile parameters even with stringified annotations.
    try:
        from fastapi import UploadFile, File as FastAPIFile, Form as FastAPIForm

        @app.post("/import/upload-session/{session_id}/files")
        async def upload_files_multipart(
            session_id: str,
            files: list[UploadFile] = FastAPIFile(default=[]),
            relative_paths: str | None = FastAPIForm(default=None),
        ):
            """Upload files via multipart form-data.

            Accepts: multipart/form-data with one or more 'files' parts.
            Optional: 'relative_paths' form field (JSON array of relative paths
                      matching each file's folder context, e.g. from webkitRelativePath).

            Each file part name should be 'files' (repeated for multiple files).
            """
            import json as _json

            # Parse relative paths if provided
            rpaths: list[str] = []
            if relative_paths:
                try:
                    rpaths = _json.loads(relative_paths)
                except Exception:
                    rpaths = []

            file_items: list[tuple[str, bytes, str]] = []
            for i, f in enumerate(files):
                content = await f.read()
                filename = f.filename or "unnamed"
                # Use provided relative_path, or fall back to filename
                rel_path = rpaths[i] if i < len(rpaths) else filename
                file_items.append((filename, content, rel_path))

            if not file_items:
                raise HTTPException(status_code=400, detail="No files provided")

            from scientra.io.web_import import WebImportSession
            session = WebImportSession(_resolve_root())
            result = session.add_files(session_id, file_items)

            if "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
    except Exception:
        pass  # Multipart route not critical — base64 endpoints available


if __name__ == "__main__":
    main()
