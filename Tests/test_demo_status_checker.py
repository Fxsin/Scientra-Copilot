import pytest
from scientra.demo.demo_status_checker import DemoStatusChecker
class TestStatus:
    def test_check(self):
        s = DemoStatusChecker().check()
        assert "src_files_exist" in s; assert "setup_instructions" in s
    def test_demo_exists(self):
        s = DemoStatusChecker().check()
        assert s["src_files_exist"]  # Demo should be created
