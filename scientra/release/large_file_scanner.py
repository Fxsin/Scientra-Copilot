"""Large File Scanner — detect files exceeding threshold."""

from __future__ import annotations
from pathlib import Path
from typing import Any

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".next", "venv", ".venv", "dist"}


class LargeFileScanner:
    def __init__(self, root: str | Path | None = None, max_mb: int = 20) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)
        self.max_bytes = max_mb * 1024 * 1024

    def scan(self) -> list[dict]:
        issues: list[dict] = []
        for f in self.root.rglob("*"):
            if not f.is_file(): continue
            if any(d in f.parts for d in SKIP_DIRS): continue
            try:
                size = f.stat().st_size
            except Exception:
                continue
            if size > self.max_bytes:
                mb = size / 1024 / 1024
                issues.append({"priority": "P1", "title": f"Large file: {f.name} ({mb:.1f} MB)", "detail": f"Exceeds {self.max_bytes // 1024 // 1024}MB threshold", "file": str(f.relative_to(self.root))})
        return issues
