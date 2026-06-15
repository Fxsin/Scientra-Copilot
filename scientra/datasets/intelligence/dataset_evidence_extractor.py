"""Dataset Evidence Extractor — generate evidence from schema, entities, and numerics."""

from __future__ import annotations

import uuid
from typing import Any


def extract_evidence(
    schema: dict[str, Any], entities: list[dict], numerics: dict[str, Any],
    paper_id: str = "", dataset_id: str = "", asset_id: str = "",
) -> list[dict[str, Any]]:
    """Generate dataset-level evidence items."""
    evidence: list[dict] = []
    pid = paper_id
    did = dataset_id
    aid = asset_id

    # 1. Entity presence evidence
    for ent in entities[:20]:
        evidence.append({
            "evidence_id": f"dsev_{uuid.uuid4().hex[:10]}",
            "paper_id": pid, "dataset_id": did, "asset_id": aid,
            "evidence_type": "entity_presence",
            "entity_text": ent.get("entity_text", ""),
            "value": None,
            "statistic": {},
            "row_reference": {"row_index": ent.get("row_index", 0)},
            "column_reference": {"column_name": ent.get("column_name", "")},
            "confidence": ent.get("confidence", 0.5),
            "grounding_source": "entity_extraction",
        })

    # 2. Differential value evidence (top hits)
    for item in numerics.get("top_positive", [])[:5]:
        evidence.append({
            "evidence_id": f"dsev_{uuid.uuid4().hex[:10]}",
            "paper_id": pid, "dataset_id": did, "asset_id": aid,
            "evidence_type": "differential_value",
            "entity_text": item.get("entity", ""),
            "value": item.get("value"),
            "statistic": {"direction": "up"},
            "row_reference": {},
            "column_reference": {},
            "confidence": 0.7,
            "grounding_source": "numeric_profile",
        })

    for item in numerics.get("top_negative", [])[:5]:
        evidence.append({
            "evidence_id": f"dsev_{uuid.uuid4().hex[:10]}",
            "paper_id": pid, "dataset_id": did, "asset_id": aid,
            "evidence_type": "differential_value",
            "entity_text": item.get("entity", ""),
            "value": item.get("value"),
            "statistic": {"direction": "down"},
            "row_reference": {},
            "column_reference": {},
            "confidence": 0.7,
            "grounding_source": "numeric_profile",
        })

    # 3. Statistical significance evidence
    thresholds = numerics.get("thresholds_detected", {})
    if thresholds.get("p_lt_0.05", 0) > 0:
        evidence.append({
            "evidence_id": f"dsev_{uuid.uuid4().hex[:10]}",
            "paper_id": pid, "dataset_id": did, "asset_id": aid,
            "evidence_type": "statistical_significance",
            "entity_text": "",
            "value": None,
            "statistic": {"significant_at_0.05": thresholds["p_lt_0.05"], "significant_at_0.01": thresholds.get("p_lt_0.01", 0)},
            "row_reference": {}, "column_reference": {},
            "confidence": 0.8,
            "grounding_source": "numeric_profile",
        })

    # 4. LC50 result evidence
    for nc in numerics.get("numeric_columns", []):
        if nc.get("field_type") == "lc50":
            evidence.append({
                "evidence_id": f"dsev_{uuid.uuid4().hex[:10]}",
                "paper_id": pid, "dataset_id": did, "asset_id": aid,
                "evidence_type": "lc50_result",
                "entity_text": nc.get("column_name", ""),
                "value": nc.get("mean"),
                "statistic": {"min": nc.get("min"), "max": nc.get("max")},
                "row_reference": {}, "column_reference": {"column_name": nc.get("column_name", "")},
                "confidence": 0.8,
                "grounding_source": "numeric_profile",
            })

    return evidence
