import pytest
from scientra.agents.research_agent.agent_answer_builder import AgentAnswerBuilder

class TestAnswerBuilder:
    def test_evidence_only(self):
        ab = AgentAnswerBuilder()
        r = ab.build("test", "literature_question", "evidence_only",
                      [{"tool_name": "test", "status": "success", "data": [{"asset_type": "evidence", "paper_id": "p1", "title": "T", "text": "txt", "source_relative_path": "test.json", "confidence": 0.5}]}], [])
        assert "answer" in r; assert len(r["evidence_references"]) >= 1
    def test_empty_results(self):
        ab = AgentAnswerBuilder()
        r = ab.build("test", "unknown", "evidence_only", [], [])
        assert "No results" in r["answer"] or "warnings" in r
