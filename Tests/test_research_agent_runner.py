import pytest, json
from scientra.agents.research_agent import ResearchAgentRunner, make_request

class TestRunner:
    def test_evidence_only(self):
        runner = ResearchAgentRunner()
        r = runner.ask(make_request("MAP2K4 expression", mode="evidence_only", top_k=5))
        assert "answer" in r; assert r["mode"] == "evidence_only"
    def test_no_graph(self):
        r = ResearchAgentRunner().ask(make_request("test", use_graph=False, use_cross_asset=False, use_dataset=False, top_k=3))
        assert "answer" in r
    def test_return_trace(self):
        r = ResearchAgentRunner().ask(make_request("test", return_trace=True, top_k=3))
        assert "trace_id" in r or "answer" in r
    def test_json_serializable(self):
        r = ResearchAgentRunner().ask(make_request("test", top_k=3))
        j = json.dumps(r, ensure_ascii=False)
        assert isinstance(j, str)
    def test_no_db_v2(self):
        assert "DB/DB_v2" not in str(ResearchAgentRunner().root)
