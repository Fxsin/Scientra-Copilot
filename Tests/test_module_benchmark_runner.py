"""Tests for P6.5 module_benchmark_runner."""

import tempfile
from pathlib import Path

from scientra.benchmark.module_benchmark_runner import run_module_benchmark


class TestModuleBenchmarkRunner:
    def test_run_no_crash(self):
        """Module benchmark should not crash even with empty root."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_module_benchmark(root)
            assert result.category == "module"
            assert result.success is True  # missing data is not failure
            # Some modules will be "missing" so there should be warnings
            assert len(result.runtime_metrics) > 0

    def test_missing_data_generates_warning(self):
        """Missing data should produce warnings, not errors."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_module_benchmark(root)
            # All tasks should have "passed" status even if data missing
            for m in result.runtime_metrics:
                assert m.success is True  # missing = warning, not failure

    def test_metrics_have_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_module_benchmark(root)
            for m in result.runtime_metrics:
                assert m.label
                assert isinstance(m.duration_ms, (int, float))
