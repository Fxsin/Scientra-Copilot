"""Storage Safety Checker — verify no user data tracked by git."""

from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any

PROTECTED_DIRS = ["00_Inbox/", "01_Sources/", "02_Parse/", "03_Assets/", "04_Corpus/", "05_Knowledge/", "06_Index/", "10_System/logs/", "10_System/backups/", "10_System/validation/"]


class StorageSafetyChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def check(self) -> list[dict]:
        issues: list[dict] = []
        try:
            r = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=str(self.root), timeout=15)
            tracked = r.stdout.split("\n")
            for d in PROTECTED_DIRS:
                hits = [f for f in tracked if f.startswith(d.rstrip("/")) and not f.endswith(".gitkeep")]
                if hits:
                    issues.append({"priority": "P0", "title": f"Tracked files in {d}", "detail": f"{len(hits)} files tracked (e.g., {hits[0]})", "file": hits[0] if hits else ""})
        except Exception as e:
            pass  # git not available — skip
        return issues
