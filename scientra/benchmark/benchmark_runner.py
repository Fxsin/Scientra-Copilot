"""Benchmark orchestrator for P6.5.

Runs all or selected benchmarks and generates reports.
Supports skip flags, partial report on failure.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkRun, BenchmarkResult, now_iso, make_run_id
from scientra.benchmark.module_benchmark_runner import run_module_benchmark
from scientra.benchmark.query_benchmark_runner import run_query_benchmark
from scientra.benchmark.graph_benchmark_runner import run_graph_benchmark
from scientra.benchmark.dataset_benchmark_runner import run_dataset_benchmark
from scientra.benchmark.agent_benchmark_runner import run_agent_benchmark
from scientra.benchmark.large_file_safety_benchmark import run_large_file_benchmark
from scientra.benchmark.cache_recommendation_builder import build_cache_recommendations
from scientra.benchmark.incremental_update_recommendation_builder import build_incremental_update_recommendations
from scientra.benchmark.benchmark_report_builder import build_all_reports
from scientra.io.storage_layout import get_storage


class BenchmarkRunner:
    """Orchestrates all P6.5 benchmarks."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else get_storage().root
        self.run: BenchmarkRun | None = None
        self._errors: list[str] = []

    def run_all(
        self,
        skip_modules: bool = False,
        skip_queries: bool = False,
        skip_graph: bool = False,
        skip_datasets: bool = False,
        skip_agent: bool = False,
        skip_large_file: bool = False,
        include_llm: bool = False,
        max_synthetic_rows: int = 100_000,
        keep_synthetic_files: bool = True,
    ) -> BenchmarkRun:
        """Run all benchmarks.

        Args:
            skip_modules: Skip module loading benchmark.
            skip_queries: Skip query latency benchmark.
            skip_graph: Skip graph benchmark.
            skip_datasets: Skip dataset benchmark.
            skip_agent: Skip agent benchmark.
            skip_large_file: Skip large-file safety benchmark.
            include_llm: Allow LLM usage (default: False).
            max_synthetic_rows: Max synthetic rows for large-file test.
            keep_synthetic_files: Keep synthetic files after benchmark.

        Returns:
            BenchmarkRun with all results.
        """
        run_id = make_run_id()
        started_at = now_iso()
        t_total = time.perf_counter_ns()

        self._errors = []
        results: dict[str, BenchmarkResult] = {}

        # Run each benchmark category, catching errors so one failure doesn't block others
        categories = []

        if not skip_modules:
            categories.append(("module", lambda: run_module_benchmark(self.root)))

        if not skip_queries:
            categories.append(("query", lambda: run_query_benchmark(self.root)))

        if not skip_graph:
            categories.append(("graph", lambda: run_graph_benchmark(self.root)))

        if not skip_datasets:
            categories.append(("dataset", lambda: run_dataset_benchmark(self.root)))

        if not skip_agent:
            categories.append(("agent", lambda: run_agent_benchmark(self.root, include_llm=include_llm)))

        if not skip_large_file:
            categories.append(("large_file", lambda: run_large_file_benchmark(
                self.root, max_rows=max_synthetic_rows, keep_files=keep_synthetic_files)))

        for category, runner_fn in categories:
            try:
                results[category] = runner_fn()
            except Exception as exc:
                self._errors.append(f"{category} benchmark failed: {type(exc).__name__}: {exc}")
                results[category] = BenchmarkResult(
                    category=category,
                    success=False,
                    error=str(exc),
                )

        # Compute aggregate stats
        total_tasks = sum(r.passed + r.warning_count + r.failed for r in results.values())
        total_passed = sum(r.passed for r in results.values())
        total_warnings = sum(r.warning_count for r in results.values())
        total_failed = sum(r.failed for r in results.values())

        # Find slowest module
        slowest_module = ""
        slowest_module_ms = 0.0
        mod_result = results.get("module")
        if mod_result:
            for m in mod_result.runtime_metrics:
                if m.duration_ms > slowest_module_ms:
                    slowest_module_ms = m.duration_ms
                    slowest_module = m.label

        # Find slowest query
        slowest_query = ""
        slowest_query_ms = 0.0
        query_result = results.get("query")
        if query_result:
            for q in query_result.query_metrics:
                if q.total_duration_ms > slowest_query_ms:
                    slowest_query_ms = q.total_duration_ms
                    slowest_query = q.query

        # Large file safety
        large_file_result = results.get("large_file")
        large_file_safety_passed = large_file_result.success if large_file_result else True

        # Build recommendations
        cache_recs = build_cache_recommendations(results)
        incr_recs = build_incremental_update_recommendations(results)

        # P7 readiness warnings
        p7_warnings: list[str] = []
        if slowest_module_ms > 2000:
            p7_warnings.append(f"Module '{slowest_module}' is very slow ({slowest_module_ms:.0f} ms) — may bottleneck P7 reasoning loop.")
        if slowest_query_ms > 5000:
            p7_warnings.append(f"Query '{slowest_query}' exceeds 5s — may affect P7 interactive reasoning response times.")
        if not large_file_safety_passed:
            p7_warnings.append("Large-file safety benchmark did not pass — P7 may need file size limits for source ingestion.")
        for _rec in cache_recs:
            if _rec.get("priority") == "high":
                p7_warnings.append(f"High-priority cache recommendation: {_rec['target']} — consider implementing before P7.")

        completed_at = now_iso()
        total_ms = (time.perf_counter_ns() - t_total) / 1_000_000.0

        self.run = BenchmarkRun(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            total_duration_ms=round(total_ms, 3),
            results=results,
            total_tasks=total_tasks,
            total_passed=total_passed,
            total_warnings=total_warnings,
            total_failed=total_failed,
            slowest_module=slowest_module,
            slowest_module_ms=round(slowest_module_ms, 3),
            slowest_query=slowest_query,
            slowest_query_ms=round(slowest_query_ms, 3),
            large_file_safety_passed=large_file_safety_passed,
            cache_recommendations=cache_recs,
            incremental_update_recommendations=incr_recs,
            p7_readiness_warnings=p7_warnings,
            errors=self._errors,
        )

        return self.run

    def generate_reports(self) -> dict[str, str]:
        """Generate all benchmark reports. Must call run_all() first."""
        if self.run is None:
            raise RuntimeError("No benchmark run. Call run_all() first.")
        return build_all_reports(self.run, self.root)

    def export_results(self, output_dir: Path | None = None) -> dict[str, str]:
        """Export results to 09_Exports/benchmarks/. Returns dict of path → name."""
        if output_dir is None:
            output_dir = self.root / "09_Exports" / "benchmarks"
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.run is None:
            raise RuntimeError("No benchmark run. Call run_all() first.")

        import json
        from scientra.benchmark.benchmark_report_builder import _serialize_run

        exported: dict[str, str] = {}

        # Export summary
        summary_path = output_dir / "benchmark_summary.json"
        summary_path.write_text(
            json.dumps(_serialize_run(self.run), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        exported[str(summary_path.relative_to(self.root))] = "benchmark_summary.json"

        return exported
