"""Cost and usage tracking for AI calls.

Writes usage records to 10_System/logs/ai_usage/usage_YYYY-MM.jsonl
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

# ── Path Resolution ──


def _detect_project_root() -> Path:
    """Walk up from this file until Config/llm_config.yaml is found."""
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "Config" / "llm_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
USAGE_LOG_DIR = PROJECT_ROOT / "10_System" / "logs" / "ai_usage"

# Thread-safe write lock
_write_lock = threading.Lock()


def _usage_log_path() -> Path:
    """Get today's usage log path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m")
    return USAGE_LOG_DIR / f"usage_{today}.jsonl"


def log_usage(
    timestamp: str,
    provider: str,
    model: str,
    task_name: str,
    paper_id: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cost_estimate: float,
    success: bool,
    error: str = "",
) -> None:
    """Append a usage record to today's JSONL log file.

    Thread-safe. Never raises — failures are silently ignored to avoid
    disrupting the main application flow.
    """
    record = {
        "timestamp": timestamp,
        "provider": provider,
        "model": model,
        "task_name": task_name,
        "paper_id": paper_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_estimate": cost_estimate,
        "success": success,
        "error": error,
    }

    try:
        USAGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = _usage_log_path()
        with _write_lock:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Never let logging failures propagate
        pass


def get_usage_summary(days: int = 30) -> dict:
    """Get a summary of usage for the last N days.

    Returns:
        dict with total_calls, total_cost, by_provider, by_task, daily
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    summary = {
        "total_calls": 0,
        "total_success": 0,
        "total_failure": 0,
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "by_provider": {},
        "by_task": {},
        "daily": {},
    }

    if not USAGE_LOG_DIR.exists():
        return summary

    for log_file in sorted(USAGE_LOG_DIR.glob("usage_*.jsonl")):
        try:
            for line in log_file.read_text(encoding="utf-8").strip().split("\n"):
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Filter by date
                ts = record.get("timestamp", "")
                if ts and ts < cutoff.isoformat():
                    continue

                summary["total_calls"] += 1
                if record.get("success"):
                    summary["total_success"] += 1
                else:
                    summary["total_failure"] += 1

                cost = float(record.get("cost_estimate", 0))
                summary["total_cost"] += cost
                summary["total_input_tokens"] += int(record.get("input_tokens", 0))
                summary["total_output_tokens"] += int(record.get("output_tokens", 0))

                provider = record.get("provider", "unknown")
                if provider not in summary["by_provider"]:
                    summary["by_provider"][provider] = {"calls": 0, "cost": 0.0}
                summary["by_provider"][provider]["calls"] += 1
                summary["by_provider"][provider]["cost"] += cost

                task = record.get("task_name", "unknown")
                if task not in summary["by_task"]:
                    summary["by_task"][task] = {"calls": 0, "cost": 0.0}
                summary["by_task"][task]["calls"] += 1
                summary["by_task"][task]["cost"] += cost

                # Daily aggregation
                day = ts[:10] if ts else "unknown"
                if day not in summary["daily"]:
                    summary["daily"][day] = {"calls": 0, "cost": 0.0}
                summary["daily"][day]["calls"] += 1
                summary["daily"][day]["cost"] += cost
        except Exception:
            continue

    summary["total_cost"] = round(summary["total_cost"], 6)
    return summary
