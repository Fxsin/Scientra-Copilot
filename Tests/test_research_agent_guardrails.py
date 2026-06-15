import pytest
from scientra.agents.research_agent.agent_guardrails import AgentGuardrails

class TestGuardrails:
    def test_clean(self):
        g = AgentGuardrails()
        r = g.check("Simple answer.", [{"ref_id": "r1", "source_relative_path": "test.json", "provenance": {}}], [])
        assert r["passed"]
    def test_overclaim(self):
        g = AgentGuardrails()
        r = g.check("This definitively proves the novel breakthrough.", [], [])
        assert not r["passed"] or r["risk_level"] != "low"
    def test_no_refs(self):
        g = AgentGuardrails()
        r = g.check("Answer.", [], [])
        assert "no_references" in r["issues"]
