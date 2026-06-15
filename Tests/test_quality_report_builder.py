import tempfile, json
from pathlib import Path
import pytest
from scientra.validation.e2e.quality_report_builder import QualityReportBuilder
class TestReport:
    def test_build(self):
        d = tempfile.mkdtemp()
        b = QualityReportBuilder(d)
        paths = b.build_all({"test": 1}, [{"paper_id": "p1", "completion_score": 0.5, "warnings": []}],
                            {"v3_compliant": True, "db_v2_clean": True, "warnings": []},
                            {"all_modules_ok": True, "all_scripts_exist": True, "modules": {}, "scripts": {}},
                            {"passed": 5, "total_queries": 5, "results": []},
                            {"passed": 3, "total_queries": 3, "results": []},
                            {"P0": [], "P1": [], "P2": [], "P3": []})
        assert len(paths) >= 2
        assert (Path(d) / "e2e_validation_summary.json").exists()
