"""Dataset Quality Checker — evaluate dataset completeness and quality."""

from __future__ import annotations

from typing import Any


def check_quality(
    manifest: dict, loader_result: dict, schema: dict,
    entities: list[dict], numerics: dict,
) -> dict[str, Any]:
    """Check dataset quality."""
    warnings: list[str] = []
    issues: list[str] = []

    # Loading checks
    if loader_result.get("load_status") != "loaded":
        warnings.append("Dataset could not be loaded.")
        issues.append("load_failed")
    if loader_result.get("n_rows", 0) == 0:
        warnings.append("Dataset has no rows.")
        issues.append("empty")

    # Header checks
    headers = loader_result.get("headers", [])
    if not headers:
        warnings.append("No headers detected.")
        issues.append("no_headers")

    # Size warning
    n_rows = loader_result.get("n_rows", 0)
    if n_rows > 50000:
        warnings.append(f"Large dataset ({n_rows} rows) — profile based on sampled rows.")
        issues.append("large_dataset_sampled")

    # Entity checks
    if len(entities) == 0:
        warnings.append("No entities extracted.")
        issues.append("no_entities")

    # Numeric checks
    if len(numerics.get("numeric_columns", [])) == 0:
        warnings.append("No numeric columns detected.")
        issues.append("no_numeric")

    # Schema confidence
    if schema.get("confidence", 0) < 0.5:
        warnings.append(f"Low schema confidence ({schema.get('confidence', 0):.2f}).")
        issues.append("low_schema_confidence")

    # Source data check
    if schema.get("dataset_type") == "source_data" and not manifest.get("source_relative_path"):
        warnings.append("Source data claim but missing relative path.")

    scores = [
        0.9 if loader_result.get("load_status") == "loaded" else 0.2,
        0.9 if headers else 0.2,
        0.8 if entities else 0.3,
        0.8 if numerics.get("numeric_columns") else 0.3,
        schema.get("confidence", 0.5),
    ]
    quality_score = round(sum(scores) / len(scores), 2)

    return {
        "dataset_id": manifest.get("dataset_id", ""),
        "quality_score": quality_score,
        "warnings": warnings,
        "issues": issues,
        "overclaim_risk": "low",
    }
