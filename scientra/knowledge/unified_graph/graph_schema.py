"""Unified Evidence Graph Schema — defines node/edge types and structures."""

from __future__ import annotations

from typing import Any

NODE_TYPES = [
    "paper", "evidence", "claim", "method", "entity",
    "figure", "table", "supplementary", "dataset",
    "gap", "hypothesis", "chunk", "section", "asset",
]

EDGE_TYPES = [
    "paper_has_evidence", "paper_has_figure", "paper_has_table",
    "paper_has_supplementary", "evidence_supports_claim",
    "evidence_uses_method", "evidence_mentions_entity",
    "evidence_linked_to_figure", "evidence_linked_to_table",
    "evidence_linked_to_supplementary",
    "figure_supports_claim", "table_supports_claim",
    "supplementary_supports_claim",
    "gap_supported_by_evidence", "hypothesis_addresses_gap",
    "hypothesis_supported_by_evidence",
    "method_used_in_figure", "method_used_in_table",
    "entity_appears_in_dataset",
    "asset_cited_by_body_text", "chunk_belongs_to_asset",
    "section_belongs_to_supplementary",
]

PROVENANCE_SOURCES = [
    "evidence_extraction", "figure_intelligence", "table_intelligence",
    "supplementary_intelligence", "ai_enrichment", "asset_linking",
    "graph_construction",
]


def make_node(
    node_id: str, node_type: str, paper_id: str, title: str = "", text: str = "",
    source_ids: list[str] | None = None, source_paths: list[str] | None = None,
    metadata: dict[str, Any] | None = None, confidence: float = 0.5,
    provenance: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "paper_id": paper_id,
        "title": title,
        "text": text,
        "source_ids": source_ids or [],
        "source_paths": source_paths or [],
        "metadata": metadata or {},
        "confidence": round(confidence, 2),
        "provenance": provenance or {},
    }


def make_edge(
    edge_id: str, source_node_id: str, target_node_id: str, edge_type: str,
    paper_id: str = "", confidence: float = 0.5, evidence_source: str = "",
    provenance: dict[str, str] | None = None, metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "edge_type": edge_type,
        "paper_id": paper_id,
        "confidence": round(confidence, 2),
        "evidence_source": evidence_source,
        "provenance": provenance or {},
        "metadata": metadata or {},
    }


def prov(source_module: str, source_file: str = "", source_relative_path: str = "", created_by: str = "rule") -> dict[str, str]:
    return {
        "source_module": source_module,
        "source_file": source_file,
        "source_relative_path": source_relative_path,
        "created_by": created_by,
    }
