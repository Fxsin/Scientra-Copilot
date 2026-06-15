"""Tests for P6.5 dataset_benchmark_runner."""

import tempfile
from pathlib import Path

from scientra.benchmark.dataset_benchmark_runner import run_dataset_benchmark


class TestDatasetBenchmarkRunner:
    def test_run_no_crash(self):
        """Dataset benchmark should not crash with no dataset data."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_dataset_benchmark(root)
            assert result.category == "dataset"
            assert len(result.runtime_metrics) > 0

    def test_missing_dataset_warning_not_error(self):
        """Missing dataset should warn, not fail."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_dataset_benchmark(root)
            assert result.success is True
            assert result.warning_count > 0

    def test_all_metric_types_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_dataset_benchmark(root)
            labels = [m.label for m in result.runtime_metrics]
            assert any("manifest" in l for l in labels)
            assert any("card" in l for l in labels)
            assert any("entity_index" in l for l in labels)
            assert any("entity_query" in l for l in labels)
            assert any("type_query" in l for l in labels)
            assert any("comparison" in l for l in labels)
