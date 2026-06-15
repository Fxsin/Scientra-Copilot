"""Tests for P6.5 graph_benchmark_runner."""

import tempfile
from pathlib import Path

from scientra.benchmark.graph_benchmark_runner import run_graph_benchmark


class TestGraphBenchmarkRunner:
    def test_run_no_crash(self):
        """Graph benchmark should not crash with no graph data."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_graph_benchmark(root)
            assert result.category == "graph"
            assert len(result.runtime_metrics) > 0

    def test_missing_graph_warning_not_error(self):
        """Missing graph should warn, not fail."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_graph_benchmark(root)
            assert result.success is True  # missing data = warning
            # Should have warnings about missing files
            assert result.warning_count > 0

    def test_metrics_cover_all_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_graph_benchmark(root)
            labels = [m.label for m in result.runtime_metrics]
            assert any("stats" in l for l in labels)
            assert any("node_search" in l for l in labels)
            assert any("subgraph" in l for l in labels)
            assert any("neighborhood" in l for l in labels)
            assert any("support_chain" in l for l in labels)
            assert any("gap_chain" in l for l in labels)
