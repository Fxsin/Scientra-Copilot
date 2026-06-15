import pytest
from scientra.datasets.intelligence import DatasetIntelligenceRunner, CrossPaperDatasetIndexer, DatasetComparisonEngine

class TestRunner:
    def test_empty(self):
        r = DatasetIntelligenceRunner().run("nonexistent")
        assert r.get("success") or "message" in r

    def test_get_cards_empty(self):
        r = DatasetIntelligenceRunner().get_cards("nonexistent")
        assert r["available"] is False

    def test_no_db_v2(self):
        assert "DB/DB_v2" not in str(DatasetIntelligenceRunner().root)

class TestIndexer:
    def test_query_empty(self):
        idx = CrossPaperDatasetIndexer()
        r = idx.query_entity("NOTEXIST")
        assert r == []

class TestComparison:
    def test_compare_empty(self):
        eng = DatasetComparisonEngine()
        r = eng.compare_entity("NONEXISTENT")
        assert r["found_in_papers"] == 0
