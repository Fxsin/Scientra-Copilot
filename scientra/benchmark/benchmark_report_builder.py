"""Benchmark report builder for P6.5.

Generates all output files:
  - benchmark_summary.json
  - benchmark_report.md
  - module_runtime_matrix.csv
  - query_latency_matrix.csv
  - large_file_safety_matrix.csv
  - cache_recommendations.json
  - incremental_update_recommendations.json
  - benchmark_raw_events.jsonl
"""

from __future__ import annotations

import csv
import json
import io
from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkRun, BenchmarkResult
from scientra.io.storage_layout import get_storage

OUTPUT_DIR = "10_System/benchmarks"


def _resolve_root() -> Path:
    return get_storage().root


def _ensure_output_dir(root: Path) -> Path:
    out = root / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    return out


def _serialize_run(run: BenchmarkRun) -> dict[str, Any]:
    """Serialize a BenchmarkRun to a JSON-safe dict."""
    results_serialized = {}
    for key, result in run.results.items():
        results_serialized[key] = {
            "category": result.category,
            "passed": result.passed,
            "warning_count": result.warning_count,
            "failed": result.failed,
            "total_duration_ms": result.total_duration_ms,
            "success": result.success,
            "error": result.error,
            "warnings": [{"module": w.module, "message": w.message, "severity": w.severity} for w in result.warnings],
            "runtime_metrics": [
                {
                    "label": m.label,
                    "duration_ms": m.duration_ms,
                    "success": m.success,
                    "error": m.error,
                    "warnings": m.warnings,
                    "metadata": m.metadata,
                }
                for m in result.runtime_metrics
            ],
            "query_metrics": [
                {
                    "query": qm.query,
                    "total_duration_ms": qm.total_duration_ms,
                    "keyword_duration_ms": qm.keyword_duration_ms,
                    "vector_duration_ms": qm.vector_duration_ms,
                    "graph_duration_ms": qm.graph_duration_ms,
                    "merge_duration_ms": qm.merge_duration_ms,
                    "hit_count": qm.hit_count,
                    "warnings": qm.warnings,
                }
                for qm in result.query_metrics
            ],
            "large_file_metrics": [
                {
                    "label": lfm.label,
                    "row_count": lfm.row_count,
                    "file_size_bytes": lfm.file_size_bytes,
                    "load_duration_ms": lfm.load_duration_ms,
                    "profile_duration_ms": lfm.profile_duration_ms,
                    "extract_duration_ms": lfm.extract_duration_ms,
                    "peak_memory_category": lfm.peak_memory_category,
                    "warnings": lfm.warnings,
                }
                for lfm in result.large_file_metrics
            ],
        }

    return {
        "run_id": run.run_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "total_duration_ms": run.total_duration_ms,
        "total_tasks": run.total_tasks,
        "total_passed": run.total_passed,
        "total_warnings": run.total_warnings,
        "total_failed": run.total_failed,
        "slowest_module": run.slowest_module,
        "slowest_module_ms": run.slowest_module_ms,
        "slowest_query": run.slowest_query,
        "slowest_query_ms": run.slowest_query_ms,
        "large_file_safety_passed": run.large_file_safety_passed,
        "cache_recommendations": run.cache_recommendations,
        "incremental_update_recommendations": run.incremental_update_recommendations,
        "p7_readiness_warnings": run.p7_readiness_warnings,
        "results": results_serialized,
        "errors": run.errors,
    }


