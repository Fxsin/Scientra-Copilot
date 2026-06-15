import pytest
from scientra.release.release_schema import make_issue, make_report
class TestSchema:
    def test_issue(self): i = make_issue("P0", "T", "D"); assert i["priority"] == "P0"
    def test_report(self): r = make_report([], [], [], [], {}); assert r["passed"]; assert r["total_issues"] == 0
