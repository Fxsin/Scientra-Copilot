import tempfile, json
from pathlib import Path
from scientra.release.release_report_builder import ReleaseReportBuilder
from scientra.release.release_schema import make_report
class TestReport:
    def test_build(self, tmp_path):
        r = make_report([], [], [], [], {"gitignore": 0})
        paths = ReleaseReportBuilder(tmp_path).build(r)
        assert "json" in paths
