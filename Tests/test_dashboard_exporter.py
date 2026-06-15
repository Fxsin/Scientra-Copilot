import tempfile, json
from pathlib import Path
import pytest
from scientra.validation.dashboard.dashboard_exporter import DashboardExporter
class TestExporter:
    def test_export_json(self):
        d = tempfile.mkdtemp()
        exporter = DashboardExporter(d)
        paths = exporter.export({"total_papers": 1, "completed_papers": 0, "average_completion_score": 0.5, "p0_count": 0, "p1_count": 0, "storage_layout_ok": True},
                                [{"stage": "Evidence", "total_papers": 1, "complete_papers": 1, "completion_pct": 100}],
                                [{"paper_id": "p1", "completion_score": 0.5}],
                                [{"priority": "P0", "title": "t", "description": "d", "suggested_action": "a"}],
                                fmt_json=True)
        assert "json" in paths
    def test_export_md(self):
        d = tempfile.mkdtemp()
        paths = DashboardExporter(d).export({"total_papers": 1, "completed_papers": 1, "average_completion_score": 1.0, "p0_count": 0, "p1_count": 0, "storage_layout_ok": True}, [], [], [], fmt_md=True)
        assert "md" in paths
