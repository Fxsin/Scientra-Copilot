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
    from scientra.models import LiteratureQueryRequest, LiteratureQueryResponse, QueryFilters, QueryType
    from scientra.query import literature_query, LiteratureQueryService
except ModuleNotFoundError:
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
    """Build a human-readable topic name from keywords and representative paper titles."""
    if not keywords:
        return "Mixed research topic"
    # Filter: remove very short, purely numeric, or artifact tokens
    clean = [k for k in keywords if len(k) >= 3 and not k.isdigit() and k.lower() not in _TOPIC_STOPWORDS]
    if not clean:
        return "Mixed research topic"

    # Try to generate a meaningful name from the best keyword + context
    best = clean[0] if clean else ""
    best_titled = best[0].upper() + best[1:] if len(best) > 1 else best.upper()

    # If we have paper titles, try to extract a descriptive phrase
    if paper_titles and len(clean) >= 2:
        # Use best keyword as primary subject, add a qualifier from second keyword
        second = clean[1]
        second_titled = second[0].upper() + second[1:] if len(second) > 1 else second.upper()
        # Avoid listing too many keywords; prefer "X and Y" or "X Research"
        if len(clean) == 2:
            return f"{best_titled} and {second_titled}"
        # For 3+ keywords, use "X and Related Studies" pattern
        if len(clean) >= 3:
            return f"{best_titled} and {second_titled} Research"

    # Fallback with single keyword
    if len(clean) == 1:
        return f"{best_titled} Research"

    # Generic fallback
    return f"Research on {best_titled}"


