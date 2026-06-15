import pytest
from scientra.agents.research_agent.agent_tool_registry import get_tool, list_tools

class TestRegistry:
    def test_list_tools(self):
        tools = list_tools()
        assert "cross_asset_query" in tools; assert "unified_graph_query" in tools; assert "dataset_query" in tools
    def test_get_tool(self):
        t = get_tool("cross_asset_query")
        assert t is not None; assert t["safe_mode"] is True
    def test_missing_tool(self):
        assert get_tool("nonexistent") is None
