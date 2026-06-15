"""Path Hardcode Checker — scan for DB/DB_v2 and absolute paths."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".next", "venv", ".venv", "dist", "06_Index", "10_System/logs"}


class PathHardcodeChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def scan(self) -> list[dict]:
        issues: list[dict] = []

        for f in self.root.rglob("*.py"):
            if any(d in f.parts for d in SKIP_DIRS): continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                rel = str(f.relative_to(self.root))
            except Exception:
                continue

            if "DB/DB_v2" in content:
                for i, line in enumerate(content.split("\n")):
                    if "DB/DB_v2" in line and "never use" not in line.lower() and "not use" not in line.lower():
                        issues.append({"priority": "P0", "title": f"DB/DB_v2 reference", "detail": f"Line {i + 1}: {line.strip()[:80]}", "file": rel})
                        break

            # Check for Windows absolute paths
            if re.search(r"[A-Z]:\\[A-Za-z]", content):
                issues.append({"priority": "P2", "title": "Windows absolute path found", "detail": f"In {rel}", "file": rel})

        return issues
