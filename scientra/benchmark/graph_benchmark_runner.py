"""Graph benchmark runner for P6.5.

Benchmarks Unified Evidence Graph queries:
  graph stats loading, node search, paper subgraph loading,
  neighborhood query, claim support chain, gap-hypothesis chain.

Missing graph → warning, no crash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkTask, BenchmarkWarning, RuntimeMetric
from scientra.benchmark.runtime_timer import RuntimeTimer
from scientra.io.storage_layout import get_storage

V3_GRAPH_DIR = "05_Knowledge/unified_graph"


def _resolve_root() -> Path:
    return get_storage().root


def _load_graph_file(root: Path, filename: str) -> Any:
    """Load a graph JSON file. Returns data or None."""
    p = root / V3_GRAPH_DIR / filename
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_node_by_label(nodes: list[dict], label_fragment: str) -> dict | None:
    """Find a node whose label contains the given fragment."""
    for n in nodes:
        node_label = n.get("label", n.get("name", ""))
        if label_fragment.lower() in str(node_label).lower():
            return n
    return None


def run_graph_benchmark(root: Path | None = None) -> BenchmarkResult:
    """Run graph benchmark."""
    if root is None:
        root = _resolve_root()

    tasks = [
        BenchmarkTask(task_id="graph_stats", category="graph", description="Load graph stats", runner="graph_benchmark_runner"),
        BenchmarkTask(task_id="graph_nodes", category="graph", description="Load and search nodes", runner="graph_benchmark_runner"),
        BenchmarkTask(task_id="graph_subgraph", category="graph", description="Load paper subgraph", runner="graph_benchmark_runner"),
        BenchmarkTask(task_id="graph_neighborhood", category="graph", description="Neighborhood query", runner="graph_benchmark_runner"),
        BenchmarkTask(task_id="graph_support_chain", category="graph", description="Claim support chain query", runner="graph_benchmark_runner"),
        BenchmarkTask(task_id="graph_gap_chain", category="graph", description="Gap-hypothesis chain query", runner="graph_benchmark_runner"),
    ]

    metrics: list[RuntimeMetric] = []
    warnings: list[BenchmarkWarning] = []

    # 1. Graph stats loading
    t = RuntimeTimer("graph:stats_loading")
    t.start()
    stats = _load_graph_file(root, "graph_stats.json")
    if stats is None:
        t.warn("graph_stats.json not found")
        warnings.append(BenchmarkWarning(module="graph", message="graph_stats.json not found"))
        t.add_metadata("node_count", 0)
        t.add_metadata("edge_count", 0)
    else:
        t.add_metadata("node_count", stats.get("total_nodes", 0))
        t.add_metadata("edge_count", stats.get("total_edges", 0))
        t.add_metadata("paper_count", stats.get("paper_count", 0))
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 2. Node search
    t = RuntimeTimer("graph:node_search")
    t.start()
    nodes_data = _load_graph_file(root, "graph_nodes.json")
    if nodes_data is None:
        t.warn("graph_nodes.json not found")
        warnings.append(BenchmarkWarning(module="graph", message="graph_nodes.json not found"))
        t.add_metadata("total_nodes", 0)
        found_node = None
    else:
        t.add_metadata("total_nodes", len(nodes_data) if isinstance(nodes_data, list) else 0)
        if isinstance(nodes_data, list) and nodes_data:
            found_node = _find_node_by_label(nodes_data, "Vip3")
            t.add_metadata("node_found", found_node is not None)
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 3. Paper subgraph loading
    t = RuntimeTimer("graph:subgraph_loading")
    t.start()
    subgraph_dir = root / V3_GRAPH_DIR / "paper_subgraphs"
    subgraph_count = 0
    if subgraph_dir.exists():
        subgraph_files = list(subgraph_dir.glob("*.json"))
        subgraph_count = len(subgraph_files)
        if subgraph_files:
            try:
                sg = json.loads(subgraph_files[0].read_text(encoding="utf-8"))
                t.add_metadata("sample_paper_id", sg.get("paper_id", ""))
                t.add_metadata("sample_node_count", len(sg.get("nodes", [])))
            except Exception:
                pass
    t.add_metadata("subgraph_count", subgraph_count)
    if subgraph_count == 0:
        warnings.append(BenchmarkWarning(module="graph", message="No paper subgraphs found"))
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 4. Neighborhood query (find connected nodes for a sample node)
    t = RuntimeTimer("graph:neighborhood_query")
    t.start()
    edges_data = _load_graph_file(root, "graph_edges.json")
    if edges_data and nodes_data and isinstance(nodes_data, list) and nodes_data:
        sample_node_id = nodes_data[0].get("node_id", "")
        if isinstance(edges_data, list):
            neighbors = [e for e in edges_data
                         if e.get("source_id") == sample_node_id or e.get("target_id") == sample_node_id]
            t.add_metadata("neighbor_count", len(neighbors))
    else:
        t.add_metadata("neighbor_count", 0)
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 5. Claim support chain query
    t = RuntimeTimer("graph:support_chain_query")
    t.start()
    if edges_data and isinstance(edges_data, list):
        support_edges = [e for e in edges_data if "support" in str(e.get("edge_type", "")).lower()]
        t.add_metadata("support_edge_count", len(support_edges))
    else:
        t.add_metadata("support_edge_count", 0)
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 6. Gap-hypothesis chain query
    t = RuntimeTimer("graph:gap_chain_query")
    t.start()
    if edges_data and isinstance(edges_data, list):
        gap_edges = [e for e in edges_data
                     if any(kw in str(e.get("edge_type", "")).lower() for kw in ["gap", "hypothesis"])]
        t.add_metadata("gap_edge_count", len(gap_edges))
    else:
        t.add_metadata("gap_edge_count", 0)
    t.stop(success=True)
    metrics.append(t.to_metric())

    passed = sum(1 for m in metrics if m.success)
    total_ms = sum(m.duration_ms for m in metrics)

    return BenchmarkResult(
        category="graph",
        tasks=tasks,
        runtime_metrics=metrics,
        warnings=warnings,
        passed=passed,
        warning_count=len(warnings),
        failed=len(metrics) - passed,
        total_duration_ms=round(total_ms, 3),
        success=True,
    )
