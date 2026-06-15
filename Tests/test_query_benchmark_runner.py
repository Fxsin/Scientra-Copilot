"""Tests for P6.5 query_benchmark_runner."""

import tempfile
from pathlib import Path

from scientra.benchmark.query_benchmark_runner import run_query_benchmark, FIXED_QUERIES


class TestQueryBenchmarkRunner:
    def test_run_no_crash(self):
        """Query benchmark should not crash even without LanceDB."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_query_benchmark(root)
            assert result.category == "query"
            assert len(result.query_metrics) == len(FIXED_QUERIES)

    def test_missing_lancedb_no_crash(self):
        """Missing LanceDB should produce warning, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_query_benchmark(root)
            # Should have query metrics for all fixed queries
            for qm in result.query_metrics:
                assert qm.total_duration_ms >= 0
                # Vector search may warn
                assert qm.success is True

    def test_all_fixed_queries_benchmarked(self):
        """All 6 fixed queries should be benchmarked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_query_benchmark(root)
            queries = [qm.query for qm in result.query_metrics]
            for q in FIXED_QUERIES:
                assert q in queries

    def test_latency_breakdown_structure(self):
        """Each query metric should have all phase durations."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_query_benchmark(root)
            for qm in result.query_metrics:
                assert hasattr(qm, "keyword_duration_ms")
                assert hasattr(qm, "vector_duration_ms")
                assert hasattr(qm, "graph_duration_ms")
                assert hasattr(qm, "merge_duration_ms")