def build_benchmark_summary(run: BenchmarkRun, root: Path | None = None) -> Path:
    """Write benchmark_summary.json. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)
    data = _serialize_run(run)
    path = out_dir / "benchmark_summary.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_benchmark_report_md(run: BenchmarkRun, root: Path | None = None) -> Path:
    """Write benchmark_report.md. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)

    lines = [
        "# Scientra Copilot P6.5 Benchmark Report",
        "",
        f"**Run ID:** {run.run_id}",
        f"**Started:** {run.started_at}",
        f"**Completed:** {run.completed_at}",
        f"**Total Duration:** {run.total_duration_ms:.1f} ms",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Tasks | {run.total_tasks} |",
        f"| Passed | {run.total_passed} |",
        f"| Warnings | {run.total_warnings} |",
        f"| Failed | {run.total_failed} |",
        f"| Large File Safety | {'✅ Passed' if run.large_file_safety_passed else '❌ Failed'} |",
        "",
        f"**Slowest Module:** {run.slowest_module} ({run.slowest_module_ms:.1f} ms)",
        f"**Slowest Query:** {run.slowest_query} ({run.slowest_query_ms:.1f} ms)",
        "",
    ]

    # Per-category results
    for key in ["module", "query", "graph", "dataset", "agent", "large_file"]:
        result = run.results.get(key)
        if result is None:
            continue
        lines.append(f"## {key.replace('_', ' ').title()} Benchmark")
        lines.append("")
        lines.append(f"- **Passed:** {result.passed} | **Warnings:** {result.warning_count} | **Failed:** {result.failed}")
        lines.append(f"- **Duration:** {result.total_duration_ms:.1f} ms")
        lines.append("")

        if result.runtime_metrics:
            lines.append("| Label | Duration (ms) | Status | Warnings |")
            lines.append("|-------|---------------|--------|----------|")
            for m in result.runtime_metrics[:20]:
                status = "✅" if m.success else "❌"
                lines.append(f"| {m.label} | {m.duration_ms:.1f} | {status} | {len(m.warnings)} |")
            lines.append("")

        if result.query_metrics:
            lines.append("| Query | Total (ms) | Keyword (ms) | Vector (ms) | Hits | Warnings |")
            lines.append("|-------|------------|--------------|-------------|------|----------|")
            for qm in result.query_metrics:
                lines.append(f"| {qm.query} | {qm.total_duration_ms:.1f} | {qm.keyword_duration_ms:.1f} | {qm.vector_duration_ms:.1f} | {qm.hit_count} | {len(qm.warnings)} |")
            lines.append("")

        if result.large_file_metrics:
            lines.append("| Label | Rows | File Size | Load (ms) | Profile (ms) | Extract (ms) | Memory |")
            lines.append("|-------|------|-----------|-----------|-------------|-------------|--------|")
            for lfm in result.large_file_metrics:
                size_kb = lfm.file_size_bytes / 1024
                lines.append(f"| {lfm.label} | {lfm.row_count} | {size_kb:.1f} KB | {lfm.load_duration_ms:.1f} | {lfm.profile_duration_ms:.1f} | {lfm.extract_duration_ms:.1f} | {lfm.peak_memory_category} |")
            lines.append("")

        if result.warnings:
            lines.append("### Warnings")
            lines.append("")
            for w in result.warnings[:10]:
                lines.append(f"- [{w.severity}] {w.module}: {w.message}")
            lines.append("")

    # Recommendations
    if run.cache_recommendations:
        lines.append("## Cache Recommendations")
        lines.append("")
        for r in run.cache_recommendations[:15]:
            lines.append(f"- **[{r['priority']}] {r['target']}**: {r['recommendation']}")
        lines.append("")

    if run.incremental_update_recommendations:
        lines.append("## Incremental Update Recommendations")
        lines.append("")
        for r in run.incremental_update_recommendations[:15]:
            lines.append(f"- **[{r['priority']}] {r['target']}**: {r['recommendation']}")
        lines.append("")

    # P7 readiness
    if run.p7_readiness_warnings:
        lines.append("## P7 Readiness Warnings")
        lines.append("")
        for w in run.p7_readiness_warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")
    else:
        lines.append("## P7 Readiness")
        lines.append("")
        lines.append("✅ No blocking performance issues found for P7 Scientific Reasoning Engine.")
        lines.append("")

    # Errors
    if run.errors:
        lines.append("## Errors")
        lines.append("")
        for e in run.errors:
            lines.append(f"- ❌ {e}")
        lines.append("")

    path = out_dir / "benchmark_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_module_runtime_csv(run: BenchmarkRun, root: Path | None = None) -> Path:
    """Write module_runtime_matrix.csv. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)
    path = out_dir / "module_runtime_matrix.csv"

    result = run.results.get("module")
    metrics = result.runtime_metrics if result else []

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["module", "duration_ms", "input_count", "output_count", "warnings", "status"])
        for m in metrics:
            writer.writerow([
                m.label,
                m.duration_ms,
                m.metadata.get("input_count", m.metadata.get("count", "")),
                m.metadata.get("output_count", ""),
                len(m.warnings),
                "passed" if m.success else "failed",
            ])
    return path


def build_query_latency_csv(run: BenchmarkRun, root: Path | None = None) -> Path:
    """Write query_latency_matrix.csv. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)
    path = out_dir / "query_latency_matrix.csv"

    result = run.results.get("query")
    metrics = result.query_metrics if result else []

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "total_ms", "keyword_ms", "vector_ms", "graph_ms", "merge_ms", "hit_count", "warnings"])
        for qm in metrics:
            writer.writerow([
                qm.query,
                qm.total_duration_ms,
                qm.keyword_duration_ms,
                qm.vector_duration_ms,
                qm.graph_duration_ms,
                qm.merge_duration_ms,
                qm.hit_count,
                len(qm.warnings),
            ])
    return path


