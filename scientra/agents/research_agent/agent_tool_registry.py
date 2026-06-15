"""Agent Tool Registry — register available tools for the research agent."""

from __future__ import annotations
from typing import Any

TOOLS: dict[str, dict[str, Any]] = {
    "cross_asset_query": {
        "name": "cross_asset_query", "description": "Search across evidence, figures, tables, supplementary, and graph nodes",
        "input_schema": {"query": "str", "top_k": "int", "use_vector": "bool", "use_graph": "bool"},
        "safe_mode": True, "requires_llm": False,
    },
    "unified_graph_query": {
        "name": "unified_graph_query", "description": "Query the unified evidence graph for nodes, neighborhoods, and support chains",
        "input_schema": {"query": "str", "node_type": "str", "limit": "int"},
        "safe_mode": True, "requires_llm": False,
    },
    "dataset_query": {
        "name": "dataset_query", "description": "Search datasets by schema type, entity, or content",
        "input_schema": {"entity": "str", "dataset_type": "str", "limit": "int"},
        "safe_mode": True, "requires_llm": False,
    },
    "dataset_entity_compare": {
        "name": "dataset_entity_compare", "description": "Compare entity presence and values across all datasets",
        "input_schema": {"entity_text": "str"},
        "safe_mode": True, "requires_llm": False,
    },
    "evidence_search": {
        "name": "evidence_search", "description": "Search evidence chunks from parsed papers",
        "input_schema": {"query": "str", "paper_id": "str", "top_k": "int"},
        "safe_mode": True, "requires_llm": False,
    },
    "gap_search": {
        "name": "gap_search", "description": "Search research gaps from AI enrichment",
        "input_schema": {"query": "str", "paper_id": "str", "limit": "int"},
        "safe_mode": True, "requires_llm": False,
    },
    "hypothesis_search": {
        "name": "hypothesis_search", "description": "Search hypotheses from AI enrichment",
        "input_schema": {"query": "str", "paper_id": "str", "limit": "int"},
        "safe_mode": True, "requires_llm": False,
    },
    "opportunity_search": {
        "name": "opportunity_search", "description": "Search research opportunities",
        "input_schema": {"query": "str", "limit": "int"},
        "safe_mode": True, "requires_llm": False,
    },
}


def get_tool(name: str) -> dict | None:
    return TOOLS.get(name)


def list_tools() -> list[str]:
    return list(TOOLS.keys())
