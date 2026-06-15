"""Tests for P6.6.1 health report (diagnostics + repair + report_builder)."""

import json
import tempfile
from pathlib import Path

from scientra.environment.diagnostics import run_diagnostics, compute_health_score, categorize_checks
from scientra.environment.repair import generate_repair_suggestions, generate_repair_report
from scientra.environment.report_builder import build_health_report_json, build_health_report_md, build_all_health_reports


class TestDiagnostics:
    def test_run_diagnostics(self):
        diag = run_diagnostics()
        assert "health_score" in diag
        assert "total_checks" in diag
        assert "status" in diag
        assert diag["status"] in ("healthy", "degraded", "critical")

    def test_health_score_range(self):
        diag = run_diagnostics()
        assert 0 <= diag["health_score"] <= 100

    def test_compute_health_score_all_pass(self):
        all_pass = [{"name": "a", "status": "PASS"}, {"name": "b", "status": "PASS"}]
        score = compute_health_score(all_pass)
        assert score == 100

    def test_compute_health_score_all_fail(self):
        all_fail = [{"name": "a", "status": "FAIL"}, {"name": "b", "status": "FAIL"}]
        score = compute_health_score(all_fail)
        assert score == 0

    def test_compute_health_score_mixed(self):
        mixed = [
            {"name": "a", "status": "PASS"},
            {"name": "b", "status": "WARN"},
            {"name": "c", "status": "FAIL"},
        ]
        score = compute_health_score(mixed)
        assert 0 < score < 100
        assert score == 50  # (10 + 5 + 0) / 30 * 100

    def test_categorize_checks(self):
        checks = [
            {"name": "a", "status": "PASS"},
            {"name": "b", "status": "WARN"},
            {"name": "c", "status": "FAIL"},
        ]
        cat = categorize_checks(checks)
        assert len(cat["PASS"]) == 1
        assert len(cat["WARN"]) == 1
        assert len(cat["FAIL"]) == 1


class TestRepair:
    def test_generate_repair_suggestions(self):
        suggestions = generate_repair_suggestions()
        assert isinstance(suggestions, list)
        for s in suggestions:
            assert "problem" in s
            assert "severity" in s
            assert "fix" in s

    def test_repair_report_structure(self):
        report = generate_repair_report()
        assert "total_issues" in report
        assert "critical" in report
        assert "warnings" in report
        assert "suggestions" in report


class TestReportBuilder:
    def test_build_health_report_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_health_report_json(root)
            assert p.exists()
            data = json.loads(p.read_text(encoding="utf-8"))
            assert "health_score" in data
            assert "checks" in data
            assert "repair_suggestions" in data
            assert 0 <= data["health_score"] <= 100

    def test_build_health_report_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_health_report_md(root)
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert "Health Report" in content
            assert "Health Score" in content or "health" in content.lower()

    def test_build_all_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = build_all_health_reports(root)
            assert "health_report.json" in reports
            assert "health_report.md" in reports

    def test_reports_use_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = build_all_health_reports(root)
            for path in reports.values():
                assert not path.startswith("/")
                assert not path.startswith("\\")
