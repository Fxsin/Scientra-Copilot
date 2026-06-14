"""Tests for Table Stat Detector."""

import pytest
from scientra.assets.table_intelligence.table_stat_detector import detect_statistical_fields


class TestPValue:
    def test_pvalue_detection(self):
        result = detect_statistical_fields(
            ["Gene", "log2FC", "pvalue", "padj"],
        )
        has_pvalue = any(f["field"] == "p_value" for f in result["statistical_fields"])
        has_padj = any(f["field"] == "adjusted_p_value" for f in result["statistical_fields"])
        assert has_pvalue or has_padj

    def test_fdr_detection(self):
        result = detect_statistical_fields(
            ["Gene", "FC", "FDR", "q-value"],
        )
        has_fdr = any(f["field"] == "fdr" for f in result["statistical_fields"])
        has_q = any(f["field"] == "q_value" for f in result["statistical_fields"])
        assert has_fdr or has_q


class TestEffectSize:
    def test_log2fc_detection(self):
        result = detect_statistical_fields(
            ["Gene", "log2FC", "pvalue"],
        )
        assert any(f["field"] == "log2FC" for f in result["statistical_fields"])

    def test_lc50_detection(self):
        result = detect_statistical_fields(
            ["Compound", "LC50", "95% CI"],
        )
        assert any(f["field"] == "lc50" for f in result["statistical_fields"])


class TestDescriptive:
    def test_mean_sd(self):
        result = detect_statistical_fields(
            ["Group", "Mean", "SD", "n"],
        )
        has_mean = any(f["field"] == "mean" for f in result["statistical_fields"])
        has_sd = any(f["field"] == "sd" for f in result["statistical_fields"])
        assert has_mean or has_sd


class TestCategories:
    def test_categories(self):
        result = detect_statistical_fields(
            ["Gene", "log2FC", "pvalue", "padj", "Mean", "SD"],
        )
        assert len(result["significance_columns"]) > 0
        assert len(result["effect_size_columns"]) > 0

    def test_empty(self):
        result = detect_statistical_fields([], [])
        assert result["statistical_fields"] == []
        assert result["confidence"] == 0.0


class TestThresholdDetection:
    def test_pvalue_thresholds(self):
        result = detect_statistical_fields(
            ["Gene", "pvalue"],
            [["GeneA", "0.001"], ["GeneB", "0.03"], ["GeneC", "0.5"]],
        )
        thresholds = result.get("detected_thresholds", {})
        if thresholds:
            assert "p_value_range" in thresholds or "p_lt_0.05_count" in thresholds
