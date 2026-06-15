import pytest
from scientra.validation.dashboard.dashboard_schema import make_summary, make_pipeline_health
class TestSchema:
    def test_summary(self):
        s = make_summary(total_papers=50, completed=30, warned=15, p0=2, p1=5)
        assert s["total_papers"] == 50; assert s["p0_count"] == 2
    def test_pipeline_health(self):
        h = make_pipeline_health("Evidence", 50, 30)
        assert h["stage"] == "Evidence"; assert h["completion_pct"] == 60.0
