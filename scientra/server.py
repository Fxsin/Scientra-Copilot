from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from fastapi import FastAPI
except ModuleNotFoundError:  # pragma: no cover - depends on deployment env
    FastAPI = None  # type: ignore

try:
    from scientra.models import LiteratureQueryRequest, LiteratureQueryResponse, QueryFilters, QueryType
    from scientra.query import literature_query
except ModuleNotFoundError:
    from scientra.models import LiteratureQueryRequest, LiteratureQueryResponse, QueryFilters, QueryType
    from scientra.query import literature_query


def _build_health_info(root: Path) -> dict[str, object]:
    """Probe LanceDB and return real health info so the Web UI shows actual data."""
    lancedb_status: str = "unknown"
    table_counts: dict[str, int] = {}
    embedding_model: str = "BAAI/bge-m3"

    try:
        import lancedb
        db_dir = root / "04_VectorDB" / "lancedb"
        if db_dir.exists() and any(db_dir.iterdir()):
            db = lancedb.connect(str(db_dir))
            tables = db.table_names()
            for t in tables:
                try:
                    tbl = db.open_table(t)
                    table_counts[t] = len(tbl.to_arrow())
                except Exception:
                    pass
            if table_counts:
                lancedb_status = "ok"
            else:
                lancedb_status = "empty"
        else:
            lancedb_status = "no database directory"
    except Exception as exc:
        lancedb_status = f"error: {type(exc).__name__}: {exc}"

    # Try to read embedding model from report
    report_path = root / "04_VectorDB" / "embedding_report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            embedding_model = report.get("embedding_model", embedding_model)
        except Exception:
            pass

    return {
        "api_status": "ok",
        "service": "Scientra Copilot Query API",
        "lancedb_status": lancedb_status,
        "table_counts": table_counts,
        "embedding_model": embedding_model,
        "agent_entrypoint": "literature_query",
        "pdf_access": "forbidden",
        "direct_lancedb_access": "forbidden",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def create_app(root: Path | None = None) -> FastAPI:
    if FastAPI is None:
        raise RuntimeError("FastAPI is required to run Scientra Copilot API. Install fastapi and uvicorn.")

    if root is None:
        root = Path(os.environ.get("SCIENTRA_ROOT", Path(__file__).resolve().parents[1]))
    root = Path(root)

    api = FastAPI(
        title="Scientra Copilot Query API",
        version="0.1.0",
        description="Unified Scientra Copilot query API. Agents must call literature_query and must not directly access PDF or LanceDB.",
    )

    @api.get("/health")
    def health() -> dict[str, object]:
        return _build_health_info(root)

    @api.post("/v1/scientra/query", response_model=LiteratureQueryResponse)
    def query_literature(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return literature_query(request)

    @api.post("/v1/scientra/search_by_keyword", response_model=LiteratureQueryResponse)
    def search_by_keyword(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return route_query(request, QueryType.search_by_keyword)

    @api.post("/v1/scientra/search_by_species", response_model=LiteratureQueryResponse)
    def search_by_species(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return route_query(request, QueryType.search_by_species)

    @api.post("/v1/scientra/search_by_toxin", response_model=LiteratureQueryResponse)
    def search_by_toxin(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return route_query(request, QueryType.search_by_toxin)

    @api.post("/v1/scientra/search_by_method", response_model=LiteratureQueryResponse)
    def search_by_method(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return route_query(request, QueryType.search_by_method)

    @api.post("/v1/scientra/search_by_mechanism", response_model=LiteratureQueryResponse)
    def search_by_mechanism(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return route_query(request, QueryType.search_by_mechanism)

    @api.post("/v1/scientra/search_by_year", response_model=LiteratureQueryResponse)
    def search_by_year(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return route_query(request, QueryType.search_by_year)

    @api.post("/v1/scientra/hybrid_search", response_model=LiteratureQueryResponse)
    def hybrid_search(request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        return route_query(request, QueryType.hybrid_search)

    return api


def route_query(request: LiteratureQueryRequest, query_type: QueryType) -> LiteratureQueryResponse:
    data = request.model_dump() if hasattr(request, "model_dump") else request.dict()
    data["query_type"] = query_type
    return literature_query(data)


def main() -> None:
    if FastAPI is None:
        raise RuntimeError("FastAPI is required to run Scientra Copilot API. Install fastapi and uvicorn.")
    import uvicorn
    uvicorn.run("scientra.server:app", host="127.0.0.1", port=8710, reload=False)


app: FastAPI | None = None
if FastAPI is not None:
    root = Path(os.environ.get("SCIENTRA_ROOT", Path(__file__).resolve().parents[1]))
    app = create_app(root)


if __name__ == "__main__":
    main()
