"""Dashboard Data Loader — read P6.0 validation outputs."""

from __future__ import annotations
import json, csv
from pathlib import Path
from typing import Any


class DashboardDataLoader:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.vdir = self.root / "10_System/validation/e2e"

    def load_all(self) -> dict[str, Any]:
        return {
            "summary": self._load_json("e2e_validation_summary.json"),
            "inventory": self._load_json("pipeline_inventory.json"),
            "paper_details": self._load_json("paper_status_details.json"),
            "paper_csv": self._load_csv("paper_status_matrix.csv"),
            "storage": self._load_json("storage_layout_report.json"),
            "modules": self._load_json("module_health.json"),
            "query_eval": self._load_json("query_eval_results.json"),
            "agent_eval": self._load_json("agent_eval_results.json"),
            "recommendations": self._load_json("hardening_recommendations.json"),
        }

    def is_available(self) -> bool:
        return (self.vdir / "e2e_validation_summary.json").exists()

    def _load_json(self, name: str) -> Any:
        p = self.vdir / name
        if p.exists():
            try: return json.loads(p.read_text(encoding="utf-8"))
            except: pass
        return None

    def _load_csv(self, name: str) -> list[dict]:
        p = self.vdir / name
        if not p.exists(): return []
        with open(p, encoding="utf-8") as f:
            return list(csv.DictReader(f))
