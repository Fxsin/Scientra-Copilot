import pytest
from scientra.agents.research_agent.research_plan_builder import ResearchPlanBuilder

class TestPlanBuilder:
    def test_no_data(self):
        rp = ResearchPlanBuilder()
        assert rp.build("test", []) is None
    def test_with_gaps(self):
        rp = ResearchPlanBuilder()
        plan = rp.build("mechanism", [{"tool_name": "gap_search", "data": [{"asset_type": "gap", "title": "Receptor mechanism unknown"}]}])
        assert plan is not None; assert "key_gaps" in plan; assert "suggested_experiments" in plan
