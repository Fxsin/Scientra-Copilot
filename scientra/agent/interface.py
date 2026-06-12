"""
Agent Query Interface — safe Agent-facing wrapper for literature_query().

Relocated from scientra/agent.py into the scientra/agent/ package (Phase 0.7).
Maintains backward compatibility: does NOT expose filesystem, PDF, SQLite,
or LanceDB access to Agent code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:
    from scientra.models import (
        EvidenceItem,
        LiteratureQueryRequest,
        LiteratureQueryResponse,
        QueryFilters,
        QueryType,
        SummaryResult,
    )
    from scientra.query import literature_query as default_literature_query
except ModuleNotFoundError:
    from scientra.models import (
        EvidenceItem,
        LiteratureQueryRequest,
        LiteratureQueryResponse,
        QueryFilters,
        QueryType,
        SummaryResult,
    )
    from scientra.query import literature_query as default_literature_query


class AgentAccessPolicyError(RuntimeError):
    pass


class AgentQueryInterface:
    """Safe Agent-facing interface.

    This class only calls Scientra Copilot literature_query(). It does not expose
    filesystem paths, database handles, PDF access, SQLite access, or LanceDB
    access to Agent code.
    """

    def __init__(
        self,
        query_fn: Callable[..., LiteratureQueryResponse] = default_literature_query,
    ) -> None:
        self._query_fn = query_fn

    def literature_query(
        self,
        request: LiteratureQueryRequest | dict[str, Any] | str | None = None,
        **kwargs: Any,
    ) -> LiteratureQueryResponse:
        parsed_request = coerce_agent_request(request, kwargs)
        response = self._query_fn(parsed_request)
        enforce_agent_policy(response)
        return response

    def search(
        self,
        query: str,
        query_type: QueryType | str = QueryType.hybrid_search,
        top_k: int = 10,
        filters: QueryFilters | dict[str, Any] | None = None,
        use_vector: bool = True,
    ) -> LiteratureQueryResponse:
        return self.literature_query(
            {
                "query_type": query_type,
                "query": query,
                "top_k": top_k,
                "filters": normalize_filters(filters),
                "include_summaries": True,
                "include_evidence": True,
                "include_citations": True,
                "use_vector": use_vector,
            }
        )

    def retrieve(
        self,
        query: str | None = None,
        paper_id: str | None = None,
        top_k: int = 10,
        filters: QueryFilters | dict[str, Any] | None = None,
    ) -> LiteratureQueryResponse:
        merged_filters = normalize_filters(filters)
        if paper_id:
            merged_filters["paper_id"] = paper_id
        return self.literature_query(
            {
                "query_type": QueryType.hybrid_search if query else QueryType.search_by_keyword,
                "query": query,
                "top_k": top_k,
                "filters": merged_filters,
                "include_summaries": True,
                "include_evidence": True,
                "include_citations": True,
                "use_vector": bool(query),
            }
        )

    def get_summary(self, paper_id: str) -> SummaryResult | None:
        response = self.retrieve(
            paper_id=paper_id,
            top_k=1,
            filters={"paper_id": paper_id},
        )
        return response.summaries[0] if response.summaries else None

    def get_evidence(
        self,
        query: str | None = None,
        paper_id: str | None = None,
        top_k: int = 10,
        filters: QueryFilters | dict[str, Any] | None = None,
    ) -> list[EvidenceItem]:
        response = self.retrieve(
            query=query,
            paper_id=paper_id,
            top_k=top_k,
            filters=filters,
        )
        return response.evidence


def normalize_filters(filters: QueryFilters | dict[str, Any] | None) -> dict[str, Any]:
    if filters is None:
        return {}
    if isinstance(filters, QueryFilters):
        return model_to_dict(filters)
    return dict(filters)


def coerce_agent_request(
    request: LiteratureQueryRequest | dict[str, Any] | str | None,
    kwargs: dict[str, Any],
) -> LiteratureQueryRequest:
    if isinstance(request, LiteratureQueryRequest):
        data = model_to_dict(request)
        data.update(kwargs)
        return LiteratureQueryRequest(**data)
    if isinstance(request, str):
        data = {"query": request}
        data.update(kwargs)
        return LiteratureQueryRequest(**data)
    if isinstance(request, dict):
        data = dict(request)
        data.update(kwargs)
        return LiteratureQueryRequest(**data)
    return LiteratureQueryRequest(**kwargs)


def enforce_agent_policy(response: LiteratureQueryResponse) -> None:
    policy = response.policy or {}
    if policy.get("agent_entrypoint") != "literature_query":
        raise AgentAccessPolicyError("Agent responses must come from literature_query.")
    if policy.get("pdf_access") != "forbidden":
        raise AgentAccessPolicyError("Agent PDF access must remain forbidden.")
    if policy.get("direct_lancedb_access") != "forbidden":
        raise AgentAccessPolicyError("Agent direct LanceDB access must remain forbidden.")


def model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)
