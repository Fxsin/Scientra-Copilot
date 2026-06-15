"""Gitignore Checker — verify .gitignore protects user data."""

from __future__ import annotations
from pathlib import Path
from typing import Any

REQUIRED_IGNORES = ["00_Inbox/", "01_Sources/", "03_Assets/", "05_Knowledge/", "06_Index/", "Config/llm_config.yaml", "10_System/logs", "*.lancedb"]


class GitignoreChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def check(self) -> list[dict]:
        issues: list[dict] = []
        gf = self.root / ".gitignore"
        if not gf.exists():
            issues.append({"priority": "P0", "title": ".gitignore missing", "detail": "No .gitignore file found"})
            return issues
        content = gf.read_text(encoding="utf-8")
        for pattern in REQUIRED_IGNORES:
            if pattern.replace("/", "") not in content.replace("/", ""):
                issues.append({"priority": "P0" if "Config" in pattern else "P1", "title": f"Missing ignore: {pattern}", "detail": f"Add '{pattern}' to .gitignore", "file": ".gitignore"})
        return issues
