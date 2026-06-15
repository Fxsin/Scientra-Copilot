"""Diagnostics engine for P6.6.1.

Runs all checks, computes Health Score, categorizes issues.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scientra.environment.checks import run_all_checks


def compute_health_score(checks: list[dict[str, Any]]) -> int:
    """Compute a 0-100 health score from check results.

    Each check: PASS=10, WARN=5, INFO=5, FAIL=0.
    Max score = len(checks) * 10, normalized to 100.
    """
    max_score = len(checks) * 10
    if max_score == 0:
        return 100

    score = 0
    for c in checks:
        status = c.get("status", "INFO")
        if status == "PASS":
            score += 10
        elif status in ("WARN", "INFO"):
            score += 5
        # FAIL = 0

    return round((score / max_score) * 100)


def categorize_checks(checks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Categorize checks by status."""
    result: dict[str, list[dict[str, Any]]] = {"PASS": [], "WARN": [], "FAIL": [], "INFO": []}
    for c in checks:
        status = c.get("status", "INFO")
        result.setdefault(status, []).append(c)
    return result


def run_diagnostics(root: Path | None = None) -> dict[str, Any]:
    """Run full system diagnostics. Returns a comprehensive report dict.

    Returns:
        {
            "health_score": 92,
            "total_checks": 12,
            "passed": 8,
            "warnings": 3,
            "failed": 1,
            "status": "healthy",  # healthy / degraded / critical
            "checks": [...],
            "by_category": {"PASS": [...], "WARN": [...], "FAIL": [...]},
        }
    """
    checks = run_all_checks(root)
    categorized = categorize_checks(checks)
    score = compute_health_score(checks)

    passed = len(categorized.get("PASS", []))
    warnings = len(categorized.get("WARN", []))
    failed = len(categorized.get("FAIL", []))
    infos = len(categorized.get("INFO", []))

    if failed == 0 and warnings <= 2:
        overall = "healthy"
    elif failed == 0:
        overall = "degraded"
    else:
        overall = "critical"

    return {
        "health_score": score,
        "total_checks": len(checks),
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "info": infos,
        "status": overall,
        "checks": checks,
        "by_category": {k: v for k, v in categorized.items() if v},
    }
