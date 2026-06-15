"""Dataset Numeric Profiler — identify and profile numeric/statistical columns."""

from __future__ import annotations

import re
from typing import Any

NUMERIC_FIELD_PATTERNS = [
    ("log2FC", [r"log2fc", r"log2.fold", r"logfc", r"l2fc"], "effect_size"),
    ("fold_change", [r"fold.change", r"fc\b", r"ratio"], "effect_size"),
    ("p_value", [r"p.value", r"pvalue", r"p.val", r"raw.p"], "significance"),
    ("adjusted_p_value", [r"padj", r"p.adj", r"adjusted.p", r"fdr.adjusted"], "significance"),
    ("q_value", [r"q.value", r"qvalue", r"storey.q"], "significance"),
    ("fdr", [r"fdr", r"false.discovery"], "significance"),
    ("mean", [r"\bmean\b", r"average", r"avg\b"], "descriptive"),
    ("sd", [r"\bsd\b", r"std.dev", r"standard.deviation", r"stdev"], "descriptive"),
    ("se", [r"\bse\b", r"sem\b", r"standard.error"], "descriptive"),
    ("ci", [r"\bci\b", r"confidence.interval", r"lower.ci", r"upper.ci", r"lcl", r"ucl"], "descriptive"),
    ("n", [r"^n$", r"\bn\s+per", r"sample.size", r"replicates?", r"count"], "descriptive"),
    ("lc50", [r"lc50", r"ld50", r"ec50", r"ic50", r"lethal.conc", r"effective.conc"], "effect_size"),
    ("mortality", [r"mortality", r"percent.dead", r"%\s*dead", r"mortality.rate"], "outcome"),
    ("concentration", [r"concentration", r"\bdose\b", r"ppm", r"μg", r"mg/ml", r"μg/ml"], "descriptive"),
    ("expression", [r"expression", r"fpkm", r"rpkm", r"tpm", r"counts?\b"], "descriptive"),
]


def profile_numerics(headers: list[str], sample_rows: list[list[str]] | None = None) -> dict[str, Any]:
    """Profile numeric columns in dataset.

    Returns dict with numeric_columns, value_ranges, statistical_columns, effect_size_columns, etc.
    """
    sample_rows = sample_rows or []
    numeric_cols: list[dict] = []
    significance_cols: list[str] = []
    effect_cols: list[str] = []
    value_ranges: dict[str, dict] = {}
    thresholds: dict[str, Any] = {}
    warnings: list[str] = []

    for ci, header in enumerate(headers):
        h_lower = re.sub(r"[_\-.]", " ", header.lower())
        matched_type = None

        for fname, patterns, category in NUMERIC_FIELD_PATTERNS:
            if any(re.search(p, h_lower) for p in patterns):
                values = _extract_numeric_values(sample_rows, ci)
                if values:
                    col_info = {
                        "column_name": header, "field_type": fname,
                        "category": category, "count": len(values),
                        "min": round(min(values), 6), "max": round(max(values), 6),
                        "mean": round(sum(values) / len(values), 4) if values else 0,
                    }
                    numeric_cols.append(col_info)
                    value_ranges[header] = {"min": col_info["min"], "max": col_info["max"]}

                    if category == "significance":
                        significance_cols.append(header)
                        if fname in ("p_value", "adjusted_p_value", "fdr"):
                            thresholds["p_lt_0.05"] = sum(1 for v in values if v < 0.05)
                            thresholds["p_lt_0.01"] = sum(1 for v in values if v < 0.01)
                    elif category == "effect_size":
                        effect_cols.append(header)
                    matched_type = fname
                    break

    # Top positive/negative for effect size columns
    top_pos: list[dict] = []
    top_neg: list[dict] = []
    if sample_rows and len(sample_rows) > 0 and len(headers) > 0:
        for ci in range(min(len(headers), len(sample_rows[0]) if sample_rows else 0)):
            h_lower = re.sub(r"[_\-.]", " ", headers[ci].lower()) if ci < len(headers) else ""
            if any(re.search(p, h_lower) for p in [r"log2fc", r"logfc", r"fold.change", r"fc\b"]):
                pairs = []
                for ri, row in enumerate(sample_rows[:50]):
                    if ci < len(row):
                        try:
                            v = float(str(row[ci]))
                            label = str(row[0]) if len(row) > 0 else f"row_{ri}"
                            pairs.append((v, label))
                        except (ValueError, TypeError):
                            pass
                pairs.sort(key=lambda x: x[0], reverse=True)
                top_pos = [{"value": v, "entity": l} for v, l in pairs[:5] if v > 0]
                top_neg = [{"value": v, "entity": l} for v, l in pairs[-5:] if v < 0]
                top_neg.reverse()
                break

    return {
        "dataset_id": "", "paper_id": "", "asset_id": "",
        "numeric_columns": numeric_cols, "statistical_columns": significance_cols,
        "effect_size_columns": effect_cols, "value_ranges": value_ranges,
        "missing_rate": {}, "significant_count": thresholds,
        "top_positive": top_pos, "top_negative": top_neg,
        "thresholds_detected": thresholds, "warnings": warnings,
    }


def _extract_numeric_values(rows: list[list[str]], col_idx: int) -> list[float]:
    values = []
    for row in rows[:100]:
        if col_idx < len(row):
            try:
                v = float(str(row[col_idx]).strip().replace(",", "."))
                values.append(v)
            except (ValueError, TypeError):
                pass
    return values
