"""Test Command Checker — verify core commands are runnable (lightweight)."""

from __future__ import annotations
import subprocess, sys
from pathlib import Path
from typing import Any


class TestCommandChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def check(self) -> list[dict]:
        issues: list[dict] = []
        commands = [
            ([sys.executable, "-m", "pytest", "--version"], "pytest available"),
            ([sys.executable, "Scripts/update_docs.py", "--check-consistency"], "docs consistency check"),
            ([sys.executable, "Scripts/release_check.py", "--secrets"], "release secret scan"),
        ]
        for cmd, desc in commands:
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=30, cwd=str(self.root))
                if r.returncode != 0:
                    issues.append({"priority": "P2", "title": f"Command returned non-zero: {desc}", "detail": r.stderr.decode("utf-8", errors="replace")[:100]})
            except Exception as e:
                issues.append({"priority": "P2", "title": f"Command failed: {desc}", "detail": str(e)})
        return issues
