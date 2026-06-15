import pytest
from scientra.agents.research_agent.agent_tool_executor import AgentToolExecutor

class TestExecutor:
    def test_unknown_tool(self):
        e = AgentToolExecutor()
        r = e.execute("nonexistent_tool", {"query": "test"})
        assert r["status"] == "skipped"
    def test_cross_asset(self):
        e = AgentToolExecutor()
        r = e.execute("cross_asset_query", {"query": "test"}, top_k=5)
        assert r["status"] in ("success", "warning")
    def test_graph_query(self):
        e = AgentToolExecutor()
        r = e.execute("unified_graph_query", {"query": "test"}, top_k=5)
        assert r["status"] in ("success", "warning")
    def test_tool_failure_no_crash(self):
        e = AgentToolExecutor()
        r = e.execute("gap_search", {"query": "test"})
        assert r["status"] in ("success", "warning", "skipped")
