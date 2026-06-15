"""Tests for P6.5 benchmark_report_builder."""

import json
import tempfile
from pathlib import Path

from scientra.benchmark.benchmark_schema import (
    BenchmarkRun, BenchmarkResult, RuntimeMetric, QueryLatencyMetric,
    LargeFileSafetyMetric,
)
from scientra.benchmark.benchmark_report_builder import (
    build_benchmark_summary, build_benchmark_report_md,
    build_module_runtime_csv, build_query_latency_csv,
    build_large_file_safety_csv, build_cache_recommendations_json,
    build_incremental_recommendations_json, build_raw_events_jsonl,
    build_all_reports,
)


class TestBenchmarkReportBuilder:
    def _make_sample_run(self) -> BenchmarkRun:
        mod_metrics = [
            RuntimeMetric(label="module:test1", duration_ms=10.0, success=True),
            RuntimeMetric(label="module:test2", duration_ms=25.0, success=True),
        ]
        q_metrics = [
            QueryLatencyMetric(query="test query", total_duration_ms=50.0,
                               keyword_duration_ms=20.0, vector_duration_ms=15.0,
                               hit_count=3),
        ]
        lf_metrics = [
            LargeFileSafetyMetric(label="synthetic_1k", row_count=1000,
                                   file_size_bytes=50000, peak_memory_category="low"),
        ]

        results = {
            "module": BenchmarkResult(category="module", runtime_metrics=mod_metrics, passed=2),
            "query": BenchmarkResult(category="query", query_metrics=q_metrics, passed=1),
            "large_file": BenchmarkResult(category="large_file", large_file_metrics=lf_metrics, passed=1),
        }

        return BenchmarkRun(
            run_id="test_run",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:00:01Z",
            total_duration_ms=1000.0,
            results=results,
            total_tasks=4,
            total_passed=4,
            total_warnings=0,
            total_failed=0,
            cache_recommendations=[{"category": "cache", "target": "test", "recommendation": "Test", "priority": "low"}],
            incremental_update_recommendations=[{"category": "incremental_update", "target": "test", "recommendation": "Test", "priority": "medium"}],
        )

    def test_build_summary_json(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_benchmark_summary(run, root)
            assert p.exists()
            data = json.loads(p.read_text(encoding="utf-8"))
            assert data["run_id"] == "test_run"
            assert data["total_tasks"] == 4

    def test_build_report_md(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_benchmark_report_md(run, root)
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert "test_run" in content
            assert "## Summary" in content

    def test_build_module_runtime_csv(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_module_runtime_csv(run, root)
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert "module,duration_ms" in content

    def test_build_query_latency_csv(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_query_latency_csv(run, root)
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert "query,total_ms" in content

    def test_build_large_file_safety_csv(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_large_file_safety_csv(run, root)
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert "label,row_count" in content

    def test_build_cache_recommendations_json(self):
        recs = [{"category": "cache", "target": "test", "recommendation": "Test it"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_cache_recommendations_json(recs, root)
            assert p.exists()
            data = json.loads(p.read_text(encoding="utf-8"))
            assert len(data) == 1

    def test_build_incremental_recommendations_json(self):
        recs = [{"category": "incremental_update", "target": "test", "recommendation": "Test it"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_incremental_recommendations_json(recs, root)
            assert p.exists()

    def test_build_raw_events_jsonl(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_raw_events_jsonl(run, root)
            assert p.exists()
            lines = p.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) >= 3  # at least 3 events

    def test_build_all_reports(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = build_all_reports(run, root)
            assert len(reports) >= 6
            assert "benchmark_summary.json" in reports
            assert "benchmark_report.md" in reports

    def test_reports_use_relative_paths(self):
        run = self._make_sample_run()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = build_all_reports(run, root)
            for path in reports.values():
                assert not path.startswith("/")  # relative
                assert not path.startswith("\\")  # not absolute Windows
    def test_partial_report_on_missing_data(self):
        """Report should generate even with missing categories."""
        run = BenchmarkRun(
            run_id="partial",
            results={},  # empty results
            total_tasks=0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = build_benchmark_report_md(run, root)
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert "partial" in content
