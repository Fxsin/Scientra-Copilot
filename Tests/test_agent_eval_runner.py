import pytest
from scientra.validation.e2e.agent_eval_runner import AgentEvalRunner
class TestAgent:
    def test_run(self):
        r = AgentEvalRunner().run()
        assert "results" in r
