import pytest
from scientra.validation.dashboard.dashboard_aggregator import DashboardAggregator
class TestAggregator:
    def test_aggregate(self):
        data = {"paper_details": [{"paper_id": "p1", "completion_score": 0.8, "warnings": [], "has_evidence": True, "has_figure_intelligence": False}],
                "recommendations": {"P0": [], "P1": [{"title": "test"}], "P2": [], "P3": []},
                "modules": {"all_modules_ok": True}, "storage": {"v3_compliant": True},
                "query_eval": {"passed": 5}, "agent_eval": {"passed": 3}}
        r = DashboardAggregator().aggregate(data)
        assert r["summary"]["total_papers"] == 1; assert len(r["pipeline_health"]) == 11
