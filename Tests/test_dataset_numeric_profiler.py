import pytest
from scientra.datasets.intelligence.dataset_numeric_profiler import profile_numerics

class TestNumeric:
    def test_profile(self):
        headers = ["Gene", "log2FC", "pvalue", "padj"]
        rows = [["A", "2.5", "0.001", "0.01"], ["B", "-1.3", "0.05", "0.10"]]
        r = profile_numerics(headers, rows)
        assert len(r["numeric_columns"]) >= 1

    def test_top_hits(self):
        headers = ["Gene", "log2FC", "pvalue"]
        rows = [["MAP2K4", "3.5", "0.001"], ["GeneB", "-2.1", "0.05"], ["GeneC", "1.0", "0.5"]]
        r = profile_numerics(headers, rows)
        assert len(r.get("top_positive", [])) > 0 or len(r.get("top_negative", [])) > 0
