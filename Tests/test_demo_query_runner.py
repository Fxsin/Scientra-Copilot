import pytest
from scientra.demo.demo_query_runner import DemoQueryRunner
class TestQueries:
    def test_run(self): r = DemoQueryRunner().run(use_agent=False); assert "results" in r
