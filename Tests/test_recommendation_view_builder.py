import pytest
from scientra.validation.dashboard.recommendation_view_builder import RecommendationViewBuilder
class TestRecs:
    def test_build(self):
        recs = {"P0": [{"title": "Module X failed", "detail": "Import error", "fix": "pip install"}], "P1": []}
        cards = RecommendationViewBuilder().build(recs)
        assert len(cards) == 1; assert cards[0]["priority"] == "P0"
