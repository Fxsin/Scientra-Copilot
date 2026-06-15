"""Tests for P6.5 benchmark schema."""

import pytest
from scientra.benchmark.benchmark_schema import (
    BenchmarkRun, BenchmarkResult, BenchmarkTask, BenchmarkWarning,
    BenchmarkRecommendation, RuntimeMetric, QueryLatencyMetric,
    LargeFileSafetyMetric, now_iso, make_run_id,
)


class TestBenchmarkSchema:
    def test_runtime_metric_creation(self):
        m = RuntimeMetric(label="test_op", duration_ms=1.5)
        assert m.label == "test_op"
        assert m.duration_ms == 1.5
        assert m.success is True
        assert m.error is None
        assert m.warnings == []

    def test_runtime_metric_failure(self):
        m = RuntimeMetric(label="failing_op", success=False, error="Something broke")
        assert m.success is False
        assert m.error == "Something broke"

    def test_query_latency_metric_creation(self):
        q = QueryLatencyMetric(query="gene expression", total_duration_ms=100.0,
                               keyword_duration_ms=30.0, hit_count=5)
        assert q.query == "gene expression"
        assert q.hit_count == 5

    def test_large_file_safety_metric_creation(self):
        lfm = LargeFileSafetyMetric(label="synthetic_1k", row_count=1000,
                                     file_size_bytes=50000, peak_memory_category="low")
        assert lfm.row_count == 1000
        assert lfm.peak_memory_category == "low"

    def test_benchmark_warning_creation(self):
        w = BenchmarkWarning(module="graph", message="No graph data found")
        assert w.module == "graph"
        assert w.severity == "warning"

    def test_benchmark_recommendation_creation(self):
        r = BenchmarkRecommendation(category="cache", target="graph_stats",
                                     recommendation="Cache graph stats", priority="high")
        assert r.category == "cache"
        assert r.priority == "high"

    def test_benchmark_task_creation(self):
        t = BenchmarkTask(task_id="mod_1", category="module",
                          description="Load figure cards", runner="module_benchmark_runner")
        assert t.task_id == "mod_1"

    def test_benchmark_result_creation(self):
        result = BenchmarkResult(category="module", passed=5, warning_count=1, failed=0)
        assert result.category == "module"
        assert result.passed == 5

    def test_benchmark_run_creation(self):
        run = BenchmarkRun(run_id="test_001", total_tasks=10, total_passed=9, total_failed=1)
        assert run.run_id == "test_001"
        assert run.total_tasks == 10

    def test_now_iso(self):
        ts = now_iso()
        assert "T" in ts
        assert len(ts) > 10

    def test_make_run_id(self):
        rid = make_run_id()
        assert rid.startswith("bench_")
        assert len(rid) > 10
