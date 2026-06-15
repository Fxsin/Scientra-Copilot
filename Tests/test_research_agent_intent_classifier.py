import pytest
from scientra.agents.research_agent.agent_intent_classifier import classify

class TestIntent:
    def test_dataset(self): assert classify("MAP2K4 appears in which dataset")["primary_intent"] in ("dataset_question", "entity_comparison_question")
    def test_claim_support(self): assert classify("which claims are weakly supported")["primary_intent"] == "claim_support_question"
    def test_research_plan(self): assert classify("generate a research plan for receptor mechanism")["primary_intent"] == "research_plan_generation"
    def test_gap(self): assert classify("what are the knowledge gaps")["primary_intent"] == "gap_question"
    def test_unknown(self):
        r = classify("hello")
        assert r["confidence"] > 0
