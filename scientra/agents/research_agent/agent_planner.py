"""Agent Planner — generate tool execution plans from intent."""

from __future__ import annotations
from typing import Any

PLANS: dict[str, list[str]] = {
    "dataset_question": ["dataset_query", "cross_asset_query"],
    "entity_comparison_question": ["dataset_entity_compare", "cross_asset_query"],
    "claim_support_question": ["unified_graph_query", "cross_asset_query"],
    "figure_table_question": ["cross_asset_query"],
    "supplementary_question": ["cross_asset_query"],
    "gap_question": ["gap_search", "unified_graph_query"],
    "hypothesis_question": ["hypothesis_search", "unified_graph_query", "cross_asset_query"],
    "research_plan_generation": ["gap_search", "hypothesis_search", "opportunity_search", "unified_graph_query", "cross_asset_query", "dataset_query"],
    "method_comparison": ["cross_asset_query", "unified_graph_query"],
    "literature_question": ["cross_asset_query", "unified_graph_query"],
    "opportunity_question": ["opportunity_search", "unified_graph_query"],
    "unknown": ["cross_asset_query"],
}


def plan(intent: str) -> list[str]:
    return PLANS.get(intent, ["cross_asset_query"])
