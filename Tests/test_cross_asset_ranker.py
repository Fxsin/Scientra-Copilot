import pytest
from scientra.cross_asset_query.cross_asset_ranker import CrossAssetRanker
from scientra.cross_asset_query.query_schema import make_hit

class TestRanker:
    def test_rank_sorts(self):
        r = CrossAssetRanker()
        h1 = make_hit("h1", "evidence", "p1", "A", score=0.9)
        h2 = make_hit("h2", "evidence", "p1", "B", score=0.3)
        ranked = r.rank([h2, h1])
        assert ranked[0]["score"] >= ranked[-1]["score"]

    def test_score_breakdown(self):
        r = CrossAssetRanker()
        h = make_hit("h1", "evidence", "p1", "Test", score=0.7)
        ranked = r.rank([h])
        assert "final_score" in ranked[0].get("score_breakdown", {})
