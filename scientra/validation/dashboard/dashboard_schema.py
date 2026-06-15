"""Dashboard Schema — P6.1 type definitions."""

from __future__ import annotations
from typing import Any


def make_summary(total_papers: int = 0, completed: int = 0, warned: int = 0,
                 avg_score: float = 0.0, p0: int = 0, p1: int = 0, p2: int = 0, p3: int = 0,
                 modules_ok: bool = False, storage_ok: bool = False, query_pass: int = 0,
                 agent_pass: int = 0, last_run: str = "") -> dict:
    return {"total_papers": total_papers, "completed_papers": completed,
            "warning_papers": warned, "failed_papers": total_papers - completed - warned,
            "average_completion_score": round(avg_score, 2),
            "p0_count": p0, "p1_count": p1, "p2_count": p2, "p3_count": p3,
            "module_pass_rate": 1.0 if modules_ok else 0.0,
            "storage_layout_ok": storage_ok, "query_eval_pass": query_pass,
            "agent_eval_pass": agent_pass, "last_validation_run": last_run}


def make_pipeline_health(stage: str, total: int, complete: int, status: str = "ok") -> dict:
    return {"stage": stage, "total_papers": total, "complete_papers": complete,
            "completion_pct": round(complete / total * 100, 1) if total else 0, "status": status}
