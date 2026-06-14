"""Graph Input Loader — load all available data sources for graph construction.

Reads from multiple source locations with graceful fallback.
Missing files → warning, not crash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GraphInputLoader:
    """Flexible multi-source data loader for graph construction."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.warnings: list[str] = []

    def load_all(self) -> dict[str, Any]:
        """Load all available data sources. Returns dict of source_name → data."""
        data: dict[str, Any] = {}

        data["paper_registry"] = self._load_paper_registry()
        data["evidence"] = self._load_all_evidence()
        data["evidence_enrichment"] = self._load_all_from_dir("03_Assets/ai/evidence_enrichment")
        data["gaps"] = self._load_all_from_dir("03_Assets/ai/gaps")
        data["hypotheses"] = self._load_all_from_dir("03_Assets/ai/hypotheses")
        data["summary_v2"] = self._load_all_from_dir("03_Assets/ai/summary_v2")
        data["figures_raw"] = self._load_all_from_dir("03_Assets/figure_assets", subfile="figures.json")
        data["tables_raw"] = self._load_all_from_dir("03_Assets/table_assets", subfile="tables.json")
        data["figure_cards"] = self._load_figure_cards()
        data["table_cards"] = self._load_table_cards()
        data["supplementary_cards"] = self._load_supplementary_cards()
        data["supplementary_evidence"] = self._load_supp_evidence()
        data["gap_clusters"] = self._load_json("05_Knowledge/cross_paper_gaps/gap_clusters.json")
        data["hypothesis_clusters"] = self._load_json("05_Knowledge/cross_paper_hypotheses/hypothesis_clusters.json")

        return data

    def load_paper(self, paper_id: str) -> dict[str, Any]:
        """Load all available data for a single paper."""
        data: dict[str, Any] = {"paper_id": paper_id}

        reg = self._load_paper_registry()
        papers = reg if isinstance(reg, list) else reg.get("papers", {})
        data["paper_meta"] = papers.get(paper_id, {})

        data["evidence"] = self._load_json(f"03_Evidence/{paper_id}/evidence.json") or self._load_json(f"04_Corpus/reasoning/evidence/{paper_id}/evidence.json") or {}
        data["evidence_enrichment"] = self._load_json(f"03_Assets/ai/evidence_enrichment/{paper_id}.json") or {}
        data["gaps"] = self._load_json(f"03_Assets/ai/gaps/{paper_id}.json") or {}
        data["hypotheses"] = self._load_json(f"03_Assets/ai/hypotheses/{paper_id}.json") or {}
        data["summary_v2"] = self._load_json(f"03_Assets/ai/summary_v2/{paper_id}.json") or {}

        # Figure data: try cards first, then raw assets
        data["figures"] = self._load_figure_cards_paper(paper_id) or self._load_raw_figures(paper_id)

        # Table data
        data["tables"] = self._load_table_cards_paper(paper_id) or self._load_raw_tables(paper_id)

        # Supplementary
        data["supplementary_cards"] = self._load_json(f"03_Assets/supplementary_intelligence/cards/{paper_id}.json") or []
        data["supplementary_evidence"] = self._load_json(f"03_Assets/supplementary_intelligence/evidence/{paper_id}.json") or {}

        # Asset links
        data["asset_links"] = self._load_asset_links(paper_id)

        return data

    # ── Internal loaders ──

    def _load_paper_registry(self) -> dict:
        return self._load_json("05_Knowledge/paper_registry.json") or {}

    def _load_all_evidence(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        ev_dir = self.root / "03_Evidence"
        if ev_dir.exists():
            for d in ev_dir.iterdir():
                if d.is_dir():
                    f = d / "evidence.json"
                    if f.exists():
                        result[d.name] = self._load_json(str(f.relative_to(self.root))) or {}
        return result

    def _load_all_from_dir(self, rel_dir: str, subfile: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        d = self.root / rel_dir
        if not d.exists():
            self.warnings.append(f"Directory not found: {rel_dir}")
            return result
        for f in sorted(d.iterdir()):
            if f.suffix == ".json":
                key = f.stem
                if subfile:
                    sub = f / subfile
                    if sub.exists():
                        result[key] = self._load_json(str(sub.relative_to(self.root))) or []
                    continue
                result[key] = self._load_json(str(f.relative_to(self.root))) or {}
        return result

    def _load_figure_cards(self) -> dict[str, list]:
        return self._scan_paper_dirs("figure_intelligence/figure_cards.json")

    def _load_table_cards(self) -> dict[str, list]:
        return self._scan_paper_dirs("table_intelligence/table_cards.json")

    def _load_supplementary_cards(self) -> dict[str, list]:
        result: dict[str, list] = {}
        d = self.root / "03_Assets/supplementary_intelligence/cards"
        if d.exists():
            for f in d.glob("*.json"):
                result[f.stem] = self._load_json(str(f.relative_to(self.root))) or []
        return result

    def _load_supp_evidence(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        d = self.root / "03_Assets/supplementary_intelligence/evidence"
        if d.exists():
            for f in d.glob("*.json"):
                result[f.stem] = self._load_json(str(f.relative_to(self.root))) or {}
        return result

    def _scan_paper_dirs(self, rel_path: str) -> dict[str, list]:
        result: dict[str, list] = {}
        papers_dir = self.root / "01_Sources/papers"
        if papers_dir.exists():
            for pd in papers_dir.iterdir():
                if pd.is_dir():
                    f = pd / rel_path
                    if f.exists():
                        result[pd.name] = self._load_json(str(f.relative_to(self.root))) or []
        return result

    def _load_raw_figures(self, paper_id: str) -> list:
        # Search 03_Assets/figure_assets for matching directory
        d = self.root / "03_Assets/figure_assets"
        if d.exists():
            for sub in d.iterdir():
                if sub.is_dir() and paper_id.replace("paper_", "") in sub.name:
                    f = sub / "figures.json"
                    if f.exists():
                        return self._load_json(str(f.relative_to(self.root))) or []
        return []

    def _load_raw_tables(self, paper_id: str) -> list:
        d = self.root / "03_Assets/table_assets"
        if d.exists():
            for sub in d.iterdir():
                if sub.is_dir() and paper_id.replace("paper_", "") in sub.name:
                    f = sub / "tables.json"
                    if f.exists():
                        return self._load_json(str(f.relative_to(self.root))) or []
        return []

    def _load_figure_cards_paper(self, paper_id: str) -> list:
        return self._scan_single_paper_dir(paper_id, "figure_intelligence/figure_cards.json")

    def _load_table_cards_paper(self, paper_id: str) -> list:
        return self._scan_single_paper_dir(paper_id, "table_intelligence/table_cards.json")

    def _scan_single_paper_dir(self, paper_id: str, rel: str) -> list:
        papers_dir = self.root / "01_Sources/papers"
        if papers_dir.exists():
            for pd in papers_dir.iterdir():
                f = pd / rel
                if f.exists():
                    return self._load_json(str(f.relative_to(self.root))) or []
        return []

    def _load_asset_links(self, paper_id: str) -> dict:
        result = self._scan_single_paper_dir(paper_id, "links/asset_links.json")
        return result if result else []

    def _load_json(self, rel_path: str) -> Any:
        p = self.root / rel_path
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            self.warnings.append(f"Failed to parse: {rel_path}")
            return None
