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


# ── Phase 0.8: query_assets + enhanced ask_literature ──

def query_assets(
    query: str,
    top_k: int = 10,
    chunk_types: list[str] | None = None,
    paper_id: str | None = None,
    min_quality_score: float = 0.0,
) -> dict[str, Any]:
    """Search pdf_asset_chunks directly. Returns structured results with provenance.

    This is the SDK entry point for asset-native search without LLM.
    """
    try:
        from scientra.agent.context_builder import ContextBuilder
        cb = ContextBuilder()
        chunks = cb.search_assets(
            query=query,
            top_k=min(top_k, 50),
            chunk_types=chunk_types,
            paper_id=paper_id,
            min_quality_score=min_quality_score,
        )
    except ImportError:
        return {"query": query, "results": [], "count": 0, "unique_papers": 0,
                "warnings": ["ContextBuilder not available"], "elapsed_ms": 0}

    papers = set()
    results = []
    for c in chunks:
        papers.add(c.paper_id)
        results.append({
            "chunk_id": c.chunk_id,
            "paper_id": c.paper_id,
            "chunk_type": c.chunk_type,
            "text": c.text,
            "score": round(c.score, 4) if c.score else 0.0,
            "linked_evidence_id": c.linked_evidence_id,
            "linked_evidence_ids": c.linked_evidence_ids if hasattr(c, 'linked_evidence_ids') else [],
            "source_asset_ids": c.source_asset_ids if hasattr(c, 'source_asset_ids') else [],
            "confidence": c.confidence,
            "quality_score": c.quality_score,
            "citation_key": f"[A:{c.paper_id}:{c.chunk_id}]",
        })

    return {
        "query": query,
        "results": results,
        "count": len(results),
        "unique_papers": len(papers),
        "warnings": [],
        "elapsed_ms": 0,
    }


def ask_literature(
    question: str,
    top_k: int = 10,
    chunk_types: list[str] | None = None,
    include_evidence: bool = True,
    include_assets: bool = True,
    paper_id: str | None = None,
    use_llm: bool = True,
    return_context: bool = False,
) -> dict[str, Any]:
    """Ask a research question using the Literature Agent.

    Returns a dict with 'answer', 'citations', 'context_used', 'papers_cited', etc.
    This is the primary entry point for Agent SDK consumers in Phase 0.8+.
    """
    try:
        from scientra.agent.literature_agent import LiteratureAgent
    except ImportError:
        return {
            "question": question,
            "answer": "[Error: Literature Agent not available. Ensure scientra/agent/ is installed.]",
            "citations": [], "context_used": 0, "papers_cited": 0,
        }

    agent = LiteratureAgent()
    response = agent.ask(
        question=question,
        top_k=top_k,
        chunk_types=chunk_types,
        include_evidence=include_evidence,
        include_assets=include_assets,
        paper_id=paper_id,
        use_llm=use_llm,
        return_context=return_context,
    )

    result = {
        "question": response.question,
        "answer": response.answer,
        "citations": [
            {
                "ref_id": c.ref_id,
                "paper_id": c.paper_id,
                "paper_title": c.paper_title,
                "paper_year": c.paper_year,
                "text_snippet": c.text_snippet,
                "linked_evidence_id": c.linked_evidence_id,
                "source": c.source,
                "confidence": c.confidence,
            }
            for c in response.citations
        ],
        "context_used": response.context_used,
        "papers_cited": response.papers_cited,
        "model": response.model,
        "elapsed_ms": response.elapsed_ms,
        "intent": response.intent,
    }

    if return_context and response.raw_context:
        ctx = response.raw_context
        result["context"] = {
            "chunks": [
                {
                    "chunk_id": getattr(c, 'chunk_id', ''),
                    "paper_id": getattr(c, 'paper_id', ''),
                    "chunk_type": getattr(c, 'chunk_type', ''),
                    "text": getattr(c, 'text', ''),
                    "source": getattr(c, 'source', ''),
                    "score": getattr(c, 'score', 0.0),
                }
                for c in getattr(ctx, 'chunks', [])
            ],
            "papers": getattr(ctx, 'papers', {}),
        }

    return result


# ── Phase 2E: Supplementary Entity Query ──

def query_supplementary_entities(
    query: str,
    entity_type: str | None = None,
    paper_id: str | None = None,
    top_k: int = 20,
) -> dict[str, Any]:
    """Search indexed supplementary entities.

    Args:
        query: Entity name to search (gene, protein, compound, etc.)
        entity_type: Filter by type (gene, protein, compound, treatment, sample, etc.)
        paper_id: Optional paper filter
        top_k: Max results

    Returns dict with 'query', 'matches', 'total'.
    """
    try:
        from scientra.pdf_data_assets.supplementary_entity_indexer import SupplementaryEntityIndexer
        indexer = SupplementaryEntityIndexer()
        matches = indexer.search_entities(
            query, entity_type=entity_type, paper_id=paper_id, top_k=min(top_k, 100)
        )
    except ImportError:
        return {"query": query, "matches": [], "total": 0}

    return {"query": query, "matches": matches, "total": len(matches)}


# ── Phase 2G-A: Cross-Paper Entity Comparison ──

def query_supplementary_entity_comparison(
    query: str,
    entity_type: str | None = None,
    paper_id: str | None = None,
    top_k: int = 50,
) -> dict[str, Any]:
    """Compare an entity across all indexed supplementary data.

    Returns aggregated records with direction summary, value column summary,
    and comparability warning. No statistical comparison, no LLM.
    """
    try:
        from scientra.pdf_data_assets.supplementary_entity_comparator import SupplementaryEntityComparator
        comparator = SupplementaryEntityComparator()
        result = comparator.compare(query, entity_type=entity_type, top_k=min(top_k, 100))
        if paper_id:
            result["records"] = [r for r in result["records"] if r.get("paper_id") == paper_id]
            result["total_matches"] = len(result["records"])
            result["unique_papers_count"] = len({r.get("paper_id") for r in result["records"]})
    except ImportError:
        return {"query_entity": query, "total_matches": 0, "records": [],
                "comparability_warning": "Comparator not available."}
    return result
