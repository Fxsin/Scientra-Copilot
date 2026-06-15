"""P6.4 Release Schema."""

from __future__ import annotations
from typing import Any

def make_issue(priority: str, title: str, detail: str = "", file: str = "") -> dict:
    return {"priority": priority, "title": title, "detail": detail, "file": file}

def make_report(p0: list[dict], p1: list[dict], p2: list[dict], p3: list[dict], checks: dict) -> dict:
    return {"P0": p0, "P1": p1, "P2": p2, "P3": p3, "checks": checks, "total_issues": len(p0) + len(p1) + len(p2) + len(p3), "passed": len(p0) == 0}
