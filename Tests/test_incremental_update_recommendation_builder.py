"""Tests for P6.5 incremental_update_recommendation_builder."""

from scientra.benchmark.benchmark_schema import BenchmarkResult, RuntimeMetric
from scientra.benchmark.incremental_update_recommendation_builder import (
    build_incremental_update_recommendations,
)


class TestIncrementalUpdateRecommendationBuilder:
    def test_empty_results(self):
        recs = build_incremental_update_recommendations({})
        assert isinstance(recs, list)
        # Always has at least supplementary_chunks and cross_paper_indexes
        assert len(recs) >= 2

    def test_subgraph_identifies_per_paper_candidate(self):
        """Small subgraph node count should trigger per-paper incremental rec."""
        m = RuntimeMetric(label="graph:subgraph_loading", duration_ms=10.0, success=True,
                           metadata={"subgraph_count": 10})
        result = BenchmarkResult(
            category="graph",
            runtime_metrics=[m],
            passed=1,
        )
        recs = build_incremental_update_recommendations({"graph": result})
        assert any("subgraph" in r["target"] for r in recs)

    def test_entity_index_incremental_candidate(self):
        """Small entity index should be identified as incremental candidate."""
        m = RuntimeMetric(label="module:P5.3_dataset_entity_index", duration_ms=5.0, success=True,
                           metadata={"input_count": 50})
        result = BenchmarkResult(
            category="module",
            runtime_metrics=[m],
            passed=1,
        )
        recs = build_incremental_update_recommendations({"module": result})
        assert any("entity_index" in r["target"] for r in recs)

    def test_always_recommends_supplementary_and_cross_paper(self):
        """Supplementary chunks and cross-paper indexes always recommended."""
        recs = build_incremental_update_recommendations({})
        targets = [r["target"] for r in recs]
        assert "supplementary_chunks" in targets
        assert "cross_paper_indexes" in targets
