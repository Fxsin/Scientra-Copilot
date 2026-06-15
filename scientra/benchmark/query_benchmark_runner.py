"""Query benchmark runner for P6.5.

Benchmarks Cross-Asset Query latency with fixed queries.
Records per-phase duration: keyword, vector, graph, merge/rank.
Missing LanceDB → warning, no crash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkTask, BenchmarkWarning, QueryLatencyMetric
from scientra.benchmark.runtime_timer import RuntimeTimer
from scientra.io.storage_layout import get_storage


FIXED_QUERIES = [
    "gene expression",
    "LC50 bioassay",
    "western blot",
    "supplementary table",
    "claim support",
    "gap hypothesis evidence",
]


def _resolve_root() -> Path:
    return get_storage().root


def _check_lancedb(root: Path) -> tuple[bool, str, dict[str, int]]:
    """Check LanceDB availability. Returns (available, status, table_counts)."""
    try:
        import lancedb
    except ImportError:
        return False, "lancedb not installed", {}

    db_dir = root / "06_Index" / "vector" / "lancedb"
    if not db_dir.exists():
        db_dir = root / "06_Index/vector/lancedb/lancedb"
    if not db_dir.exists():
        # Fallback: try legacy path
        archives = sorted((root / "10_System/legacy_archive").glob("storage_v1_legacy_*/04_VectorDB/lancedb"))
        db_dir = archives[-1] if archives else db_dir

    if not db_dir.exists() or not any(db_dir.iterdir()):
        return False, "no LanceDB directory", {}

    try:
        db = lancedb.connect(str(db_dir))
        tables = db.table_names()
        counts: dict[str, int] = {}
        for t in tables:
            try:
                counts[t] = len(db.open_table(t).to_arrow())
            except Exception:
                pass
        return True, "ok", counts
    except Exception as exc:
        return False, f"error: {type(exc).__name__}: {exc}", {}


def _try_keyword_search(root: Path, query: str) -> tuple[int, list[str]]:
    """Try keyword search on metadata. Returns (hit_count, warnings)."""
    warnings: list[str] = []
    hit_count = 0
    try:
        import yaml
        yaml_dir = root / "02_Metadata"
        if yaml_dir.exists():
            for yf in yaml_dir.rglob("*.yaml"):
                try:
                    content = yf.read_text(encoding="utf-8")
                    if query.lower() in content.lower():
                        hit_count += 1
                except Exception:
                    pass
    except Exception as exc:
        warnings.append(f"keyword search error: {exc}")
    return hit_count, warnings


def _try_vector_search(root: Path, query: str) -> tuple[int, float, list[str]]:
    """Try vector search via LanceDB. Returns (hit_count, duration_ms, warnings)."""
    import time
    warnings: list[str] = []
    hit_count = 0
    t0 = time.perf_counter_ns()

    available, status, _ = _check_lancedb(root)
    if not available:
        duration_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        warnings.append(f"LanceDB not available: {status}")
        return 0, duration_ms, warnings

    try:
        import lancedb
        db_dir = root / "06_Index" / "vector" / "lancedb"
        if not db_dir.exists():
            db_dir = root / "06_Index/vector/lancedb/lancedb"
        db = lancedb.connect(str(db_dir))
        tables = db.table_names()
        if tables:
            table = db.open_table(tables[0])
            # Simple full table scan for benchmark — not a real vector search
            # but measures data access speed
            results = table.search().limit(10).to_list()
            hit_count = len(results)
    except Exception as exc:
        warnings.append(f"vector search error: {exc}")

    duration_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    return hit_count, duration_ms, warnings


def run_query_benchmark(root: Path | None = None) -> BenchmarkResult:
    """Run query latency benchmark with fixed queries."""
    if root is None:
        root = _resolve_root()

    tasks = [
        BenchmarkTask(task_id=f"query_{i}", category="query", description=f"Query: {q}", runner="query_benchmark_runner")
        for i, q in enumerate(FIXED_QUERIES)
    ]

    query_metrics: list[QueryLatencyMetric] = []
    warnings: list[BenchmarkWarning] = []
    import time

    for query in FIXED_QUERIES:
        t_total = time.perf_counter_ns()
        all_warnings: list[str] = []

        # Phase 1: Keyword retrieval
        t0 = time.perf_counter_ns()
        kw_hits, kw_warnings = _try_keyword_search(root, query)
        kw_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        all_warnings.extend(kw_warnings)

        # Phase 2: Vector retrieval
        vec_hits, vec_ms, vec_warnings = _try_vector_search(root, query)
        all_warnings.extend(vec_warnings)

        # Phase 3: Graph retrieval (placeholder — graph benchmark does this)
        t0 = time.perf_counter_ns()
        graph_hits = 0
        graph_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        # Phase 4: Merge/rank (placeholder)
        t0 = time.perf_counter_ns()
        merge_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        total_ms = (time.perf_counter_ns() - t_total) / 1_000_000.0
        total_hits = kw_hits + vec_hits + graph_hits

        if all_warnings:
            for w in all_warnings:
                warnings.append(BenchmarkWarning(module="query", message=w))

        query_metrics.append(QueryLatencyMetric(
            query=query,
            total_duration_ms=round(total_ms, 3),
            keyword_duration_ms=round(kw_ms, 3),
            vector_duration_ms=round(vec_ms, 3),
            graph_duration_ms=round(graph_ms, 3),
            merge_duration_ms=round(merge_ms, 3),
            hit_count=total_hits,
            warnings=all_warnings,
            success=True,
        ))

    passed = sum(1 for q in query_metrics if q.success)
    total_ms = sum(q.total_duration_ms for q in query_metrics)

    return BenchmarkResult(
        category="query",
        tasks=tasks,
        query_metrics=query_metrics,
        warnings=warnings,
        passed=passed,
        warning_count=len(warnings),
        failed=len(query_metrics) - passed,
        total_duration_ms=round(total_ms, 3),
        success=True,
    )
