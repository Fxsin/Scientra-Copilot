"""Tests for Table Schema Inferer."""

import pytest
from scientra.assets.table_intelligence.table_schema_inferer import infer_table_schema


class TestDifferentialExpression:
    def test_log2fc_padj(self):
        result = infer_table_schema(
            ["Gene", "log2FC", "padj", "pvalue", "baseMean"],
            "Differentially expressed genes after treatment.",
        )
        assert result["table_type"] == "differential_expression"
        assert result["confidence"] > 0.6

    def test_fold_change_pvalue(self):
        result = infer_table_schema(
            ["Gene Symbol", "fold change", "p value", "FDR"],
            "DE analysis results.",
        )
        assert result["table_type"] == "differential_expression"


class TestBioassay:
    def test_lc50_mortality(self):
        result = infer_table_schema(
            ["Concentration", "Mortality", "Corrected Mortality", "LC50"],
            "LC50 determination for Cry toxin.",
        )
        assert result["table_type"] in ("lc50_table", "bioassay_table")

    def test_bioassay_headers(self):
        result = infer_table_schema(
            ["Treatment", "Dose", "Replicate", "Total", "Dead", "Mortality %"],
        )
        assert result["table_type"] == "bioassay_table"


class TestPrimer:
    def test_primer_table(self):
        result = infer_table_schema(
            ["Primer Name", "Sequence (5'-3')", "Product Size", "Tm", "Target Gene"],
        )
        assert result["table_type"] == "primer_table"
        assert result["confidence"] > 0.6

    def test_fwd_rev(self):
        result = infer_table_schema(
            ["Gene", "Forward", "Reverse", "Amplicon"],
        )
        assert result["table_type"] == "primer_table"


class TestSampleMetadata:
    def test_sample_metadata(self):
        result = infer_table_schema(
            ["Sample ID", "Treatment", "Condition", "Replicate", "Tissue"],
        )
        assert result["table_type"] == "sample_metadata"


class TestStatisticalResult:
    def test_statistical(self):
        result = infer_table_schema(
            ["Test", "Statistic", "p-value", "Effect Size", "df"],
        )
        assert result["table_type"] == "statistical_result"


class TestUnknown:
    def test_empty(self):
        result = infer_table_schema([], "")
        assert result["table_type"] == "unknown"

    def test_vague(self):
        result = infer_table_schema(["A", "B", "C"], "")
        assert result["table_type"] == "unknown"


class TestKeyColumns:
    def test_diff_expr_key_columns(self):
        result = infer_table_schema(
            ["Gene", "log2FC", "padj", "pvalue"],
            "Differential expression results.",
        )
        assert "log2fc" in result.get("key_columns", {}) or "padj" in result.get("key_columns", {})
