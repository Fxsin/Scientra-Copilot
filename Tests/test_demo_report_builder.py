import pytest
from scientra.demo.demo_report_builder import DemoReportBuilder
class TestReport:
    def test_build(self):
        r = DemoReportBuilder().build({"src_files_exist": True, "imported": True, "queries_run": False, "validated": False, "setup_instructions": ["run demo"]})
        assert "SYNTHETIC" in r; assert "run demo" in r
