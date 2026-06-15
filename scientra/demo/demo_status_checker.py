"""Demo Status Checker — check demo project state."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class DemoStatusChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def check(self) -> dict[str, Any]:
        src = (self.root / "examples/demo_project/article_bundle/Demo_Paper_001").exists()
        imported = (self.root / "00_Inbox/article_bundles/demo/Demo_Paper_001").exists()
        queries = (self.root / "09_Exports/demo_project/demo_query_results.json").exists()
        validated = (self.root / "10_System/validation/e2e/e2e_validation_summary.json").exists()

        return {
            "src_files_exist": src, "imported": imported, "queries_run": queries,
            "validated": validated, "ready_for_demo": src,
            "setup_instructions": [
                "python Scripts/create_demo_project.py --create-only",
                "python Scripts/create_demo_project.py --run-pipeline --run-validation --verbose",
                "python Scripts/run_demo_queries.py --use-cross-asset --use-dataset --verbose",
            ],
            "warning": "ALL DEMO DATA IS SYNTHETIC — FOR FUNCTIONALITY TESTING ONLY",
        }
