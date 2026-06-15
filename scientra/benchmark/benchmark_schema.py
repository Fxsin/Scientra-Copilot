"""P6.5 Benchmark data structures.

All paths are relative to project root. No absolute paths exposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RuntimeMetric:
    """Single runtime measurement."""
    label: str
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryLatencyMetric:
    """Cross-asset query latency breakdown."""
    query: str
    total_duration_ms: float = 0.0
    keyword_duration_ms: float = 0.0
    vector_duration_ms: float = 0.0
    graph_duration_ms: float = 0.0
    merge_duration_ms: float = 0.0
    hit_count: int = 0
    warnings: list[str] = field(default_factory=list)
    success: bool = True
    error: str | None = None


@dataclass
class LargeFileSafetyMetric:
    """Large-file safety test result."""
    label: str
    row_count: int
    file_size_bytes: int = 0
    load_duration_ms: float = 0.0
    profile_duration_ms: float = 0.0
    extract_duration_ms: float = 0.0
    peak_memory_category: str = "low"  # low / medium / high
    success: bool = True
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class BenchmarkWarning:
    """Non-fatal warning encountered during benchmark."""
    module: str
    message: str
    severity: str = "warning"  # warning / info


@dataclass
class BenchmarkRecommendation:
    """A single recommendation from benchmark analysis."""
    category: str  # cache / incremental_update / performance_risk
    target: str    # module or pipeline stage
    recommendation: str
    priority: str = "medium"  # high / medium / low
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkTask:
    """A single benchmark task configuration."""
    task_id: str
    category: str  # module / query / graph / dataset / agent / large_file
    description: str
    runner: str  # runner module name


@dataclass
class BenchmarkResult:
    """Aggregated result for one benchmark category."""
    category: str
    tasks: list[BenchmarkTask] = field(default_factory=list)
    runtime_metrics: list[RuntimeMetric] = field(default_factory=list)
    query_metrics: list[QueryLatencyMetric] = field(default_factory=list)
    large_file_metrics: list[LargeFileSafetyMetric] = field(default_factory=list)
    warnings: list[BenchmarkWarning] = field(default_factory=list)
    recommendations: list[BenchmarkRecommendation] = field(default_factory=list)
    passed: int = 0
    warning_count: int = 0
    failed: int = 0
    total_duration_ms: float = 0.0
    success: bool = True
    error: str | None = None


@dataclass
class BenchmarkRun:
    """Top-level benchmark run result."""
    run_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    total_duration_ms: float = 0.0
    results: dict[str, BenchmarkResult] = field(default_factory=dict)
    recommendations: list[BenchmarkRecommendation] = field(default_factory=list)
    total_tasks: int = 0
    total_passed: int = 0
    total_warnings: int = 0
    total_failed: int = 0
    slowest_module: str = ""
    slowest_module_ms: float = 0.0
    slowest_query: str = ""
    slowest_query_ms: float = 0.0
    large_file_safety_passed: bool = True
    cache_recommendations: list[dict[str, Any]] = field(default_factory=list)
    incremental_update_recommendations: list[dict[str, Any]] = field(default_factory=list)
    p7_readiness_warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    """Generate a simple run ID."""
    return datetime.now(timezone.utc).strftime("bench_%Y%m%d_%H%M%S")
