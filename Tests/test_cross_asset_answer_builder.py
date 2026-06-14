import pytest
from scientra.cross_asset_query.cross_asset_answer_builder import CrossAssetAnswerBuilder
from scientra.cross_asset_query.query_schema import make_hit

class TestAnswer:
    def test_build_answer(self):
        ab = CrossAssetAnswerBuilder()
        hits = [make_hit("h1", "evidence", "p1", "MAP2K4 expression", score=0.8),
                make_hit("h2", "figure", "p1", "Figure 1", score=0.6)]
        result = ab.build_answer("MAP2K4", hits, [], "entity_search")
        assert "answer" in result
        assert len(result["citations"]) >= 1

    def test_no_results(self):
        ab = CrossAssetAnswerBuilder()
        result = ab.build_answer("xyz", [], [], "unknown")
        assert "No results" in result["answer"]
        assert len(result["warnings"]) >= 1

    def test_no_llm_called(self):
        ab = CrossAssetAnswerBuilder()
        result = ab.build_answer("test", [make_hit("h1", "evidence", "p1")], [], "evidence_search")
        assert "answer" in result
        # Evidence-only mode — no LLM involved
