"""Table Stat Detector — identify statistical fields in table headers and data.

Detects: p-value, adjusted p-value, q-value, FDR, log2FC, fold change,
mean, SD, SE, CI, n, replicate, t-test, ANOVA, correlation, survival,
LC50/LD50/IC50
"""

from __future__ import annotations

import re
from typing import Any

# ── Statistical field patterns ──

STAT_FIELD_PATTERNS: list[tuple[str, list[str], str]] = [
    # (field_name, header_patterns, category)
    ("p_value", ["p value", "p-value", "pvalue", "p val", "p_val", "raw p", "unadjusted p"], "significance"),
    ("adjusted_p_value", ["padj", "p adj", "p_adj", "adjusted p", "adjusted p-value", "fdr adjusted p", "bonferroni", "bh adjusted"], "significance"),
    ("q_value", ["q value", "q-value", "qvalue", "q val", "storey q"], "significance"),
    ("fdr", ["fdr", "false discovery rate", "bh fdr"], "significance"),
    ("log2FC", ["log2fc", "log2 fc", "log2 fold", "logfc", "log fc", "l2fc", "log2(fc)", "log2 fold change"], "effect_size"),
    ("fold_change", ["fold change", "fc", "fold-change", "foldchange", "fold enrichment", "ratio"], "effect_size"),
    ("mean", ["mean", "average", "avg", "arithmetic mean", "geometric mean"], "descriptive"),
    ("sd", ["sd", "std dev", "standard deviation", "stdev", "std"], "descriptive"),
    ("se", ["se", "sem", "std err", "standard error", "std error", "standard error of mean"], "descriptive"),
    ("ci", ["ci", "confidence interval", "95% ci", "95% confidence", "lower ci", "upper ci", "lcl", "ucl"], "descriptive"),
    ("n", ["n", "sample size", "n per group", "n total", "number", "count", "replicates"], "descriptive"),
    ("replicate", ["replicate", "rep", "bio rep", "tech rep", "biological replicate", "technical replicate"], "descriptive"),
    ("t_test", ["t test", "t-test", "t statistic", "t stat", "student t", "welch t", "paired t"], "test"),
    ("anova", ["anova", "f test", "f-test", "f statistic", "f value", "f ratio", "one-way", "two-way", "kruskal", "friedman"], "test"),
    ("correlation", ["correlation", "pearson", "spearman", "kendall", "r value", "r squared", "r2", "rho", "tau", "corr"], "test"),
    ("survival", ["survival", "kaplan", "meier", "hazard ratio", "hr", "log rank", "log-rank", "cox", "median survival"], "test"),
    ("lc50", ["lc50", "lc50", "ld50", "ld50", "ec50", "ec50", "ic50", "ic50", "lethal conc", "lethal dose", "effective conc"], "effect_size"),
]


def detect_statistical_fields(
    headers: list[str],
    sample_rows: list[list[str]] | None = None,
) -> dict[str, Any]:
    """Detect statistical fields in table structure.

    Args:
        headers: List of column header strings.
        sample_rows: Sample data rows for value-based detection.

    Returns:
        Statistics dict with detected fields and confidence.
    """
    statistical_fields: list[dict[str, Any]] = []
    significance_columns: list[str] = []
    effect_size_columns: list[str] = []
    detected_thresholds: dict[str, Any] = {}

    # Build search text from headers
    header_text = " ".join(h.lower() for h in headers)
    header_text = re.sub(r"[_\-.]", " ", header_text)

    for field_name, patterns, category in STAT_FIELD_PATTERNS:
        matched_headers = []
        for h in headers:
            h_norm = re.sub(r"[_\-.]", " ", h.lower())
            for pat in patterns:
                if pat in h_norm:
                    matched_headers.append(h)
                    break

        if matched_headers:
            field_info = {
                "field": field_name,
                "category": category,
                "matched_columns": matched_headers,
                "detection_method": "header_pattern",
            }
            statistical_fields.append(field_info)

            if category == "significance":
                significance_columns.extend(matched_headers)
            elif category == "effect_size":
                effect_size_columns.extend(matched_headers)

    # Detect significance thresholds from sample data
    if sample_rows:
        thresholds = _detect_thresholds_from_data(headers, sample_rows)
        detected_thresholds.update(thresholds)

    # Deduplicate
    significance_columns = list(dict.fromkeys(significance_columns))
    effect_size_columns = list(dict.fromkeys(effect_size_columns))

    # Confidence based on how many fields detected
    confidence = min(0.3 + 0.1 * len(statistical_fields), 0.9) if statistical_fields else 0.0

    return {
        "table_id": "",
        "statistical_fields": statistical_fields,
        "significance_columns": significance_columns,
        "effect_size_columns": effect_size_columns,
        "detected_thresholds": detected_thresholds,
        "confidence": round(confidence, 2),
    }


def _detect_thresholds_from_data(
    headers: list[str], sample_rows: list[list[str]],
) -> dict[str, Any]:
    """Detect common statistical thresholds from data values."""
    thresholds: dict[str, Any] = {}

    # Find p-value related columns
    for i, h in enumerate(headers):
        h_lower = re.sub(r"[_\-.]", " ", h.lower())
        is_p_col = any(
            kw in h_lower for kw in ["p value", "p-value", "pvalue", "padj", "fdr", "q value"]
        )

        if is_p_col and i < len(sample_rows[0]) if sample_rows else False:
            # Check if values are in [0, 1] range
            try:
                values = []
                for row in sample_rows[:20]:
                    if i < len(row):
                        try:
                            v = float(str(row[i]).strip())
                            if 0 <= v <= 1:
                                values.append(v)
                        except (ValueError, TypeError):
                            pass
                if values:
                    thresholds["p_value_range"] = [round(min(values), 6), round(max(values), 6)]
                    # Count below common thresholds
                    thresholds["p_lt_0.05_count"] = sum(1 for v in values if v < 0.05)
                    thresholds["p_lt_0.01_count"] = sum(1 for v in values if v < 0.01)
                    thresholds["p_lt_0.001_count"] = sum(1 for v in values if v < 0.001)
            except Exception:
                pass
            break

    return thresholds
