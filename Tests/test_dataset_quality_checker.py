import pytest
from scientra.datasets.intelligence.dataset_quality_checker import check_quality

class TestQuality:
    def test_good(self):
        r = check_quality({"dataset_id": "ds1"}, {"load_status": "loaded", "n_rows": 100, "headers": ["G"]}, {"confidence": 0.9}, [{"e": 1}], {"numeric_columns": [{}]})
        assert r["quality_score"] > 0.5

    def test_empty(self):
        r = check_quality({"dataset_id": "ds2"}, {"load_status": "empty", "n_rows": 0, "headers": []}, {"confidence": 0.3}, [], {"numeric_columns": []})
        assert r["quality_score"] < 0.5
        assert "no_headers" in r["issues"]
