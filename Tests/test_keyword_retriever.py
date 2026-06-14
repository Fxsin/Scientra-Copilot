import pytest
from scientra.cross_asset_query.keyword_retriever import KeywordRetriever

def _make_item(**kw):
    d = {"asset_type": "evidence", "paper_id": "p1", "asset_id": "a1", "title": "Test Title", "text": "Test text content.", "source_relative_path": "test.json"}
    d.update(kw)
    return d

class TestKeyword:
    def test_exact_match(self):
        kr = KeywordRetriever()
        assets = {"evidence": [_make_item(title="MAP2K4 expression data", text="Gene expression analysis.")]}
        hits = kr.search("MAP2K4", assets)
        assert len(hits) >= 1

    def test_partial_match(self):
        kr = KeywordRetriever()
        assets = {"evidence": [_make_item(text="We performed MAP2K4 expression analysis.")]}
        hits = kr.search("MAP2K4", assets)
        assert len(hits) >= 1

    def test_no_match(self):
        kr = KeywordRetriever()
        assets = {"evidence": [_make_item()]}
        hits = kr.search("nonexistent_term_xyz", assets)
        assert len(hits) == 0

    def test_hit_structure(self):
        kr = KeywordRetriever()
        assets = {"figure": [_make_item(asset_type="figure", title="Figure 1", text="Western blot.")]}
        hits = kr.search("western", assets)
        if hits:
            h = hits[0]
            for k in ["hit_id", "asset_type", "score", "matched_fields", "source_relative_path"]:
                assert k in h
