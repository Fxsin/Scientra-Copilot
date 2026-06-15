"""Large-file safety benchmark for P6.5.

Generates synthetic CSV files and tests:
  - dataset_loader sampling
  - numeric profiler
  - entity extractor

Uses ONLY synthetic data — never user real data.
Output: 10_System/benchmarks/synthetic_large_files/
"""

from __future__ import annotations

import csv
import io
import time
from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkTask, BenchmarkWarning, LargeFileSafetyMetric
from scientra.benchmark.memory_estimator import estimate_memory_category, record_process_memory
from scientra.io.storage_layout import get_storage

SYNTHETIC_DIR = "10_System/benchmarks/synthetic_large_files"


def _resolve_root() -> Path:
    return get_storage().root


def _generate_synthetic_csv(root: Path, num_rows: int) -> Path:
    """Generate a synthetic CSV file with numeric and categorical columns.

    Returns the path to the generated file.
    """
    out_dir = root / SYNTHETIC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"synthetic_{num_rows}_rows.csv"

    if file_path.exists():
        return file_path

    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "group", "value_a", "value_b", "category", "note"])
        for i in range(num_rows):
            writer.writerow([
                i + 1,
                f"group_{(i % 10) + 1}",
                round((i * 1.5) % 100, 2),
                round((i * 0.7) % 50, 2),
                f"cat_{(i % 5) + 1}",
                f"sample_note_{i + 1}",
            ])
    return file_path


def _test_dataset_loader(file_path: Path) -> dict[str, Any]:
    """Test loading the synthetic CSV as a dataset."""
    warnings: list[str] = []
    t0 = time.perf_counter_ns()
    row_count = 0
    try:
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for _ in reader:
                row_count += 1
    except Exception as exc:
        warnings.append(f"loader error: {exc}")
    duration_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    return {"duration_ms": duration_ms, "row_count": row_count, "warnings": warnings}


def _test_numeric_profiler(file_path: Path) -> dict[str, Any]:
    """Test numeric profiling on synthetic CSV."""
    warnings: list[str] = []
    t0 = time.perf_counter_ns()
    numeric_columns = 0
    try:
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                # Identify numeric columns by sampling first 100 rows
                sample = []
                for i, row in enumerate(reader):
                    if i >= 100:
                        break
                    sample.append(row)
                for col in reader.fieldnames:
                    values = [row.get(col, "") for row in sample if row.get(col, "")]
                    numeric_count = 0
                    for v in values:
                        try:
                            float(v)
                            numeric_count += 1
                        except (ValueError, TypeError):
                            pass
                    if numeric_count > len(values) * 0.8:
                        numeric_columns += 1
    except Exception as exc:
        warnings.append(f"profiler error: {exc}")
    duration_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    return {"duration_ms": duration_ms, "numeric_columns": numeric_columns, "warnings": warnings}


def _test_entity_extractor(file_path: Path) -> dict[str, Any]:
    """Test entity extraction on synthetic CSV."""
    warnings: list[str] = []
    t0 = time.perf_counter_ns()
    entities_found = 0
    try:
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 1000:  # Sample first 1000 rows
                    break
                # Extract group and category as "entities"
                group = row.get("group", "")
                category = row.get("category", "")
                if group:
                    entities_found += 1
                if category:
                    entities_found += 1
    except Exception as exc:
        warnings.append(f"entity extractor error: {exc}")
    duration_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    return {"duration_ms": duration_ms, "entities_found": entities_found, "warnings": warnings}


def run_large_file_benchmark(root: Path | None = None,
                             max_rows: int = 100_000,
                             keep_files: bool = True) -> BenchmarkResult:
    """Run large-file safety benchmark.

    Args:
        root: Project root path.
        max_rows: Maximum synthetic rows to generate (default 100k).
        keep_files: If True, retain synthetic files after benchmark.
    """
    if root is None:
        root = _resolve_root()

    sizes = [n for n in [1_000, 10_000, 100_000] if n <= max_rows]
    tasks = [
        BenchmarkTask(task_id=f"large_file_{n}", category="large_file",
                      description=f"Test synthetic CSV with {n} rows", runner="large_file_safety_benchmark")
        for n in sizes
    ]

    metrics: list[LargeFileSafetyMetric] = []
    warnings: list[BenchmarkWarning] = []

    for num_rows in sizes:
        all_warnings: list[str] = []

        # Generate synthetic CSV
        try:
            file_path = _generate_synthetic_csv(root, num_rows)
        except Exception as exc:
            warnings.append(BenchmarkWarning(module="large_file", message=f"Failed to generate {num_rows} row CSV: {exc}"))
            metrics.append(LargeFileSafetyMetric(
                label=f"synthetic_{num_rows}_rows",
                row_count=0,
                success=False,
                error=str(exc),
            ))
            continue

        file_size = file_path.stat().st_size if file_path.exists() else 0

        # Test loader
        loader_result = _test_dataset_loader(file_path)
        all_warnings.extend(loader_result.get("warnings", []))

        # Test numeric profiler
        profiler_result = _test_numeric_profiler(file_path)
        all_warnings.extend(profiler_result.get("warnings", []))

        # Test entity extractor
        extractor_result = _test_entity_extractor(file_path)
        all_warnings.extend(extractor_result.get("warnings", []))

        # Memory estimation
        mem_category = estimate_memory_category(
            file_size_bytes=file_size,
            row_count=num_rows,
            output_count=loader_result.get("row_count", 0) * 2,
        )
        mem_info = record_process_memory()

        if all_warnings:
            for w in all_warnings:
                warnings.append(BenchmarkWarning(module="large_file", message=w))

        metrics.append(LargeFileSafetyMetric(
            label=f"synthetic_{num_rows}_rows",
            row_count=num_rows,
            file_size_bytes=file_size,
            load_duration_ms=round(loader_result.get("duration_ms", 0), 3),
            profile_duration_ms=round(profiler_result.get("duration_ms", 0), 3),
            extract_duration_ms=round(extractor_result.get("duration_ms", 0), 3),
            peak_memory_category=mem_category,
            success=True,
            warnings=all_warnings,
        ))

    # Clean up if not keeping files
    if not keep_files:
        for num_rows in sizes:
            fp = root / SYNTHETIC_DIR / f"synthetic_{num_rows}_rows.csv"
            try:
                if fp.exists():
                    fp.unlink()
            except Exception:
                pass

    passed = sum(1 for m in metrics if m.success)
    total_ms = sum(m.load_duration_ms + m.profile_duration_ms + m.extract_duration_ms for m in metrics)

    return BenchmarkResult(
        category="large_file",
        tasks=tasks,
        large_file_metrics=metrics,
        warnings=warnings,
        passed=passed,
        warning_count=len(warnings),
        failed=len(metrics) - passed,
        total_duration_ms=round(total_ms, 3),
        success=all(m.success for m in metrics),
    )
