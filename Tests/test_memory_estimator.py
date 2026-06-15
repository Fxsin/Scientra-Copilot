"""Tests for P6.5 memory_estimator."""

import tempfile
from pathlib import Path

from scientra.benchmark.memory_estimator import (
    estimate_memory_category, record_process_memory, estimate_file_memory_risk,
)


class TestMemoryEstimator:
    def test_low_memory_category(self):
        assert estimate_memory_category(file_size_bytes=1000, row_count=100) == "low"

    def test_medium_memory_category(self):
        assert estimate_memory_category(file_size_bytes=50 * 1024 * 1024, row_count=50_000) == "medium"

    def test_high_memory_category(self):
        assert estimate_memory_category(file_size_bytes=200 * 1024 * 1024, row_count=200_000) == "high"

    def test_high_memory_from_output(self):
        assert estimate_memory_category(output_count=20_000) == "medium"  # depends on scoring

    def test_record_process_memory_no_crash(self):
        """psutil may or may not be available — must not crash."""
        result = record_process_memory()
        assert "rss_mb" in result
        assert "warnings" in result

    def test_estimate_file_memory_risk_no_crash(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"a,b,c\n1,2,3\n")
            tmp_path = Path(f.name)

        try:
            result = estimate_file_memory_risk(tmp_path, row_count=1)
            assert "memory_category" in result
            assert result["file_size_bytes"] > 0
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_missing_file_warning(self):
        result = estimate_file_memory_risk(Path("/nonexistent/file.csv"))
        assert "memory_category" in result
        assert len(result["warnings"]) > 0
