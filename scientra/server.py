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
    def paper_related(paper_id: str, limit: int = 5, mode: str = "hybrid") -> dict[str, Any]:
        return {"paper_id": paper_id, "related": [], "mode": mode, "limit": limit}

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
    def research_map() -> dict[str, Any]:
        return {
            "mature_topics": [], "growing_topics": [], "gap_topics": [],
            "topic_relationships": [], "clusters": [],
            "network_stats": {"total_nodes": 0, "total_edges": 0},
        }

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
