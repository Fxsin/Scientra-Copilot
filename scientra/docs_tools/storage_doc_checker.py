"""Storage Doc Checker — scan docs for DB/DB_v2 references and absolute paths."""

from __future__ import annotations
from pathlib import Path
from typing import Any


class StorageDocChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def check(self) -> dict[str, Any]:
        db_v2_hits: list[str] = []
        abs_path_hits: list[str] = []
        issues: list[str] = []

        for doc_dir in ["docs", ""]:
            for ext in ["*.md", "*.rst", "*.txt"]:
                for f in (self.root / doc_dir).glob(ext):
                    try:
                        content = f.read_text(encoding="utf-8", errors="replace")
                        rel = str(f.relative_to(self.root))
                        if "DB/DB_v2" in content:
                            for i, line in enumerate(content.split("\n")):
                                if "DB/DB_v2" in line:
                                    db_v2_hits.append(f"{rel}:{i + 1}")
                        if ":\\" in content or "C:\\" in content:
                            abs_path_hits.append(rel)
                    except Exception:
                        pass

        if db_v2_hits:
            issues.append(f"Found {len(db_v2_hits)} DB/DB_v2 references")
        if abs_path_hits:
            issues.append(f"Found {len(abs_path_hits)} files with absolute paths")

        return {
            "clean": len(db_v2_hits) == 0,
            "db_v2_hits": db_v2_hits,
            "abs_path_files": abs_path_hits,
            "issues": issues,
            "checked": "docs/ + README.md",
        }
