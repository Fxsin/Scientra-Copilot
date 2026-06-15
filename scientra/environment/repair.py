"""Repair suggestions for P6.6.1.

Generates actionable fix instructions for each FAIL/WARN check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scientra.environment.checks import run_all_checks


def generate_repair_suggestions(root: Path | None = None) -> list[dict[str, Any]]:
    """Generate repair suggestions for all non-PASS checks.

    Returns list of {problem, cause, fix, severity}.
    """
    checks = run_all_checks(root)
    suggestions: list[dict[str, Any]] = []

    for c in checks:
        status = c.get("status", "INFO")
        if status in ("PASS", "INFO"):
            continue

        # Build a repair entry
        suggestion: dict[str, Any] = {
            "problem": c["name"],
            "severity": status,
            "detail": c.get("detail", ""),
            "fix": c.get("fix", ""),
        }

        # Add contextual cause
        name = c["name"]
        if "python" in name.lower():
            suggestion["cause"] = "Python version is below 3.11 requirement."
        elif "node" in name.lower():
            suggestion["cause"] = "Node.js or npm is not installed or not in PATH."
        elif "git" in name.lower():
            suggestion["cause"] = "Git is not installed or not in PATH."
        elif "disk" in name.lower():
            suggestion["cause"] = "Available disk space is below the recommended threshold."
        elif "ram" in name.lower():
            suggestion["cause"] = "System RAM is below the recommended minimum."
        elif "cpu" in name.lower():
            suggestion["cause"] = "CPU core count is low for optimal performance."
        elif "gpu" in name.lower():
            suggestion["cause"] = "No CUDA-capable GPU detected. This is not required."
        elif "dependencies" in name.lower() or "dep" in name.lower():
            suggestion["cause"] = "Some Python packages are missing."
        elif "lancedb" in name.lower():
            suggestion["cause"] = "LanceDB has no data or is not accessible."
        elif "bge" in name.lower():
            suggestion["cause"] = "BGE-M3 embedding model is not yet downloaded."
        elif "api" in name.lower():
            suggestion["cause"] = "API key is missing, invalid, or not configured."
        elif "port" in name.lower():
            suggestion["cause"] = "Required ports are occupied by other programs."
        else:
            suggestion["cause"] = f"Check '{name}' configuration."

        suggestions.append(suggestion)

    return suggestions


def generate_repair_report(root: Path | None = None) -> dict[str, Any]:
    """Generate a repair report with summary and detailed suggestions.

    Returns:
        {
            "total_issues": 3,
            "critical": 1,
            "warnings": 2,
            "suggestions": [...],
        }
    """
    suggestions = generate_repair_suggestions(root)
    critical = [s for s in suggestions if s["severity"] == "FAIL"]
    warnings = [s for s in suggestions if s["severity"] == "WARN"]

    return {
        "total_issues": len(suggestions),
        "critical": len(critical),
        "warnings": len(warnings),
        "suggestions": suggestions,
    }
