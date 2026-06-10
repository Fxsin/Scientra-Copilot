from __future__ import annotations

from typing import Any

try:
    from scientra.agent import AgentQueryInterface
    from scientra.models import EvidenceItem, LiteratureQueryResponse, QueryFilters, QueryType, SummaryResult
except ModuleNotFoundError:
    from scientra.agent import AgentQueryInterface
    from scientra.models import EvidenceItem, LiteratureQueryResponse, QueryFilters, QueryType, SummaryResult


class LiteratureAgentSDK:
    """Public SDK for future Agents.

    Agents should depend on this SDK or call literature_query through the API.
    The SDK does not expose PDF, SQLite, LanceDB, or internal index access.
    """

    def __init__(self, interface: AgentQueryInterface | None = None) -> None:
        self.interface = interface or AgentQueryInterface()

    def search(
        self,
        query: str,
        query_type: QueryType | str = QueryType.hybrid_search,
        top_k: int = 10,
        filters: QueryFilters | dict[str, Any] | None = None,
        use_vector: bool = True,
    ) -> LiteratureQueryResponse:
        return self.interface.search(
            query=query,
            query_type=query_type,
            top_k=top_k,
            filters=filters,
            use_vector=use_vector,
        )

    def retrieve(
        self,
        query: str | None = None,
        paper_id: str | None = None,
        top_k: int = 10,
        filters: QueryFilters | dict[str, Any] | None = None,
    ) -> LiteratureQueryResponse:
        return self.interface.retrieve(
            query=query,
            paper_id=paper_id,
            top_k=top_k,
            filters=filters,
        )

    def get_summary(self, paper_id: str) -> SummaryResult | None:
        return self.interface.get_summary(paper_id)

    def get_evidence(
        self,
        query: str | None = None,
        paper_id: str | None = None,
        top_k: int = 10,
        filters: QueryFilters | dict[str, Any] | None = None,
    ) -> list[EvidenceItem]:
        return self.interface.get_evidence(
            query=query,
            paper_id=paper_id,
            top_k=top_k,
            filters=filters,
        )


_default_sdk = LiteratureAgentSDK()


def search(
    query: str,
    query_type: QueryType | str = QueryType.hybrid_search,
    top_k: int = 10,
    filters: QueryFilters | dict[str, Any] | None = None,
    use_vector: bool = True,
) -> LiteratureQueryResponse:
    return _default_sdk.search(
        query=query,
        query_type=query_type,
        top_k=top_k,
        filters=filters,
        use_vector=use_vector,
    )


def retrieve(
    query: str | None = None,
    paper_id: str | None = None,
    top_k: int = 10,
    filters: QueryFilters | dict[str, Any] | None = None,
) -> LiteratureQueryResponse:
    return _default_sdk.retrieve(
        query=query,
        paper_id=paper_id,
        top_k=top_k,
        filters=filters,
    )


def get_summary(paper_id: str) -> SummaryResult | None:
    return _default_sdk.get_summary(paper_id)


def get_evidence(
    query: str | None = None,
    paper_id: str | None = None,
    top_k: int = 10,
    filters: QueryFilters | dict[str, Any] | None = None,
) -> list[EvidenceItem]:
    return _default_sdk.get_evidence(
        query=query,
        paper_id=paper_id,
        top_k=top_k,
        filters=filters,
    )


def get_agent_sdk() -> LiteratureAgentSDK:
    return _default_sdk

