import pytest
from scientra.validation.e2e.query_eval_runner import QueryEvalRunner
class TestQuery:
    def test_run(self):
        r = QueryEvalRunner().run()
        assert "results" in r; assert "total_queries" in r
