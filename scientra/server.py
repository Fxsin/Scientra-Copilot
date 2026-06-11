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
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


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


def _build_topic_name(keywords: list[str]) -> str:
    """Build a human-readable topic name from top keywords."""
    if not keywords:
        return "Mixed research topic"
    # Filter: remove very short, purely numeric, or artifact tokens
    clean = [k for k in keywords if len(k) >= 3 and not k.isdigit() and k.lower() not in _TOPIC_STOPWORDS]
    if not clean:
        return "Mixed research topic"
    top = clean[:4]
    # Capitalize each word properly
    titled = [w[0].upper() + w[1:] if len(w) > 1 else w.upper() for w in top]
    if len(titled) == 1:
        return titled[0]
    if len(titled) == 2:
        return f"{titled[0]} and {titled[1]}"
    return f"{titled[0]}, {titled[1]}, and {titled[2]}"


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
                        vectors[pid] = list(vec)
        except Exception:
            pass

        # ── Build paper lookup ──
        paper_map: dict[str, dict[str, Any]] = {}
        for p in papers:
            pid = p.get("paper_id", "")
            if pid:
                paper_map[pid] = p

        # ── Simple greedy clustering ──
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
            cluster_pids = {seed}
            for pid in neighbors:
                cluster_pids.add(pid)
                if len(cluster_pids) >= MIN_CLUSTER * 4:
                    break

            if len(cluster_pids) < MIN_CLUSTER:
                continue

            # Compute cluster stats
            years = [int(paper_map[pid].get("year") or 0) for pid in cluster_pids if pid in paper_map]
            avg_year = float(sum(years) / len(years)) if years else 0.0
            ctype = "growing" if avg_year >= 2020 else "mature"

            # Representative papers
            rep_pids = list(cluster_pids)[:limit]
            rep_papers = []
            for pid in rep_pids:
                p = paper_map.get(pid)
                if p:
                    rep_papers.append({
                        "paper_id": pid,
                        "title": p.get("title", ""),
                        "authors": p.get("authors", []) or [],
                        "year": p.get("year"),
                        "journal": p.get("journal", ""),
                        "doi": p.get("doi", ""),
                    })

            cluster_id = f"topic_{len(clusters) + 1:03d}"

            # ── Extract keywords ──
            cluster_paper_ids = list(cluster_pids)
            keywords = _extract_cluster_keywords(cluster_paper_ids, paper_map, root, paper_ids)
            topic_name = _build_topic_name(keywords) if keywords else f"Topic {len(clusters) + 1}"

            # ── Build summary ──
            summary_text = " / ".join(keywords[:5]) if keywords else ""
            if summary_text:
                summary_text = f"Research cluster covering {summary_text.lower()}."

            # ── Year range ──
            if years:
                year_range = [int(min(years)), int(max(years))]
            else:
                year_range = [0, 0]

            # ── Better type detection ──
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
                "representative_papers": rep_papers,
                "papers": rep_papers,
            })
            used.update(cluster_pids)

        # ── Separate by type ──
        mature_topics = [c for c in clusters if c["type"] == "mature"]
        growing_topics = [c for c in clusters if c["type"] == "growing"]
        gap_topics = [c for c in clusters if c["type"] == "gap"]

        # ── Relationships (always included, using centroid + keyword overlap) ──
        topic_relationships: list[dict[str, Any]] = []
        if len(clusters) >= 2:
            pairs: list[tuple[int, int, float]] = []
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    score = 0.0
                    # Centroid similarity
                    pids_i = [p["paper_id"] for p in clusters[i]["papers"] if p["paper_id"] in vectors]
                    pids_j = [p["paper_id"] for p in clusters[j]["papers"] if p["paper_id"] in vectors]
                    if pids_i and pids_j:
                        score += 1.0 - _cosine_distance(vectors[pids_i[0]], vectors[pids_j[0]])
                    # Keyword overlap
                    kw_i = set(clusters[i].get("keywords", [])[:5])
                    kw_j = set(clusters[j].get("keywords", [])[:5])
                    if kw_i and kw_j:
                        overlap = len(kw_i & kw_j) / max(len(kw_i | kw_j), 1)
                        score += overlap * 0.5
                    score = score / 1.5  # normalise
                    if score > 0.35:
                        pairs.append((i, j, score))
            pairs.sort(key=lambda x: x[2], reverse=True)
            # Keep top 2 per topic
            used_pairs: set[tuple[int, int]] = set()
            seen_counts: dict[int, int] = {}
            for i, j, score in pairs:
                if (i, j) in used_pairs:
                    continue
                if seen_counts.get(i, 0) >= 3 or seen_counts.get(j, 0) >= 3:
                    continue
                used_pairs.add((i, j))
                seen_counts[i] = seen_counts.get(i, 0) + 1
                seen_counts[j] = seen_counts.get(j, 0) + 1
                topic_relationships.append({
                    "source_topic_id": clusters[i]["cluster_id"],
                    "target_topic_id": clusters[j]["cluster_id"],
                    "similarity": float(round(score, 3)),
                    "reason": "Centroid similarity and keyword overlap",
                })

        return {
            "mature_topics": mature_topics,
            "growing_topics": growing_topics,
            "gap_topics": gap_topics,
            "topic_relationships": topic_relationships,
            "clusters": clusters,
            "network_stats": {
                "total_nodes": int(len(clusters)),
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
        # Reuse clustering logic to find the topic
        papers = _load_yaml_metadata(root)
        paper_map: dict[str, dict[str, Any]] = {}
        for p in papers:
            pid = p.get("paper_id", "")
            if pid:
                paper_map[pid] = p

        # Load vectors and regenerate clusters
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
                        vectors[pid] = list(vec)
        except Exception:
            pass

        MIN_CLUSTER = 3
        MAX_CLUSTERS = 8
        used: set[str] = set()
        clusters: list[dict[str, Any]] = []
        paper_ids = list(vectors.keys())
        import random
        random.shuffle(paper_ids)

        for _ in range(MAX_CLUSTERS):
            seed = None
            for pid in paper_ids:
                if pid not in used:
                    seed = pid
                    break
            if seed is None:
                break
            qv = vectors[seed]
            scored = [(pid, _cosine_distance(qv, vectors[pid])) for pid in paper_ids if pid not in used and pid != seed and pid in vectors]
            scored.sort(key=lambda x: x[1])
            cluster_pids = {seed}
            for pid, _ in scored[:MIN_CLUSTER * 3]:
                cluster_pids.add(pid)
                if len(cluster_pids) >= MIN_CLUSTER * 4:
                    break
            if len(cluster_pids) < MIN_CLUSTER:
                continue

            years_list = [int(paper_map[pid].get("year") or 0) for pid in cluster_pids if pid in paper_map]
            avg_year_val = float(sum(years_list) / len(years_list)) if years_list else 0.0
            yr_range = [int(min(years_list)), int(max(years_list))] if years_list else [0, 0]
            kw = _extract_cluster_keywords(list(cluster_pids), paper_map, root, paper_ids)
            cluster_id = f"topic_{len(clusters) + 1:03d}"

            ctype = "mature"
            trend = "stable"
            this_year = datetime.now(timezone.utc).year
            recent_count = sum(1 for y in years_list if y >= this_year - 5)
            recent_ratio = recent_count / len(years_list) if years_list else 0
            year_span = max(years_list) - min(years_list) if len(years_list) >= 2 else 0
            if len(cluster_pids) >= 6 and year_span >= 5:
                ctype = "mature"; trend = "active" if recent_ratio >= 0.4 else "stable"
            elif recent_ratio >= 0.4 or (years_list and avg_year_val >= this_year - 5):
                ctype = "growing"; trend = "active"
            elif len(cluster_pids) <= 3:
                ctype = "gap"; trend = "sparse"

            all_papers = []
            for pid in cluster_pids:
                p = paper_map.get(pid)
                if p:
                    all_papers.append(_build_topic_paper_payload(root, p))

            clusters.append({
                "cluster_id": cluster_id, "name": _build_topic_name(kw) if kw else f"Topic {len(clusters)+1}",
                "type": ctype, "trend": trend, "paper_count": int(len(cluster_pids)),
                "avg_year": round(avg_year_val, 1), "year_range": yr_range,
                "keywords": [str(k) for k in kw[:8]], "summary": (" / ".join(kw[:5]) if kw else ""),
                "papers": all_papers,
                "representative_papers": all_papers[:5],
                "recent_count": int(recent_count), "recent_ratio": float(round(recent_ratio, 3)),
                "trend_label": trend, "trend_reason": "Based on publication recency and volume",
            })
            used.update(cluster_pids)

        # Find the requested topic
        for c in clusters:
            if c["cluster_id"] == topic_id:
                # Compute relevance scores for papers within this topic
                cleaned_kw = [k for k in kw if k.lower() not in _TOPIC_STOPWORDS and len(k) >= 3]
                kw_set = set(k.lower() for k in cleaned_kw)
                for p in c["papers"]:
                    title_words = set((p.get("title") or "").lower().split())
                    summary_text = (p.get("summary") or "").lower()
                    summary_words = set(summary_text.split())
                    all_words = title_words | summary_words
                    overlap = len(kw_set & all_words)
                    ratio = overlap / max(len(kw_set), 1)
                    if ratio >= 0.10:
                        p["topic_relevance"] = round(float(ratio), 3)
                        p["relevance_label"] = "high"
                        p["relevance_reason"] = "Shares key title and summary signals with this topic."
                    elif ratio >= 0.03:
                        p["topic_relevance"] = round(float(ratio), 3)
                        p["relevance_label"] = "medium"
                        p["relevance_reason"] = "Partial overlap with the main topic signals."
                    else:
                        p["topic_relevance"] = round(float(ratio), 3)
                        p["relevance_label"] = "low"
                        p["relevance_reason"] = "Only limited overlap with the main topic signals."
                low_count = sum(1 for p in c["papers"] if p.get("relevance_label") == "low")
                high_count = sum(1 for p in c["papers"] if p.get("relevance_label") == "high")
                total_p = len(c["papers"])
                if high_count / max(total_p, 1) >= 0.6:
                    c["cohesion_label"] = "strong"
                    c["cohesion_score"] = round(high_count / total_p, 2)
                elif low_count / max(total_p, 1) <= 0.3:
                    c["cohesion_label"] = "moderate"
                    c["cohesion_score"] = round(1.0 - low_count / total_p, 2)
                else:
                    c["cohesion_label"] = "mixed"
                    c["cohesion_score"] = round(1.0 - low_count / total_p, 2)

            # Add related topics
            related = []
            for other in clusters:
                if other["cluster_id"] == topic_id:
                    continue
                score = 0.0
                pids_a = [p["paper_id"] for p in c["papers"] if p["paper_id"] in vectors]
                pids_b = [p["paper_id"] for p in other["papers"] if p["paper_id"] in vectors]
                if pids_a and pids_b:
                    score = 1.0 - _cosine_distance(vectors[pids_a[0]], vectors[pids_b[0]])
                kw_x = set(c.get("keywords", [])[:5])
                kw_y = set(other.get("keywords", [])[:5])
                if kw_x and kw_y:
                    score += len(kw_x & kw_y) / max(len(kw_x | kw_y), 1) * 0.5
                    score /= 1.5
                if score > 0.3:
                    related.append({"cluster_id": other["cluster_id"], "name": other["name"], "similarity": float(round(score, 3)), "reason": "Vector and keyword similarity"})
                c["related_topics"] = sorted(related, key=lambda x: x["similarity"], reverse=True)[:5]
                # Year distribution
                yd: dict[int, int] = {}
                for p in c["papers"]:
                    y = p.get("year")
                    if y and isinstance(y, (int, float)) and 1800 <= y <= this_year + 1:
                        yd[int(y)] = yd.get(int(y), 0) + 1
                c["year_distribution"] = [{"year": y, "count": c2} for y, c2 in sorted(yd.items())]
                # Evolution phases
                valid_years = [p.get("year") for p in c["papers"] if p.get("year") and isinstance(p.get("year"), (int, float))]
                phases = []
                if valid_years and max(valid_years) > min(valid_years):
                    min_y, max_y = int(min(valid_years)), int(max(valid_years))
                    span = max_y - min_y
                    third = max(1, span // 3) if span >= 3 else 1
                    phase_defs = [("early", "Early phase", min_y, min_y + third), ("middle", "Middle phase", max(min_y + third + 1, min_y + third), min_y + third * 2), ("recent", "Recent phase", max(min_y + third * 2 + 1, min_y + third * 2), max_y)]
                for p_phase, p_label, p_start, p_end in phase_defs:
                        pp = [p for p in c["papers"] if p.get("year") and p_start <= int(p["year"]) <= p_end]
                        if pp:
                            phases.append({"phase": p_phase, "label": p_label, "year_range": [p_start, p_end], "paper_count": len(pp), "keywords": kw[:4], "representative_papers": pp[:2]})
                c["evolution_phases"] = phases
                return {"topic": c}
        raise HTTPException(status_code=404, detail=f"Topic not found: {topic_id}")

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
