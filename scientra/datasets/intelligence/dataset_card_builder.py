"""Dataset Card Builder — assemble unified Dataset Card."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_card(
    manifest: dict, schema: dict, loader_result: dict,
    entities: list[dict], numerics: dict, evidence: list[dict],
    quality: dict,
) -> dict[str, Any]:
    """Build a single Dataset Card."""

    entity_types: dict[str, int] = {}
    for e in entities:
        entity_types[e.get("entity_type", "unknown")] = entity_types.get(e.get("entity_type", "unknown"), 0) + 1

    top_entities = sorted(entity_types.items(), key=lambda x: -x[1])[:5]
    top_entities_list = [{"type": t, "count": c} for t, c in top_entities]

    numeric_summary = {
        "numeric_columns": len(numerics.get("numeric_columns", [])),
        "significance_columns": len(numerics.get("statistical_columns", [])),
        "effect_size_columns": len(numerics.get("effect_size_columns", [])),
    }

    key_cols = schema.get("key_columns", {})

    return {
        "dataset_id": manifest.get("dataset_id", ""),
        "paper_id": manifest.get("paper_id", ""),
        "asset_id": manifest.get("asset_id", ""),
        "label": f"Dataset: {Path(manifest.get('source_relative_path', '')).name}",
        "title": f"{schema.get('dataset_type', 'unknown')} — {loader_result.get('n_rows', 0)}×{loader_result.get('n_columns', 0)}",
        "source_relative_path": manifest.get("source_relative_path", ""),
        "file_type": manifest.get("file_type", ""),
        "dataset_type": schema.get("dataset_type", "unknown"),
        "n_rows": loader_result.get("n_rows", 0),
        "n_columns": loader_result.get("n_columns", 0),
        "sheet_count": len(loader_result.get("sheets", [])),
        "key_columns": key_cols,
        "entity_summary": dict(top_entities),
        "numeric_summary": numeric_summary,
        "evidence_count": len(evidence),
        "top_entities": top_entities_list,
        "top_findings": [e.get("entity_text", "") for e in evidence[:5] if e.get("entity_text")],
        "linked_table_ids": [manifest.get("linked_table_id")] if manifest.get("linked_table_id") else [],
        "linked_supplementary_ids": [manifest.get("linked_supplementary_id")] if manifest.get("linked_supplementary_id") else [],
        "linked_evidence_ids": [e.get("evidence_id", "") for e in evidence[:10]],
        "quality_score": quality.get("quality_score", 0),
        "warnings": quality.get("warnings", []),
        "confidence": schema.get("confidence", 0.5),
    }


def build_cards(
    manifests: list[dict], schemas: list[dict], loader_results: list[dict],
    entities_list: list[list[dict]], numerics_list: list[dict],
    evidence_list: list[list[dict]], quality_list: list[dict],
) -> list[dict]:
    """Build all dataset cards."""
    cards = []
    for i in range(len(manifests)):
        cards.append(build_card(
            manifests[i] if i < len(manifests) else {},
            schemas[i] if i < len(schemas) else {},
            loader_results[i] if i < len(loader_results) else {},
            entities_list[i] if i < len(entities_list) else [],
            numerics_list[i] if i < len(numerics_list) else {},
            evidence_list[i] if i < len(evidence_list) else [],
            quality_list[i] if i < len(quality_list) else {},
        ))
    return cards
