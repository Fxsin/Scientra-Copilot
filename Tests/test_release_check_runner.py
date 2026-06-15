import pytest
from scientra.release.release_check_runner import ReleaseCheckRunner
class TestRunner:
    def test_run(self): r = ReleaseCheckRunner().run(check_tests=False); assert "P0" in r; assert "passed" in r
    def test_fail_p0(self): r = ReleaseCheckRunner().run(check_tests=False); assert isinstance(r["passed"], bool)
    def test_no_db_v2(self): assert "DB/DB_v2" not in str(ReleaseCheckRunner().root)
