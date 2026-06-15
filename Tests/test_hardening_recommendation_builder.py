import pytest
from scientra.validation.e2e.hardening_recommendation_builder import HardeningRecommendationBuilder
class TestRecs:
    def test_build(self):
        r = HardeningRecommendationBuilder().build({}, [], {"v3_compliant": True, "db_v2_clean": True, "issues": [], "db_v2_hits": []},
                                                    {"all_modules_ok": True, "modules": {}, "scripts": {}},
                                                    {"passed": 5, "failed": 0}, {"passed": 3, "failed": 0})
        assert "P0" in r; assert "P3" in r  # P3 always has future recs
