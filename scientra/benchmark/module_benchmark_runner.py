"""Module benchmark runner for P6.5.

Benchmarks loading times for key modules:
  P4.1 figure cards, P4.2 table cards, P4.3 supplementary cards,
  P5.1 unified graph, P5.2 cross-asset input, P5.3 dataset index,
  P5.4 research agent, P6.0 validation, P6.1 quality dashboard.

Missing data → warning, no crash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkTask, BenchmarkWarning, RuntimeMetric
from scientra.benchmark.runtime_timer import RuntimeTimer, timed
from scientra.io.storage_layout import get_storage


def _resolve_root() -> Path:
    """Resolve project root via storage layout."""
    return get_storage().root


def _check_file_exists(root: Path, *parts: str) -> tuple[bool, str]:
    """Check if a file or directory exists. Returns (exists, relative_path)."""
    p = root.joinpath(*parts)
    rel = "/".join(parts)
    return p.exists(), rel


def _count_json_items(file_path: Path) -> int:
    """Count items in a JSON array file."""
    try:
        import json
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data)
        return 1
    except Exception:
        return 0


def _count_dir_files(dir_path: Path, pattern: str = "*") -> int:
    """Count files in a directory matching pattern."""
    try:
        if dir_path.exists() and dir_path.is_dir():
            return len(list(dir_path.glob(pattern)))
    except Exception:
        pass
    return 0


def run_module_benchmark(root: Path | None = None) -> BenchmarkResult:
    """Benchmark key module loading and data availability."""
    if root is None:
        root = _resolve_root()

    modules = [
        ("P4.1_figure_cards", "03_Assets/figures", "figure_cards.json"),
        ("P4.1_figure_links", "03_Assets/figures", "asset_links.json"),
        ("P4.2_table_cards", "03_Assets/tables", "table_cards.json"),
        ("P4.3_supplementary_cards", "03_Assets/supplementary", "supplementary_cards.json"),
        ("P5.1_unified_graph_nodes", "05_Knowledge/unified_graph", "graph_nodes.json"),
        ("P5.1_unified_graph_edges", "05_Knowledge/unified_graph", "graph_edges.json"),
        ("P5.1_unified_graph_stats", "05_Knowledge/unified_graph", "graph_stats.json"),
        ("P5.3_dataset_manifest", "05_Knowledge/dataset_intelligence", "dataset_manifest.json"),
        ("P5.3_dataset_entity_index", "05_Knowledge/dataset_intelligence", "entity_index.json"),
        ("P6.0_validation_results", "10_System/validation/e2e", "e2e_validation_report.json"),
        ("P6.1_quality_dashboard", "10_System/quality", "quality_dashboard_summary.json"),
    ]

    tasks = [
        BenchmarkTask(task_id=f"module_{m[0]}", category="module", description=f"Load {m[0]}", runner="module_benchmark_runner")
        for m in modules
    ]

    metrics: list[RuntimeMetric] = []
    warnings: list[BenchmarkWarning] = []

    for mod_id, dir_rel, file_name in modules:
        t = RuntimeTimer(f"module:{mod_id}")
        t.start()
        file_path = root / dir_rel / file_name
        if file_path.exists():
            count = _count_json_items(file_path)
            t.add_metadata("input_count", count)
            t.add_metadata("file_path", f"{dir_rel}/{file_name}")
            t.stop(success=True)
        else:
            t.warn(f"File not found: {dir_rel}/{file_name}")
            t.add_metadata("file_path", f"{dir_rel}/{file_name}")
            t.add_metadata("input_count", 0)
            t.stop(success=True)  # missing data is not a failure
            warnings.append(BenchmarkWarning(
                module=mod_id,
                message=f"Data not found: {dir_rel}/{file_name}",
                severity="warning",
            ))
        metrics.append(t.to_metric())

    # Also check directory-level counts
    extra_checks = [
        ("P4.1_figure_count", "03_Assets/figures", "*.json", "file"),
        ("P4.2_table_count", "03_Assets/tables", "*.json", "file"),
        ("P4.3_supplementary_count", "03_Assets/supplementary", "*.json", "file"),
        ("P4.1_paper_subgraph_count", "05_Knowledge/unified_graph/paper_subgraphs", "*.json", "file"),
        ("P5.3_dataset_card_count", "05_Knowledge/dataset_intelligence/cards", "*.json", "file"),
    ]
    for label, dir_rel, pattern, _ in extra_checks:
        t = RuntimeTimer(f"count:{label}")
        t.start()
        count = _count_dir_files(root / dir_rel, pattern)
        t.add_metadata("count", count)
        t.add_metadata("directory", dir_rel)
        if count == 0:
            warnings.append(BenchmarkWarning(
                module=label,
                message=f"No {pattern} files in {dir_rel}",
                severity="warning" if label.startswith("P5") else "info",
            ))
        t.stop(success=True)
        metrics.append(t.to_metric())

    passed = sum(1 for m in metrics if m.success)
    failed = sum(1 for m in metrics if not m.success)
    total_ms = sum(m.duration_ms for m in metrics)

    return BenchmarkResult(
        category="module",
        tasks=tasks,
        runtime_metrics=metrics,
        warnings=warnings,
        passed=passed,
        warning_count=len(warnings),
        failed=failed,
        total_duration_ms=round(total_ms, 3),
        success=failed == 0,
    )
