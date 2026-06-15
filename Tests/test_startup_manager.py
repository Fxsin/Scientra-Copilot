"""Tests for P6.6.1 startup manager integration."""

import tempfile
from pathlib import Path

from scientra.environment.checks import run_all_checks, check_port
from scientra.environment.diagnostics import run_diagnostics
from scientra.environment.repair import generate_repair_report


class TestStartupIntegration:
    def test_full_check_to_diagnostics_flow(self):
        """End-to-end: checks → diagnostics → repair."""
        checks = run_all_checks()
        assert len(checks) == 12

        diag = run_diagnostics()
        assert diag["total_checks"] == 12
        assert 0 <= diag["health_score"] <= 100

        repair = generate_repair_report()
        assert repair["total_issues"] >= 0

    def test_port_check_free(self):
        """A high port should be free."""
        in_use, proc = check_port(54321)
        assert in_use is False
        assert proc is None

    def test_no_crash_on_temp_root(self):
        """All operations should work with a temp root."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checks = run_all_checks(root)
            assert len(checks) == 12

    def test_startup_does_not_require_config(self):
        """Startup manager should work without Config/ dir."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diag = run_diagnostics(root)
            assert "health_score" in diag
            # API key check will be WARN (no config file)
            api_check = [c for c in diag["checks"] if c["name"] == "API Keys"]
            assert len(api_check) == 1
            assert api_check[0]["status"] == "WARN"


class TestHealthScoreScenarios:
    def test_missing_api_key_affects_score(self):
        """Missing API key should lower the score."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diag = run_diagnostics(root)
            # API key missing should be a WARN, lowering score
            assert diag["health_score"] < 100

    def test_missing_database_affects_score(self):
        """Missing database should be a WARN, not FAIL."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checks = run_all_checks(root)
            db_check = [c for c in checks if c["name"] == "LanceDB"]
            assert len(db_check) == 1
            # Missing data = WARN, not FAIL — don't scare new users
            assert db_check[0]["status"] != "FAIL" or "not installed" in db_check[0].get("detail", "")
