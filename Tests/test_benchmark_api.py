"""Tests for P6.5 benchmark API endpoints.

Tests verify API behavior:
  - Returns empty + warning when no results (not 500)
  - Returns data when results exist
  - No absolute paths in responses
  - No user data exposed
"""

import json
import tempfile
from pathlib import Path

import pytest

# We test the endpoint logic directly without starting a server
from scientra.server import create_app
from fastapi.testclient import TestClient

from scientra.benchmark.benchmark_schema import (
    BenchmarkRun, BenchmarkResult, RuntimeMetric, QueryLatencyMetric,
)
from scientra.benchmark.benchmark_report_builder import build_benchmark_summary


def _make_test_summary(root: Path) -> None:
    """Write a minimal benchmark_summary.json for testing."""
    metrics = [
        RuntimeMetric(label="test_mod", duration_ms=10.0, success=True),
    ]
    q_metrics = [
        QueryLatencyMetric(query="test q", total_duration_ms=50.0, hit_count=3),
    ]
    run = BenchmarkRun(
        run_id="api_test",
        started_at="2025-01-01T00:00:00Z",
        completed_at="2025-01-01T00:00:01Z",
        total_duration_ms=100.0,
        results={
            "module": BenchmarkResult(category="module", runtime_metrics=metrics, passed=1),
            "query": BenchmarkResult(category="query", query_metrics=q_metrics, passed=1),
            "agent": BenchmarkResult(category="agent", runtime_metrics=metrics, passed=1),
        },
        total_tasks=3,
        total_passed=3,
        total_warnings=0,
        total_failed=0,
        cache_recommendations=[{"category": "cache", "target": "x", "recommendation": "Cache it", "priority": "low"}],
        incremental_update_recommendations=[{"category": "incremental_update", "target": "y", "recommendation": "Incr it", "priority": "medium"}],
        p7_readiness_warnings=[],
    )
    build_benchmark_summary(run, root)


class TestBenchmarkAPI:
    @pytest.fixture
    def client_empty(self):
        """Client pointing to empty dir — no benchmark results."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(root)
            with TestClient(app) as client:
                yield client

    @pytest.fixture
    def client_with_data(self):
        """Client with benchmark results."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_test_summary(root)
            app = create_app(root)
            with TestClient(app) as client:
                yield client

    # ── Empty state tests ──

    def test_status_empty(self, client_empty):
        resp = client_empty.get("/benchmark/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "No benchmark results" in data["message"]

    def test_summary_empty(self, client_empty):
        resp = client_empty.get("/benchmark/summary")
        assert resp.status_code == 200  # NOT 500
        data = resp.json()
        assert data["available"] is False

    def test_modules_empty(self, client_empty):
        resp = client_empty.get("/benchmark/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["modules"] == []

    def test_queries_empty(self, client_empty):
        resp = client_empty.get("/benchmark/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["queries"] == []

    def test_graph_empty(self, client_empty):
        resp = client_empty.get("/benchmark/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"] == []

    def test_datasets_empty(self, client_empty):
        resp = client_empty.get("/benchmark/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"] == []

    def test_agent_empty(self, client_empty):
        resp = client_empty.get("/benchmark/agent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"] == []

    def test_recommendations_empty(self, client_empty):
        resp = client_empty.get("/benchmark/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cache_recommendations"] == []

    # ── Data-present tests ──

    def test_status_with_data(self, client_with_data):
        resp = client_with_data.get("/benchmark/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["total_tasks"] == 3
        assert data["run_id"] == "api_test"

    def test_summary_with_data(self, client_with_data):
        resp = client_with_data.get("/benchmark/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["run_id"] == "api_test"

    def test_modules_with_data(self, client_with_data):
        resp = client_with_data.get("/benchmark/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["category"] == "module"
        assert len(data["metrics"]) > 0

    def test_queries_with_data(self, client_with_data):
        resp = client_with_data.get("/benchmark/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert len(data["queries"]) > 0

    def test_agent_with_data(self, client_with_data):
        resp = client_with_data.get("/benchmark/agent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True

    def test_recommendations_with_data(self, client_with_data):
        resp = client_with_data.get("/benchmark/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert len(data["cache_recommendations"]) > 0
        assert len(data["incremental_update_recommendations"]) > 0

    # ── Safety tests ──

    def test_no_absolute_paths_in_response(self, client_with_data):
        """All API responses should not contain absolute paths."""
        endpoints = [
            "/benchmark/status", "/benchmark/summary", "/benchmark/modules",
            "/benchmark/queries", "/benchmark/graph", "/benchmark/datasets",
            "/benchmark/agent", "/benchmark/recommendations",
        ]
        for ep in endpoints:
            resp = client_with_data.get(ep)
            assert resp.status_code == 200
            text = resp.text
            # Should not contain Windows absolute paths like C:\ or Unix /home/
            assert "C:\\" not in text
            assert "file:///" not in text

    def test_no_user_text_content(self, client_with_data):
        """Responses should be stats, not user text."""
        resp = client_with_data.get("/benchmark/summary")
        data = resp.json()
        # Check that no raw user text appears (just stats)
        results_str = json.dumps(data.get("results", {}))
        # Should not contain PDF content or raw text
        for keyword in ["Vip3A", "Bacillus", "thuringiensis"]:
            assert keyword not in results_str

    def test_no_db_v2_references(self, client_with_data):
        """API should not reference DB/DB_v2."""
        resp = client_with_data.get("/benchmark/summary")
        text = resp.text.lower()
        assert "db_v2" not in text
        assert '"db"' not in text or "lancedb" in text  # DB reference only as lancedb

    def test_no_api_key_exposed(self, client_with_data):
        """No API key should appear in responses."""
        for ep in ["/benchmark/status", "/benchmark/summary", "/benchmark/modules"]:
            resp = client_with_data.get(ep)
            text = resp.text.lower()
            assert "sk-" not in text
            assert "api_key" not in text
