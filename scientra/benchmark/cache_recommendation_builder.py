"""Cache recommendation builder for P6.5.

Analyzes benchmark results and recommends caching strategies:
  - Graph loading slow → recommend graph cache
  - Cross-asset input loading slow → recommend precomputed index
  - Dataset entity query slow → recommend entity inverted index
  - Agent tool execution slow → recommend tool result cache
"""

from __future__ import annotations

from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkRecommendation

# Thresholds in milliseconds
SLOW_MODULE_THRESHOLD_MS = 500.0
VERY_SLOW_MODULE_THRESHOLD_MS = 2_000.0
SLOW_QUERY_THRESHOLD_MS = 1_000.0
SLOW_GRAPH_THRESHOLD_MS = 200.0
SLOW_DATASET_THRESHOLD_MS = 200.0


def build_cache_recommendations(results: dict[str, BenchmarkResult]) -> list[dict[str, Any]]:
    """Build cache recommendations from benchmark results.

    Returns a list of recommendation dicts (serializable).
    """
    recommendations: list[dict[str, Any]] = []

    # Check module loading times
    mod_result = results.get("module")
    if mod_result:
        for metric in mod_result.runtime_metrics:
            if metric.duration_ms > VERY_SLOW_MODULE_THRESHOLD_MS:
                recommendations.append({
                    "category": "cache",
                    "target": metric.label,
                    "recommendation": f"Consider caching {metric.label} results — loading took {metric.duration_ms:.1f} ms.",
                    "priority": "high",
                    "evidence": {"duration_ms": metric.duration_ms, "threshold_ms": VERY_SLOW_MODULE_THRESHOLD_MS},
                })
            elif metric.duration_ms > SLOW_MODULE_THRESHOLD_MS:
                recommendations.append({
                    "category": "cache",
                    "target": metric.label,
                    "recommendation": f"Monitor {metric.label} loading speed ({metric.duration_ms:.1f} ms); may benefit from caching.",
                    "priority": "medium",
                    "evidence": {"duration_ms": metric.duration_ms, "threshold_ms": SLOW_MODULE_THRESHOLD_MS},
                })

    # Check graph loading
    graph_result = results.get("graph")
    if graph_result:
        for metric in graph_result.runtime_metrics:
            if "stats" in metric.label and metric.duration_ms > SLOW_GRAPH_THRESHOLD_MS:
                recommendations.append({
                    "category": "cache",
                    "target": "graph_stats",
                    "recommendation": "Cache graph stats in memory — loading is slow and stats change infrequently.",
                    "priority": "medium",
                    "evidence": {"duration_ms": metric.duration_ms},
                })
            if "subgraph" in metric.label and metric.duration_ms > SLOW_GRAPH_THRESHOLD_MS:
                recommendations.append({
                    "category": "cache",
                    "target": "paper_subgraphs",
                    "recommendation": "Consider LRU cache for paper subgraphs — subgraph loading is a hot path.",
                    "priority": "medium",
                    "evidence": {"duration_ms": metric.duration_ms},
                })

    # Check query latency
    query_result = results.get("query")
    if query_result:
        slow_queries = [q for q in query_result.query_metrics if q.total_duration_ms > SLOW_QUERY_THRESHOLD_MS]
        if slow_queries:
            recommendations.append({
                "category": "cache",
                "target": "query_results",
                "recommendation": f"Implement query result cache — {len(slow_queries)}/{len(query_result.query_metrics)} queries exceed {SLOW_QUERY_THRESHOLD_MS} ms.",
                "priority": "high" if len(slow_queries) > 2 else "medium",
                "evidence": {"slow_query_count": len(slow_queries), "total_queries": len(query_result.query_metrics)},
            })

        # Check vector retrieval
        for qm in query_result.query_metrics:
            if qm.vector_duration_ms > 500:
                recommendations.append({
                    "category": "cache",
                    "target": "vector_index",
                    "recommendation": f"Vector retrieval for '{qm.query}' took {qm.vector_duration_ms:.1f} ms — consider index preloading or approximate NN.",
                    "priority": "medium",
                    "evidence": {"query": qm.query, "vector_ms": qm.vector_duration_ms},
                })

    # Check dataset queries
    dataset_result = results.get("dataset")
    if dataset_result:
        for metric in dataset_result.runtime_metrics:
            if metric.duration_ms > SLOW_DATASET_THRESHOLD_MS:
                recommendations.append({
                    "category": "cache",
                    "target": metric.label,
                    "recommendation": f"Consider caching {metric.label} — took {metric.duration_ms:.1f} ms.",
                    "priority": "low",
                    "evidence": {"duration_ms": metric.duration_ms},
                })

    # Check agent tool execution
    agent_result = results.get("agent")
    if agent_result:
        for metric in agent_result.runtime_metrics:
            tool_ms = float(metric.metadata.get("tool_execution_ms", 0))
            if tool_ms > SLOW_QUERY_THRESHOLD_MS:
                recommendations.append({
                    "category": "cache",
                    "target": "agent_tool_results",
                    "recommendation": f"Cache agent tool results — tool execution for '{metric.label}' took {tool_ms:.1f} ms.",
                    "priority": "high" if tool_ms > 3000 else "medium",
                    "evidence": {"tool_ms": tool_ms, "query": metric.label},
                })

    return recommendations
