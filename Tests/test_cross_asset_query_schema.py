import pytest
from scientra.cross_asset_query.query_schema import make_query, make_hit, make_search_result

class TestSchema:
    def test_make_query(self):
        q = make_query("test", top_k=10)
        assert q["query"] == "test"
        assert q["top_k"] == 10
        assert q["use_llm"] is False

    def test_make_hit(self):
        h = make_hit("h1", "evidence", "p1", "Title", "Text", score=0.8)
        assert h["hit_id"] == "h1"
        assert h["score"] == 0.8
        assert "provenance" in h

    def test_make_search_result(self):
        hits = [make_hit("h1", "evidence", "p1", "T")]
        r = make_search_result("q", "intent", "answer", hits, warnings=["w1"])
        assert "evidence" in r["grouped_hits"]
        assert r["warnings"] == ["w1"]
        assert r["mode"] == "evidence_only"
