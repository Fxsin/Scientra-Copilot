import pytest
from scientra.datasets.intelligence.dataset_schema_inferer import infer_schema

class TestSchema:
    def test_differential_expression(self):
        r = infer_schema(["Gene", "log2FC", "pvalue", "padj"])
        assert r["dataset_type"] == "differential_expression"; assert r["confidence"] > 0.6

    def test_lc50(self):
        r = infer_schema(["Compound", "LC50", "95% CI", "Slope"])
        assert r["dataset_type"] == "lc50"

    def test_primer(self):
        r = infer_schema(["Primer Name", "Sequence", "Product Size", "Tm"])
        assert r["dataset_type"] == "primer_table"

    def test_pathway(self):
        r = infer_schema(["Pathway", "Gene Ratio", "pvalue", "FDR", "Enrichment Score"])
        assert r["dataset_type"] == "pathway_enrichment"

    def test_unknown(self):
        r = infer_schema(["A", "B", "C"])
        assert r["dataset_type"] == "unknown"
