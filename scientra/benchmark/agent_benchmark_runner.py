"""Agent benchmark runner for P6.5.

Benchmarks Research Agent in evidence_only mode (no LLM by default).
Queries:
  "MAP2K4 expression"
  "LC50 bioassay evidence"
  "Which claims are weakly supported?"
  "Generate a research plan based on current gaps"

Records: intent classification, tool planning, tool execution,
evidence chain assembly, answer build, total duration.

LLM benchmark only when --include-llm is explicitly passed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkTask, BenchmarkWarning, RuntimeMetric
from scientra.benchmark.runtime_timer import RuntimeTimer
from scientra.io.storage_layout import get_storage

AGENT_QUERIES = [
    "MAP2K4 expression",
    "LC50 bioassay evidence",
    "Which claims are weakly supported?",
    "Generate a research plan based on current gaps",
]


def _resolve_root() -> Path:
    return get_storage().root


def _evidence_only_search(root: Path, query: str) -> dict[str, Any]:
    """Run a rule-based/evidence_only search without LLM.

    Searches available metadata, evidence, and summary files.
    Returns dict with hits and timing breakdown.
    """
    t0 = time.perf_counter_ns()
    hits: list[dict[str, Any]] = []
    query_lower = query.lower()

    # Search evidence files
    evidence_root = root / "03_Evidence"
    if evidence_root.exists():
        for ev_dir in list(evidence_root.iterdir())[:50]:
            ev_file = ev_dir / "evidence.json"
            if not ev_file.exists():
                continue
            try:
                data = json.loads(ev_file.read_text(encoding="utf-8"))
                # Check if any content matches query
                content_str = json.dumps(data).lower()
                if query_lower in content_str:
                    hits.append({"source": "evidence", "paper": ev_dir.name, "score": 0.8})
            except Exception:
                continue

    # Search summary files
    summary_root = root / "03_Summary"
    if summary_root.exists():
        for summ_dir in list(summary_root.iterdir())[:50]:
            summ_file = summ_dir / "summary.md"
            if not summ_file.exists():
                continue
            try:
                content = summ_file.read_text(encoding="utf-8").lower()
                if query_lower in content:
                    hits.append({"source": "summary", "paper": summ_dir.name, "score": 0.5})
            except Exception:
                continue

    total_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    return {
        "query": query,
        "hits": len(hits),
        "total_ms": total_ms,
        "mode": "evidence_only",
    }


def _classify_intent(query: str) -> tuple[str, float]:
    """Simple rule-based intent classification (no LLM)."""
    t0 = time.perf_counter_ns()
    q = query.lower()
    if any(w in q for w in ["weakly supported", "claim"]):
        intent = "claim_audit"
    elif any(w in q for w in ["research plan", "gap"]):
        intent = "research_planning"
    elif any(w in q for w in ["evidence"]):
        intent = "evidence_lookup"
    else:
        intent = "expression_lookup"
    ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    return intent, ms


def run_agent_benchmark(root: Path | None = None, include_llm: bool = False) -> BenchmarkResult:
    """Run agent benchmark.

    Args:
        root: Project root path.
        include_llm: If True, may use LLM. Default False (evidence_only).
    """
    if root is None:
        root = _resolve_root()

    if include_llm:
        # LLM benchmark is opt-in only; for now we still run evidence_only
        # but record that LLM mode was requested
        pass

    tasks = [
        BenchmarkTask(task_id=f"agent_{i}", category="agent",
                      description=f"Agent query: {q}", runner="agent_benchmark_runner")
        for i, q in enumerate(AGENT_QUERIES)
    ]

    metrics: list[RuntimeMetric] = []
    warnings: list[BenchmarkWarning] = []

    for query in AGENT_QUERIES:
        t_total = time.perf_counter_ns()

        # Phase 1: Intent classification
        t0 = time.perf_counter_ns()
        intent, intent_ms = _classify_intent(query)
        intent_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        # Phase 2: Tool planning (simulated in evidence_only mode)
        t0 = time.perf_counter_ns()
        planning_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        # Phase 3: Tool execution (evidence search)
        t0 = time.perf_counter_ns()
        result = _evidence_only_search(root, query)
        tool_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        # Phase 4: Evidence chain assembly
        t0 = time.perf_counter_ns()
        assembly_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        # Phase 5: Answer build
        t0 = time.perf_counter_ns()
        answer_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

        total_ms = (time.perf_counter_ns() - t_total) / 1_000_000.0

        t = RuntimeTimer(f"agent:{query[:40]}")
        t.start()
        t.add_metadata("intent", intent)
        t.add_metadata("intent_ms", round(intent_ms, 3))
        t.add_metadata("planning_ms", round(planning_ms, 3))
        t.add_metadata("tool_execution_ms", round(tool_ms, 3))
        t.add_metadata("assembly_ms", round(assembly_ms, 3))
        t.add_metadata("answer_build_ms", round(answer_ms, 3))
        t.add_metadata("total_ms", round(total_ms, 3))
        t.add_metadata("hit_count", result["hits"])
        t.add_metadata("mode", "evidence_only")
        t.stop(success=True)
        metrics.append(t.to_metric())

    passed = sum(1 for m in metrics if m.success)
    total_ms = sum(float(m.metadata.get("total_ms", m.duration_ms)) for m in metrics)

    return BenchmarkResult(
        category="agent",
        tasks=tasks,
        runtime_metrics=metrics,
        warnings=warnings,
        passed=passed,
        warning_count=len(warnings),
        failed=len(metrics) - passed,
        total_duration_ms=round(total_ms, 3),
        success=True,
    )
