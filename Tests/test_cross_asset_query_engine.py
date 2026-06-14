import pytest
from scientra.cross_asset_query import CrossAssetQueryEngine, make_query

class TestEngine:
    def test_query_no_crash(self):
        engine = CrossAssetQueryEngine()
        q = make_query("MAP2K4 expression", top_k=5)
        result = engine.query(q)
        assert "query" in result
        assert "hits" in result
        assert "grouped_hits" in result
        assert "stats" in result

    def test_query_with_graph(self):
        engine = CrossAssetQueryEngine()
        q = make_query("Vip3Aa receptor", use_graph=True, use_vector=False)
        result = engine.query(q)
        assert isinstance(result["hits"], list)

    def test_no_llm_used(self):
        engine = CrossAssetQueryEngine()
        q = make_query("test", use_llm=False)
        result = engine.query(q)
        assert result["mode"] == "evidence_only"
