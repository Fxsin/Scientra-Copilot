"""Tests for P6.5 cache_recommendation_builder."""

from scientra.benchmark.benchmark_schema import BenchmarkResult, RuntimeMetric, QueryLatencyMetric
from scientra.benchmark.cache_recommendation_builder import build_cache_recommendations


class TestCacheRecommendationBuilder:
    def test_empty_results(self):
        recs = build_cache_recommendations({})
        assert isinstance(recs, list)

    def test_slow_module_triggers_recommendation(self):
        """A module with >500ms duration should trigger a cache recommendation."""
        slow_metric = RuntimeMetric(label="module:slow_loader", duration_ms=1200.0, success=True,
                                     metadata={"input_count": 100})
        result = BenchmarkResult(
            category="module",
            runtime_metrics=[slow_metric],
            passed=1,
        )
        recs = build_cache_recommendations({"module": result})
        assert len(recs) > 0
        assert any("slow_loader" in r["target"] for r in recs)

    def test_fast_module_no_recommendation(self):
        """A fast module should not trigger a cache recommendation."""
        fast_metric = RuntimeMetric(label="module:fast_loader", duration_ms=10.0, success=True)
        result = BenchmarkResult(
            category="module",
            runtime_metrics=[fast_metric],
            passed=1,
        )
        recs = build_cache_recommendations({"module": result})
        # No slow modules = no recommendations for modules specifically
        module_recs = [r for r in recs if r["target"] == "module:fast_loader"]
        assert len(module_recs) == 0

    def test_slow_query_triggers_recommendation(self):
        """A query >1s should trigger a recommendation."""
        qm = QueryLatencyMetric(query="slow query", total_duration_ms=2000.0, hit_count=0)
        result = BenchmarkResult(
            category="query",
            query_metrics=[qm],
            passed=1,
        )
        recs = build_cache_recommendations({"query": result})
        assert len(recs) > 0
        assert any("query_results" in r["target"] for r in recs)

    def test_graph_slow_stats_recommendation(self):
        """Slow graph stats loading should trigger recommendation."""
        m = RuntimeMetric(label="graph:stats_loading", duration_ms=500.0, success=True)
        result = BenchmarkResult(
            category="graph",
            runtime_metrics=[m],
            passed=1,
        )
        recs = build_cache_recommendations({"graph": result})
        assert len(recs) > 0
