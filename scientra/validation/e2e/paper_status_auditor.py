"""Paper Status Auditor — per-paper completion matrix."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class PaperStatusAuditor:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def audit_all(self) -> list[dict]:
        results = []
        reg = self._load_registry()
        papers = reg if isinstance(reg, list) else reg.get("papers", {})
        for pid in (papers.keys() if isinstance(papers, dict) else [p.get("paper_id", "") for p in (papers if isinstance(papers, list) else [])]):
            results.append(self.audit_one(pid))
        return results

    def audit_one(self, paper_id: str) -> dict[str, Any]:
        s = {"paper_id": paper_id, "warnings": []}
        s["has_source"] = self._check_paper_dir(paper_id)
        s["has_parse"] = self._check(f"02_Parse/text/{paper_id}") or self._check(f"02_Parse/markdown/{paper_id}")
        s["has_evidence"] = self._check(f"03_Evidence/{paper_id}/evidence.json")
        s["has_asset_links"] = self._check_in_paper_dir(paper_id, "links/asset_links.json")
        s["has_figure_intelligence"] = self._check_in_paper_dir(paper_id, "figure_intelligence/figure_cards.json") or self._check_glob(f"03_Assets/figure_assets/*{paper_id.replace('paper_','')}*/figures.json")
        s["has_table_intelligence"] = self._check_in_paper_dir(paper_id, "table_intelligence/table_cards.json") or self._check_glob(f"03_Assets/table_assets/*{paper_id.replace('paper_','')}*/tables.json")
        s["has_supplementary_intelligence"] = self._check(f"03_Assets/supplementary_intelligence/cards/{paper_id}.json")
        s["has_dataset_intelligence"] = self._check(f"03_Assets/dataset_intelligence/dataset_cards/{paper_id}.json")
        s["has_graph_subgraph"] = self._check(f"05_Knowledge/unified_evidence_graph/paper_subgraphs/{paper_id}.json")
        s["has_cross_asset_support"] = s["has_evidence"] and self._check(f"05_Knowledge/unified_evidence_graph/graph_nodes.json")
        s["has_agent_traces"] = self._check(f"07_Agents/research_agent/traces")

        items = ["has_source", "has_evidence", "has_asset_links", "has_figure_intelligence",
                  "has_table_intelligence", "has_supplementary_intelligence", "has_dataset_intelligence",
                  "has_graph_subgraph"]
        s["completion_score"] = round(sum(1 for k in items if s.get(k)) / len(items), 2)

        if not s["has_evidence"]: s["warnings"].append("No evidence found")
        if not s["has_figure_intelligence"]: s["warnings"].append("No figure intelligence")
        if not s["has_table_intelligence"]: s["warnings"].append("No table intelligence")
        if s["completion_score"] < 0.3: s["warnings"].append("Very low completion score")

        return s

    def _check(self, rel: str) -> bool: return (self.root / rel).exists()
    def _check_paper_dir(self, pid: str) -> bool:
        for d in (self.root / "01_Sources/papers").iterdir():
            if d.is_dir() and (pid in d.name or d.name.replace("_", "").startswith(pid.replace("paper_", ""))):
                return True
        return False

    def _check_in_paper_dir(self, pid: str, rel: str) -> bool:
        papers = self.root / "01_Sources/papers"
        if not papers.exists(): return False
        for d in papers.iterdir():
            if d.is_dir() and (pid in d.name):
                return (d / rel).exists()
        return False

    def _check_glob(self, pattern: str) -> bool:
        return len(list(self.root.glob(pattern))) > 0

    def _load_registry(self) -> dict:
        p = self.root / "05_Knowledge/paper_registry.json"
        if p.exists():
            try: return json.loads(p.read_text(encoding="utf-8"))
            except: pass
        return {}
