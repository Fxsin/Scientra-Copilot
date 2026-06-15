import pytest
from scientra.agents.research_agent.agent_schema import make_request, make_response, make_tool_call, make_evidence_ref

class TestSchema:
    def test_make_request(self):
        r = make_request("test query", mode="evidence_only")
        assert r["query"] == "test query"; assert r["mode"] == "evidence_only"
    def test_make_response(self):
        r = make_response("q", "intent", "evidence_only", "answer")
        assert r["answer"] == "answer"; assert r["evidence_references"] == []
    def test_make_tool_call(self):
        t = make_tool_call("test_tool")
        assert t["tool_name"] == "test_tool"; assert t["status"] == "pending"
    def test_make_evidence_ref(self):
        e = make_evidence_ref("r1", "evidence", "p1", "T")
        assert e["ref_id"] == "r1"; assert e["source_type"] == "evidence"
