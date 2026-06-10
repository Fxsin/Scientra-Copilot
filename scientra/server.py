from __future__ import annotations

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


def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is required to run Scientra Copilot API. Install fastapi and uvicorn.")

    api = FastAPI(
        title="Scientra Copilot API",
        version="0.1.0",
        description="Unified Scientra Copilot query API. Agents must call literature_query and must not directly access PDF or LanceDB.",
    )

    @api.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "Scientra Copilot API",
            "agent_entrypoint": "literature_query",
            "pdf_access": "forbidden",
            "direct_lancedb_access": "forbidden",
        }

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


app = create_app() if FastAPI is not None else None


def main() -> None:
    if FastAPI is None:
        raise RuntimeError("FastAPI is required to run Scientra Copilot API. Install fastapi and uvicorn.")
    import uvicorn

    uvicorn.run("scientra.api_server:app", host="127.0.0.1", port=8710, reload=False)


if __name__ == "__main__":
    main()
