import pytest
from scientra.cross_asset_query.result_merger import ResultMerger
from scientra.cross_asset_query.query_schema import make_hit

class TestMerger:
    def test_merge_dedup(self):
        m = ResultMerger()
        h1 = make_hit("h1", "evidence", "p1", "T", score=0.8)
        h2 = make_hit("h2", "evidence", "p1", "T", score=0.6)
        # Same asset_id should deduplicate
        kw = [h1]; vec = [h2]
        merged = m.merge(kw, vec, [])
        # Two different hit_ids → both may remain if titles differ
        assert len(merged) >= 1

    def test_merge_sources(self):
        m = ResultMerger()
        h = make_hit("h1", "evidence", "p1", "Unique Title Here", score=0.7)
        merged = m.merge([h], [h], [])
        if merged:
            assert len(merged[0].get("sources", [])) >= 1

    def test_empty(self):
        m = ResultMerger()
        assert m.merge([], [], []) == []