def _load_evidence_summary(root: Path, paper_id: str) -> dict[str, Any] | None:
    """Load a lightweight evidence summary for a paper (searches by paper_id suffix)."""
    evidence_root = root / "03_Evidence"
    if not evidence_root.exists():
        return None
    # Try exact match first
    ev_path = evidence_root / paper_id / "evidence.json"
    if not ev_path.exists():
        # Search by paper_id suffix (evidence dirs use paper_key naming with hash suffix)
        search_id = paper_id.replace("paper_", "") if paper_id.startswith("paper_") else paper_id
        for d in evidence_root.iterdir():
            if d.is_dir() and (d.name.endswith(search_id) or d.name.endswith(paper_id)):
                ev_path = d / "evidence.json"
                break
    if not ev_path.exists():
        return None
    try:
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        return {
            "status": ev.get("status", "unknown"),
            "core_findings": [c.get("finding", c.get("text", ""))[:200] for c in ev.get("core_findings", [])[:3]],
            "key_results": [r.get("result", "")[:200] for r in ev.get("key_results", [])[:3]],
            "methods": [m.get("name", "")[:150] for m in ev.get("methods", [])[:3]],
            "limitations": [l.get("limitation", "")[:200] for l in ev.get("limitations", [])[:2]],
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
        # Select 1-2 representative papers from this phase
        ph_rep = ph_papers[:2] if ph_papers else []
        phases.append({
            "phase": ph_key,
            "label": ph_label,
            "year_range": [ph_start, ph_end],
            "paper_count": len(ph_papers),
            "keywords": [str(k) for k in ph_kw[:5]],
            "representative_papers": [
                {
                    "paper_id": str(rp.get("paper_id", "")),
                    "title": str(rp.get("title", "")),
                    "authors": rp.get("authors", []) or [],
                    "year": rp.get("year"),
                    "journal": str(rp.get("journal", "")),
                    "doi": str(rp.get("doi", "")),
                }
                for rp in ph_rep
            ],
            "papers": ph_rep,
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
        papers = _load_yaml_metadata(root)
        if not papers:
            return _empty_cluster_result()

        # ── Load vectors ──
        vectors: dict[str, list[float]] = {}
        try:
            import lancedb
            db_dir = root / "04_VectorDB" / "lancedb"
            if db_dir.exists() and any(db_dir.iterdir()):
                db = lancedb.connect(str(db_dir))
                table = db.open_table(db.table_names()[0])
                df = table.to_pandas()
                for row in df.to_dict("records"):
                    pid = str(row.get("paper_id", ""))
                    vec = row.get("vector")
                    if pid and vec is not None:
                        vectors[pid] = [float(x) for x in vec]
        except Exception:
            pass

        # ── Use shared clustering ──
        clusters, topic_relationships = _build_research_map_clusters(root, papers, vectors, limit)

        # ── For overview: light version (strip evidence/summary from papers to reduce payload) ──
        light_clusters: list[dict[str, Any]] = []
        for c in clusters:
            lc = dict(c)
            # Keep only light paper info for overview
            light_papers: list[dict[str, Any]] = []
            for p in c.get("papers", []):
                light_papers.append({
                    "paper_id": p.get("paper_id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []) or [],
                    "year": p.get("year"),
                    "journal": p.get("journal", ""),
                    "doi": p.get("doi", ""),
                    "topic_relevance": p.get("topic_relevance"),
                    "relevance_label": p.get("relevance_label"),
                    "relevance_reason": p.get("relevance_reason"),
                })
            lc["papers"] = light_papers
            # Add related_topics placeholder (computed lazily)
            lc["related_topics"] = []
            light_clusters.append(lc)

        # Build related_topics for each cluster
        for c in light_clusters:
            c["related_topics"] = _build_related_topics_for_cluster(
                c["cluster_id"], light_clusters, topic_relationships
            )

        # ── Separate by type ──
        mature_topics = [c for c in light_clusters if c["type"] == "mature"]
        growing_topics = [c for c in light_clusters if c["type"] == "growing"]
        gap_topics = [c for c in light_clusters if c["type"] == "gap"]

        return {
            "mature_topics": mature_topics,
            "growing_topics": growing_topics,
            "gap_topics": gap_topics,
            "topic_relationships": topic_relationships,
            "clusters": light_clusters,
            "network_stats": {
                "total_nodes": int(len(light_clusters)),
                "total_edges": int(len(topic_relationships)),
            },
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

        # ── Load vectors ──
        vectors: dict[str, list[float]] = {}
        try:
            import lancedb
            db_dir = root / "04_VectorDB" / "lancedb"
            if db_dir.exists() and any(db_dir.iterdir()):
                db = lancedb.connect(str(db_dir))
                table = db.open_table(db.table_names()[0])
                df = table.to_pandas()
                for row in df.to_dict("records"):
                    pid = str(row.get("paper_id", ""))
                    vec = row.get("vector")
                    if pid and vec is not None:
                        vectors[pid] = [float(x) for x in vec]
        except Exception:
            pass

        # ── Use shared clustering to get the same clusters as /research-map ──
        clusters, topic_relationships = _build_research_map_clusters(root, papers, vectors)

        # ── Find the requested cluster ──
        cluster = next((c for c in clusters if c.get("cluster_id") == topic_id), None)
        if not cluster:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

        # ── Build paper map for evolution phases ──
        paper_map: dict[str, dict[str, Any]] = {}
        for p in papers:
            pid = p.get("paper_id", "")
            if pid:
                paper_map[pid] = p

        # ── Compute year_distribution ──
        year_distribution = _compute_year_distribution(cluster.get("papers", []))

        # ── Compute evolution_phases ──
        cluster_pids = {p["paper_id"] for p in cluster.get("papers", []) if p.get("paper_id")}
        evolution_phases = _build_evolution_phases(
            cluster.get("papers", []), cluster_pids, paper_map, root
        )

        # ── Build related_topics ──
        related_topics = _build_related_topics_for_cluster(
            topic_id, clusters, topic_relationships
        )

        # ── Build topic with full detail (keep full papers with summary/evidence) ──
        topic = dict(cluster)
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


if __name__ == "__main__":
    main()