def build_large_file_safety_csv(run: BenchmarkRun, root: Path | None = None) -> Path:
    """Write large_file_safety_matrix.csv. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)
    path = out_dir / "large_file_safety_matrix.csv"

    result = run.results.get("large_file")
    metrics = result.large_file_metrics if result else []

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label", "row_count", "file_size_bytes", "load_ms", "profile_ms", "extract_ms", "memory_category", "status"])
        for lfm in metrics:
            writer.writerow([
                lfm.label,
                lfm.row_count,
                lfm.file_size_bytes,
                lfm.load_duration_ms,
                lfm.profile_duration_ms,
                lfm.extract_duration_ms,
                lfm.peak_memory_category,
                "passed" if lfm.success else "failed",
            ])
    return path


def build_cache_recommendations_json(cache_recs: list[dict[str, Any]], root: Path | None = None) -> Path:
    """Write cache_recommendations.json. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)
    path = out_dir / "cache_recommendations.json"
    path.write_text(json.dumps(cache_recs, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_incremental_recommendations_json(incr_recs: list[dict[str, Any]], root: Path | None = None) -> Path:
    """Write incremental_update_recommendations.json. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)
    path = out_dir / "incremental_update_recommendations.json"
    path.write_text(json.dumps(incr_recs, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_raw_events_jsonl(run: BenchmarkRun, root: Path | None = None) -> Path:
    """Write benchmark_raw_events.jsonl. Returns output path."""
    if root is None:
        root = _resolve_root()
    out_dir = _ensure_output_dir(root)
    path = out_dir / "benchmark_raw_events.jsonl"

    with open(path, "w", encoding="utf-8") as f:
        for key, result in run.results.items():
            for metric in result.runtime_metrics:
                event = {
                    "run_id": run.run_id,
                    "category": key,
                    "label": metric.label,
                    "duration_ms": metric.duration_ms,
                    "success": metric.success,
                    "warnings": metric.warnings,
                    "metadata": metric.metadata,
                }
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            for qm in result.query_metrics:
                event = {
                    "run_id": run.run_id,
                    "category": key,
                    "query": qm.query,
                    "total_duration_ms": qm.total_duration_ms,
                    "keyword_ms": qm.keyword_duration_ms,
                    "vector_ms": qm.vector_duration_ms,
                    "graph_ms": qm.graph_duration_ms,
                    "merge_ms": qm.merge_duration_ms,
                    "hit_count": qm.hit_count,
                }
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            for lfm in result.large_file_metrics:
                event = {
                    "run_id": run.run_id,
                    "category": key,
                    "label": lfm.label,
                    "row_count": lfm.row_count,
                    "file_size_bytes": lfm.file_size_bytes,
                    "load_ms": lfm.load_duration_ms,
                    "profile_ms": lfm.profile_duration_ms,
                    "extract_ms": lfm.extract_duration_ms,
                    "memory_category": lfm.peak_memory_category,
                }
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def build_all_reports(run: BenchmarkRun, root: Path | None = None) -> dict[str, str]:
    """Generate all benchmark reports. Returns dict mapping report name → path."""
    if root is None:
        root = _resolve_root()

    reports: dict[str, str] = {}

    # Summary JSON
    p = build_benchmark_summary(run, root)
    reports["benchmark_summary.json"] = str(p.relative_to(root))

    # Report MD
    p = build_benchmark_report_md(run, root)
    reports["benchmark_report.md"] = str(p.relative_to(root))

    # Module runtime CSV
    p = build_module_runtime_csv(run, root)
    reports["module_runtime_matrix.csv"] = str(p.relative_to(root))

    # Query latency CSV
    p = build_query_latency_csv(run, root)
    reports["query_latency_matrix.csv"] = str(p.relative_to(root))

    # Large file safety CSV
    p = build_large_file_safety_csv(run, root)
    reports["large_file_safety_matrix.csv"] = str(p.relative_to(root))

    # Cache recommendations
    p = build_cache_recommendations_json(run.cache_recommendations, root)
    reports["cache_recommendations.json"] = str(p.relative_to(root))

    # Incremental update recommendations
    p = build_incremental_recommendations_json(run.incremental_update_recommendations, root)
    reports["incremental_update_recommendations.json"] = str(p.relative_to(root))

    # Raw events
    p = build_raw_events_jsonl(run, root)
    reports["benchmark_raw_events.jsonl"] = str(p.relative_to(root))

    return reports
