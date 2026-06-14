"""Cross-Asset Query Engine — orchestrates full query pipeline.

Stages: intent → load → keyword → vector → graph → merge → rank → chains → answer
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scientra.cross_asset_query.query_intent_classifier import classify_intent, get_target_asset_types
from scientra.cross_asset_query.cross_asset_input_loader import CrossAssetInputLoader
from scientra.cross_asset_query.keyword_retriever import KeywordRetriever
from scientra.cross_asset_query.vector_retriever import VectorRetriever
from scientra.cross_asset_query.graph_retriever import GraphRetriever
from scientra.cross_asset_query.result_merger import ResultMerger
from scientra.cross_asset_query.cross_asset_ranker import CrossAssetRanker
from scientra.cross_asset_query.support_chain_builder import SupportChainBuilder
from scientra.cross_asset_query.cross_asset_answer_builder import CrossAssetAnswerBuilder
from scientra.cross_asset_query.query_schema import make_search_result


class CrossAssetQueryEngine:
    """Orchestrate cross-asset query execution."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.warnings: list[str] = []

    def query(self, q: dict[str, Any]) -> dict[str, Any]:
        """Execute a cross-asset query.

        Args:
            q: Query dict matching CrossAssetQuery schema.

        Returns:
            CrossAssetSearchResult dict.
        """
        query_text = q.get("query", "")
        top_k = q.get("top_k", 20)
        use_vector = q.get("use_vector", True)
        use_graph = q.get("use_graph", True)
        min_confidence = q.get("min_confidence", 0.0)

        # Stage 1: Intent classification
        intent = classify_intent(query_text)

        # Stage 2: Load assets
        loader = CrossAssetInputLoader(self.root)
        assets = loader.load_all()
        self.warnings.extend(loader.warnings)

        # Stage 3: Keyword retrieval
        kw = KeywordRetriever()
        kw_hits = kw.search(query_text, assets, top_k)

        # Stage 4: Vector retrieval
        vec_hits: list[dict] = []
        if use_vector:
            vr = VectorRetriever(self.root)
            vec_hits = vr.search(query_text, top_k)
            self.warnings.extend(vr.warnings)

        # Stage 5: Graph retrieval
        graph_hits: list[dict] = []
        gr = GraphRetriever(self.root)
        if use_graph:
            graph_hits = gr.search_nodes(query_text, top_k)
            self.warnings.extend(gr.warnings)

        # Stage 6: Merge
        merger = ResultMerger()
        merged = merger.merge(kw_hits, vec_hits, graph_hits)

        # Stage 7: Rank
        ranker = CrossAssetRanker()
        ranked = ranker.rank(merged)

        # Apply confidence filter
        ranked = [h for h in ranked if h.get("confidence", 0) >= min_confidence]

        # Stage 8: Build support chains
        scb = SupportChainBuilder()
        chains = scb.build_chains(ranked[:5], gr)

        # Stage 9: Build answer
        ab = CrossAssetAnswerBuilder()
        answer_data = ab.build_answer(query_text, ranked, chains, intent["primary_intent"])
        self.warnings.extend(answer_data.get("warnings", []))

        # Assemble result
        result = make_search_result(
            query=query_text,
            resolved_intent=intent["primary_intent"],
            answer=answer_data["answer"],
            hits=ranked,
            support_chains=chains,
            warnings=self.warnings,
            stats={
                "total_hits": len(ranked),
                "keyword_hits": len(kw_hits),
                "vector_hits": len(vec_hits),
                "graph_hits": len(graph_hits),
                "intent_confidence": intent["confidence"],
            },
        )
        return result
