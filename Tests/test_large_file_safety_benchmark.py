"""Tests for P6.5 large_file_safety_benchmark."""

import tempfile
from pathlib import Path

from scientra.benchmark.large_file_safety_benchmark import (
    run_large_file_benchmark, _generate_synthetic_csv,
)


class TestLargeFileSafetyBenchmark:
    def test_generate_1k_csv(self):
        """Can generate a 1k row synthetic CSV."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fp = _generate_synthetic_csv(root, 1000)
            assert fp.exists()
            assert fp.suffix == ".csv"
            # Count lines
            lines = fp.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 1001  # header + 1000 rows

    def test_run_1k_no_crash(self):
        """1k row benchmark should not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_large_file_benchmark(root, max_rows=1000)
            assert result.category == "large_file"
            assert len(result.large_file_metrics) == 1

    def test_run_does_not_use_user_data(self):
        """Benchmark generates synthetic data only — no user data accessed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_large_file_benchmark(root, max_rows=1000)
            for lfm in result.large_file_metrics:
                assert "synthetic" in lfm.label

    def test_10k_rows(self):
        """10k row benchmark."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_large_file_benchmark(root, max_rows=10000)
            assert len(result.large_file_metrics) == 2  # 1k + 10k

    def test_100k_rows(self):
        """100k row benchmark."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_large_file_benchmark(root, max_rows=100000)
            assert len(result.large_file_metrics) == 3  # 1k + 10k + 100k

    def test_memory_category_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_large_file_benchmark(root, max_rows=1000)
            for lfm in result.large_file_metrics:
                assert lfm.peak_memory_category in ("low", "medium", "high")

    def test_cleanup_on_no_keep(self):
        """Synthetic files should be cleaned up when keep_files=False."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_large_file_benchmark(root, max_rows=1000, keep_files=False)
            # Check that files don't exist in synthetic dir
            syn_dir = root / "10_System/benchmarks/synthetic_large_files"
            csv_files = list(syn_dir.glob("*.csv")) if syn_dir.exists() else []
            assert len(csv_files) == 0
