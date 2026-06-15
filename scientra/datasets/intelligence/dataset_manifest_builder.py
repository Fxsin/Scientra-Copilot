"""Dataset Manifest Builder — identify dataset-like assets from registry and intelligence outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.assets.asset_registry import load_registry, get_paper_dir

DATASET_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv", ".txt"}


class DatasetManifestBuilder:
    """Identify and catalog dataset assets."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def build(self, paper_id: str) -> list[dict[str, Any]]:
        datasets: list[dict] = []

        # Source 1: Asset registry (supplementary_table, dataset types)
        registry = load_registry(paper_id)
        if registry:
            paper_dir = get_paper_dir(paper_id)
            assets = registry.assets if hasattr(registry, 'assets') else []
            for a in assets:
                atype = a.get("asset_type", "")
                filename = a.get("filename", "")
                ext = Path(filename).suffix.lower()
                if atype in ("supplementary_table", "dataset") and ext in DATASET_EXTENSIONS:
                    aid = a.get("asset_id", "")
                    datasets.append({
                        "dataset_id": f"ds_{aid}", "paper_id": paper_id,
                        "asset_id": aid,
                        "source_relative_path": str(paper_dir / a.get("relative_path", "")),
                        "file_type": ext.replace(".", ""),
                        "source_module": "asset_registry",
                        "linked_table_id": "", "linked_supplementary_id": "",
                        "status": "candidate", "confidence": 0.8,
                    })

        # Source 2: Table intelligence cards (already parsed tables that are dataset-like)
        table_cards = self._load_table_cards(paper_id)
        for tc in table_cards:
            ttype = tc.get("table_type", "")
            if ttype in ("differential_expression", "gene_expression", "bioassay_table",
                          "lc50_table", "primer_table", "pathway_enrichment"):
                datasets.append({
                    "dataset_id": f"ds_{tc.get('table_id', '')}",
                    "paper_id": paper_id,
                    "asset_id": tc.get("asset_id", ""),
                    "source_relative_path": tc.get("asset_path", ""),
                    "file_type": Path(tc.get("asset_path", "")).suffix.replace(".", ""),
                    "source_module": "table_intelligence",
                    "linked_table_id": tc.get("table_id", ""),
                    "linked_supplementary_id": "",
                    "status": "confirmed", "confidence": 0.9,
                })

        return datasets

    def _load_table_cards(self, paper_id: str) -> list[dict]:
        paper_dir = get_paper_dir(paper_id)
        p = paper_dir / "table_intelligence/table_cards.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []
