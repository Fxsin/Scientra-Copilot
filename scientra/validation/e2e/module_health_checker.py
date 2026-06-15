"""Module Health Checker — verify all P4/P5 modules are importable and CLI files exist."""

from __future__ import annotations
from pathlib import Path
from typing import Any

MODULES = [
    "scientra.assets.linking", "scientra.assets.figure_intelligence",
    "scientra.assets.table_intelligence", "scientra.assets.supplementary_intelligence",
    "scientra.cross_asset_query", "scientra.knowledge.unified_graph",
    "scientra.datasets.intelligence", "scientra.agents.research_agent",
    "scientra.validation.e2e",
]

SCRIPTS = [
    "Scripts/build_asset_links.py", "Scripts/build_figure_intelligence.py",
    "Scripts/build_table_intelligence.py", "Scripts/build_supplementary_intelligence.py",
    "Scripts/build_unified_evidence_graph.py", "Scripts/query_cross_assets.py",
    "Scripts/build_dataset_intelligence.py", "Scripts/query_datasets.py",
    "Scripts/ask_research_agent.py",
]


class ModuleHealthChecker:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def check(self) -> dict[str, Any]:
        modules, script_status = {}, {}
        warnings = []

        for mod in MODULES:
            try:
                __import__(mod)
                modules[mod] = "ok"
            except Exception as e:
                modules[mod] = f"failed: {e}"
                warnings.append(f"Module {mod} import failed: {e}")

        for script in SCRIPTS:
            p = self.root / script
            script_status[script] = "exists" if p.exists() else "missing"
            if not p.exists():
                warnings.append(f"Script missing: {script}")

        return {
            "modules": modules,
            "scripts": script_status,
            "all_modules_ok": all(v == "ok" for v in modules.values()),
            "all_scripts_exist": all(v == "exists" for v in script_status.values()),
            "warnings": warnings,
        }
