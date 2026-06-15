"""Docs Consistency Checker — verify required docs exist and README mentions key features."""

from __future__ import annotations
from pathlib import Path
from typing import Any

REQUIRED_DOCS = ["docs/USER_WORKFLOW.md", "docs/DEMO_PROJECT_GUIDE.md", "docs/IMPORT_WORKFLOW.md", "docs/CLI_REFERENCE.md", "docs/API_REFERENCE.md", "docs/TROUBLESHOOTING.md", "docs/STORAGE_LAYOUT_V3.md", "docs/RESEARCH_AGENT_GUIDE.md"]

README_CHECKS = ["Demo Project", "Quality Dashboard", "Research Agent", "Storage Layout v3", "Validation", "Cross-Asset Query", "Dataset Intelligence", "Unified Evidence Graph"]


class DocsConsistencyChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def check(self) -> dict[str, Any]:
        missing_docs = [d for d in REQUIRED_DOCS if not (self.root / d).exists()]
        readme = (self.root / "README.md").read_text(encoding="utf-8", errors="replace") if (self.root / "README.md").exists() else ""
        missing_readme = [c for c in README_CHECKS if c.lower() not in readme.lower()]

        return {
            "all_docs_exist": len(missing_docs) == 0,
            "missing_docs": missing_docs,
            "all_readme_checks": len(missing_readme) == 0,
            "missing_readme_mentions": missing_readme,
        }
