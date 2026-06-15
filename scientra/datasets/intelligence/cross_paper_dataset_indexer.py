"""Cross-Paper Dataset Indexer — build cross-paper entity and type indexes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CrossPaperDatasetIndexer:
    """Build and query cross-paper dataset indexes."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.out_dir = root / "05_Knowledge/dataset_intelligence" if isinstance(root, Path) else Path(root) / "05_Knowledge/dataset_intelligence"

    def build_indexes(self) -> dict[str, Any]:
        """Build all cross-paper indexes from existing dataset intelligence outputs."""
        ds_dir = self.root / "03_Assets/dataset_intelligence"
        entity_index: dict[str, list[dict]] = {}
        type_index: dict[str, list[dict]] = {}
        numeric_index: dict[str, list[dict]] = {}

        # Load all entity indexes
        ent_dir = ds_dir / "entity_indexes"
        if ent_dir.exists():
            for f in sorted(ent_dir.glob("*.json")):
                try:
                    entities = json.loads(f.read_text(encoding="utf-8"))
                    pid = f.stem
                    for e in (entities if isinstance(entities, list) else []):
                        norm = e.get("normalized_text", e.get("entity_text", "")).upper()
                        if norm:
                            entity_index.setdefault(norm, []).append({
                                "paper_id": pid, "dataset_id": e.get("dataset_id", ""),
                                "entity_type": e.get("entity_type", ""),
                                "column_name": e.get("column_name", ""),
                                "confidence": e.get("confidence", 0),
                            })
                except Exception:
                    pass

        # Load all dataset cards for type index
        cards_dir = ds_dir / "dataset_cards"
        if cards_dir.exists():
            for f in sorted(cards_dir.glob("*.json")):
                try:
                    cards = json.loads(f.read_text(encoding="utf-8"))
                    pid = f.stem
                    for c in (cards if isinstance(cards, list) else []):
                        dtype = c.get("dataset_type", "unknown")
                        type_index.setdefault(dtype, []).append({
                            "paper_id": pid, "dataset_id": c.get("dataset_id", ""),
                            "n_rows": c.get("n_rows", 0), "n_columns": c.get("n_columns", 0),
                            "quality_score": c.get("quality_score", 0),
                        })
                except Exception:
                    pass

        # Load all numeric profiles
        num_dir = ds_dir / "numeric_profiles"
        if num_dir.exists():
            for f in sorted(num_dir.glob("*.json")):
                try:
                    profiles = json.loads(f.read_text(encoding="utf-8"))
                    pid = f.stem
                    items = profiles if isinstance(profiles, list) else [profiles]
                    for p in items:
                        for nc in p.get("numeric_columns", []):
                            ftype = nc.get("field_type", "")
                            if ftype:
                                numeric_index.setdefault(ftype, []).append({
                                    "paper_id": pid, "column": nc.get("column_name", ""),
                                    "min": nc.get("min"), "max": nc.get("max"),
                                })
                except Exception:
                    pass

        # Write indexes
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._wj(self.out_dir / "cross_paper_entity_index.json", entity_index)
        self._wj(self.out_dir / "cross_paper_dataset_index.json", type_index)
        self._wj(self.out_dir / "cross_paper_numeric_index.json", numeric_index)

        return {
            "entity_count": len(entity_index),
            "type_count": len(type_index),
            "numeric_count": len(numeric_index),
            "output_dir": str(self.out_dir.relative_to(self.root)),
        }

    def query_entity(self, entity_text: str) -> list[dict]:
        """Query datasets by entity text."""
        f = self.out_dir / "cross_paper_entity_index.json"
        if not f.exists():
            return []
        try:
            idx = json.loads(f.read_text(encoding="utf-8"))
            return idx.get(entity_text.upper(), [])
        except Exception:
            return []

    def query_type(self, dataset_type: str) -> list[dict]:
        """Query datasets by type."""
        f = self.out_dir / "cross_paper_dataset_index.json"
        if not f.exists():
            return []
        try:
            idx = json.loads(f.read_text(encoding="utf-8"))
            return idx.get(dataset_type, [])
        except Exception:
            return []

    @staticmethod
    def _wj(p: Path, d: Any) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
