import pytest
from scientra.agents.research_agent.agent_planner import plan

class TestPlanner:
    def test_dataset_question(self): assert "dataset_query" in plan("dataset_question")
    def test_claim_support(self): assert "unified_graph_query" in plan("claim_support_question") or "cross_asset_query" in plan("claim_support_question")
    def test_research_plan(self):
        tools = plan("research_plan_generation")
        assert "gap_search" in tools; assert "hypothesis_search" in tools
    def test_unknown(self): assert len(plan("unknown")) > 0
