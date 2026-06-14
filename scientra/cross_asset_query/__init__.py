"""P5.2 Cross-Asset Query Engine.

Query across evidence, figures, tables, supplementary, graph, gaps, hypotheses.
"""

from scientra.cross_asset_query.query_schema import make_query, make_hit, make_search_result
from scientra.cross_asset_query.query_intent_classifier import classify_intent
from scientra.cross_asset_query.cross_asset_input_loader import CrossAssetInputLoader
from scientra.cross_asset_query.keyword_retriever import KeywordRetriever
from scientra.cross_asset_query.vector_retriever import VectorRetriever
from scientra.cross_asset_query.graph_retriever import GraphRetriever
from scientra.cross_asset_query.result_merger import ResultMerger
from scientra.cross_asset_query.cross_asset_ranker import CrossAssetRanker
from scientra.cross_asset_query.support_chain_builder import SupportChainBuilder
from scientra.cross_asset_query.cross_asset_answer_builder import CrossAssetAnswerBuilder
from scientra.cross_asset_query.cross_asset_query_engine import CrossAssetQueryEngine

__all__ = [
    "make_query", "make_hit", "make_search_result",
    "classify_intent", "CrossAssetInputLoader",
    "KeywordRetriever", "VectorRetriever", "GraphRetriever",
    "ResultMerger", "CrossAssetRanker", "SupportChainBuilder",
    "CrossAssetAnswerBuilder", "CrossAssetQueryEngine",
]
