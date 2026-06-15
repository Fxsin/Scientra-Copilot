"""Incremental update recommendation builder for P6.5.

Analyzes benchmark results and recommends which modules are suitable
for incremental updates:
  - Dataset intelligence per paper
  - Supplementary chunks per asset
  - Graph subgraph per paper
  - Cross-paper indexes after batch import
"""

from __future__ import annotations

from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkRecommendation


def build_incremental_update_recommendations(results: dict[str, BenchmarkResult]) -> list[dict[str, Any]]:
    """Build incremental update recommendations from benchmark results.

    Returns a list of recommendation dicts (serializable).
    """
    recommendations: list[dict[str, Any]] = []

    # Check if per-module data sizes are small enough for per-paper incremental updates
    mod_result = results.get("module")
    if mod_result:
        for metric in mod_result.runtime_metrics:
            input_count = int(metric.metadata.get("input_count", 0))
            label = metric.label.lower()

            # Small per-paper data → suitable for incremental
            if "subgraph" in label and input_count < 100:
                recommendations.append({
                    "category": "incremental_update",
                    "target": "paper_subgraphs",
                    "recommendation": "Graph subgraphs can be built incrementally per paper — average node count is low.",
                    "priority": "high",
                    "evidence": {"avg_nodes": input_count},
                })

            if "entity_index" in label and input_count < 500:
                recommendations.append({
                    "category": "incremental_update",
                    "target": "entity_index",
                    "recommendation": "Entity index can be updated incrementally per paper — entity count per dataset is manageable.",
                    "priority": "high",
                    "evidence": {"entity_count": input_count},
                })

    # Dataset intelligence is inherently per-dataset/per-paper
    dataset_result = results.get("dataset")
    if dataset_result:
        for metric in dataset_result.runtime_metrics:
            if "card_loading" in metric.label:
                card_count = int(metric.metadata.get("card_count", 0))
                if card_count > 0:
                    recommendations.append({
                        "category": "incremental_update",
                        "target": "dataset_cards",
                        "recommendation": f"Dataset cards ({card_count} found) can be rebuilt incrementally as new papers are imported.",
                        "priority": "high",
                        "evidence": {"card_count": card_count},
                    })

    # Graph subgraphs are per-paper by design
    graph_result = results.get("graph")
    if graph_result:
        for metric in graph_result.runtime_metrics:
            if "subgraph" in metric.label:
                subgraph_count = int(metric.metadata.get("subgraph_count", 0))
                if subgraph_count > 0:
                    recommendations.append({
                        "category": "incremental_update",
                        "target": "graph_subgraphs",
                        "recommendation": f"Each paper has its own subgraph ({subgraph_count} total) — ideal for incremental updates after batch import.",
                        "priority": "high",
                        "evidence": {"subgraph_count": subgraph_count},
                    })

    # Always recommend incremental for supplementary chunks
    recommendations.append({
        "category": "incremental_update",
        "target": "supplementary_chunks",
        "recommendation": "Supplementary chunks can be processed per asset — chunk sizes are independent and naturally incremental.",
        "priority": "medium",
        "evidence": {},
    })

    # Cross-paper indexes after batch import
    recommendations.append({
        "category": "incremental_update",
        "target": "cross_paper_indexes",
        "recommendation": "Cross-paper indexes (embeddings, keywords) should be rebuilt after batch import, not per-paper.",
        "priority": "medium",
        "evidence": {},
    })

    # Query cache invalidation strategy
    query_result = results.get("query")
    if query_result and len(query_result.query_metrics) > 0:
        avg_ms = sum(q.total_duration_ms for q in query_result.query_metrics) / len(query_result.query_metrics)
        if avg_ms > 200:
            recommendations.append({
                "category": "incremental_update",
                "target": "query_cache_invalidation",
                "recommendation": "Consider time-based query cache invalidation — queries are moderately slow and results can be stale for short periods.",
                "priority": "low",
                "evidence": {"avg_query_ms": round(avg_ms, 1)},
            })

    return recommendations
