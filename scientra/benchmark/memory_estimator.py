"""Lightweight memory risk estimator for P6.5 benchmark.

Does not require precise profiler. Uses input size, row count, and output
count to estimate memory risk category. Optionally records process memory
if psutil is available.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# Optional psutil import
try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None  # type: ignore
    _HAS_PSUTIL = False


def estimate_memory_category(
    file_size_bytes: int = 0,
    row_count: int = 0,
    output_count: int = 0,
    estimated_objects: int = 0,
) -> str:
    """Estimate memory risk category: low / medium / high.

    Heuristic thresholds (tunable):
        - low:    < 10 MB file, < 10k rows, < 1k outputs
        - medium: 10-100 MB file, 10k-100k rows, 1k-10k outputs
        - high:   > 100 MB file, > 100k rows, > 10k outputs
    """
    score = 0

    if file_size_bytes > 100 * 1024 * 1024:  # > 100 MB
        score += 3
    elif file_size_bytes > 10 * 1024 * 1024:  # > 10 MB
        score += 1

    if row_count > 100_000:
        score += 3
    elif row_count > 10_000:
        score += 1

    if output_count > 10_000:
        score += 2
    elif output_count > 1_000:
        score += 1

    if estimated_objects > 50_000:
        score += 2
    elif estimated_objects > 10_000:
        score += 1

    if score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    return "low"


def record_process_memory() -> dict[str, Any]:
    """Record current process memory usage if psutil is available.

    Returns dict with keys: rss_mb, vms_mb, available, warnings.
    Returns warning if psutil is not available (never raises).
    """
    if not _HAS_PSUTIL:
        return {
            "rss_mb": None,
            "vms_mb": None,
            "available": None,
            "warnings": ["psutil not available; process memory not recorded"],
        }

    try:
        proc = _psutil.Process(os.getpid())
        mem = proc.memory_info()
        vm = _psutil.virtual_memory() if hasattr(_psutil, "virtual_memory") else None
        return {
            "rss_mb": round(mem.rss / (1024 * 1024), 2),
            "vms_mb": round(mem.vms / (1024 * 1024), 2) if hasattr(mem, "vms") else None,
            "available": round(vm.available / (1024 * 1024), 2) if vm else None,
            "warnings": [],
        }
    except Exception as exc:
        return {
            "rss_mb": None,
            "vms_mb": None,
            "available": None,
            "warnings": [f"psutil error: {exc}"],
        }


def estimate_file_memory_risk(file_path: Path, row_count: int = 0, output_count: int = 0) -> dict[str, Any]:
    """Estimate memory risk for a specific file.

    Returns dict with category, file_size_bytes, row_count, output_count, and warnings.
    Never raises.
    """
    warnings: list[str] = []
    file_size = 0
    try:
        if file_path.exists():
            file_size = file_path.stat().st_size
        else:
            warnings.append(f"File not found: {file_path.name}")
    except Exception as exc:
        warnings.append(f"Cannot stat file: {exc}")

    category = estimate_memory_category(
        file_size_bytes=file_size,
        row_count=row_count,
        output_count=output_count,
    )
    mem_info = record_process_memory()
    if mem_info.get("warnings"):
        warnings.extend(mem_info["warnings"])

    return {
        "file": str(file_path.name) if file_path.name else "unknown",
        "file_size_bytes": file_size,
        "row_count": row_count,
        "output_count": output_count,
        "memory_category": category,
        "process_rss_mb": mem_info.get("rss_mb"),
        "process_vms_mb": mem_info.get("vms_mb"),
        "warnings": warnings,
    }
