#!/usr/bin/env python
"""P6.5 Performance Benchmark & Runtime Profiling. Usage:
    python Scripts/run_benchmark.py --all --verbose
    python Scripts/run_benchmark.py --modules --queries --graph
    python Scripts/run_benchmark.py --large-file --max-synthetic-rows 100000
    python Scripts/run_benchmark.py --agent --json
    python Scripts/run_benchmark.py --all --skip-large-file --export
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="P6.5 Performance Benchmark & Runtime Profiling",
    )
    # Category flags
    p.add_argument("--all", action="store_true", help="Run all benchmarks")
    p.add_argument("--modules", action="store_true", help="Run module loading benchmark")
    p.add_argument("--queries", action="store_true", help="Run query latency benchmark")
    p.add_argument("--graph", action="store_true", help="Run graph benchmark")
    p.add_argument("--datasets", action="store_true", help="Run dataset benchmark")
    p.add_argument("--agent", action="store_true", help="Run agent benchmark (evidence_only)")
    p.add_argument("--large-file", action="store_true", help="Run large-file safety benchmark")

    # Skip flags
    p.add_argument("--skip-modules", action="store_true")
    p.add_argument("--skip-queries", action="store_true")
    p.add_argument("--skip-graph", action="store_true")
    p.add_argument("--skip-datasets", action="store_true")
    p.add_argument("--skip-agent", action="store_true")
    p.add_argument("--skip-large-file", action="store_true")
    p.add_argument("--skip-vector", action="store_true", help="Skip vector search in queries")

    # Options
    p.add_argument("--include-llm", action="store_true", help="Allow LLM usage in agent benchmark")
    p.add_argument("--max-synthetic-rows", type=int, default=100_000,
                   help="Max synthetic CSV rows for large-file test (default: 100000)")
    p.add_argument("--root", type=Path, default=None, help="Project root path")
    p.add_argument("--json", action="store_true", help="Output results as JSON")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    p.add_argument("--export", action="store_true", help="Export results to 09_Exports/benchmarks/")

    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    from scientra.benchmark.benchmark_runner import BenchmarkRunner
    from scientra.benchmark.benchmark_report_builder import _serialize_run

    # Determine what to run
    run_all = args.all
    if not any([run_all, args.modules, args.queries, args.graph, args.datasets, args.agent, args.large_file]):
        # If no specific flag, default to --all
        run_all = True

    runner = BenchmarkRunner(root=args.root)

    try:
        benchmark_run = runner.run_all(
            skip_modules=args.skip_modules or (not run_all and not args.modules),
            skip_queries=args.skip_queries or (not run_all and not args.queries),
            skip_graph=args.skip_graph or (not run_all and not args.graph),
            skip_datasets=args.skip_datasets or (not run_all and not args.datasets),
            skip_agent=args.skip_agent or (not run_all and not args.agent),
            skip_large_file=args.skip_large_file or (not run_all and not args.large_file),
            include_llm=args.include_llm,
            max_synthetic_rows=args.max_synthetic_rows,
            keep_synthetic_files=True,
        )
    except Exception as exc:
        print(f"Fatal benchmark error: {exc}", file=sys.stderr)
        return 1

    # Generate reports
    try:
        reports = runner.generate_reports()
    except Exception as exc:
        print(f"Warning: Report generation failed: {exc}", file=sys.stderr)
        reports = {}

    # Export if requested
    if args.export:
        try:
            exported = runner.export_results()
            if args.verbose:
                for path, name in exported.items():
                    print(f"  Exported: {path}")
        except Exception as exc:
            print(f"Warning: Export failed: {exc}", file=sys.stderr)

    # Output
    if args.json:
        print(json.dumps(_serialize_run(benchmark_run), ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  Scientra Copilot P6.5 Performance Benchmark")
        print(f"  Run ID: {benchmark_run.run_id}")
        print(f"  Duration: {benchmark_run.total_duration_ms:.1f} ms")
        print(f"{'='*60}")
        print(f"\n  Summary:")
        print(f"    Tasks:     {benchmark_run.total_tasks}")
        print(f"    Passed:    {benchmark_run.total_passed} ✅")
        print(f"    Warnings:  {benchmark_run.total_warnings} ⚠️")
        print(f"    Failed:    {benchmark_run.total_failed} ❌")
        print(f"\n  Slowest Module: {benchmark_run.slowest_module} ({benchmark_run.slowest_module_ms:.1f} ms)")
        print(f"  Slowest Query:  {benchmark_run.slowest_query} ({benchmark_run.slowest_query_ms:.1f} ms)")
        print(f"  Large-File Safety: {'✅ Passed' if benchmark_run.large_file_safety_passed else '❌ Failed'}")

        if args.verbose:
            print(f"\n  Per-Category Results:")
            for key, result in benchmark_run.results.items():
                status = "✅" if result.success else "❌"
                print(f"    [{status}] {key}: {result.passed} passed, {result.warning_count} warnings, {result.failed} failed ({result.total_duration_ms:.1f} ms)")

            if benchmark_run.cache_recommendations:
                print(f"\n  Cache Recommendations ({len(benchmark_run.cache_recommendations)}):")
                for rec in benchmark_run.cache_recommendations[:5]:
                    print(f"    [{rec['priority']}] {rec['target']}: {rec['recommendation'][:80]}...")

            if benchmark_run.incremental_update_recommendations:
                print(f"\n  Incremental Update Recommendations ({len(benchmark_run.incremental_update_recommendations)}):")
                for rec in benchmark_run.incremental_update_recommendations[:5]:
                    print(f"    [{rec['priority']}] {rec['target']}: {rec['recommendation'][:80]}...")

            if benchmark_run.p7_readiness_warnings:
                print(f"\n  P7 Readiness Warnings ({len(benchmark_run.p7_readiness_warnings)}):")
                for w in benchmark_run.p7_readiness_warnings:
                    print(f"    ⚠️  {w}")

            if reports:
                print(f"\n  Reports Generated:")
                for name, path in reports.items():
                    print(f"    {name}: {path}")

            if benchmark_run.errors:
                print(f"\n  Errors:")
                for e in benchmark_run.errors:
                    print(f"    ❌ {e}")

        print(f"\n  Full report: 10_System/benchmarks/benchmark_report.md\n")

    # Return non-zero if there were hard failures
    if benchmark_run.total_failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
