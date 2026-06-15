"""Dataset Comparison Engine — cross-paper entity and value comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DatasetComparisonEngine:
    """Compare entities/values across datasets and papers."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def compare_entity(self, entity_text: str) -> dict[str, Any]:
        """Find entity across all datasets, return comparison."""
        result: dict[str, list[dict]] = {}
        ds_dir = self.root / "03_Assets/dataset_intelligence"

        # Search entity indexes
        ent_dir = ds_dir / "entity_indexes"
        if ent_dir.exists():
            for f in sorted(ent_dir.glob("*.json")):
                try:
                    entities = json.loads(f.read_text(encoding="utf-8"))
                    pid = f.stem
                    for e in (entities if isinstance(entities, list) else []):
                        if entity_text.upper() in e.get("normalized_text", "").upper():
                            result.setdefault(pid, []).append(e)
                except Exception:
                    pass

        # Search numeric profiles for entity in top_positive/negative
        num_dir = ds_dir / "numeric_profiles"
        if num_dir.exists():
            for f in sorted(num_dir.glob("*.json")):
                try:
                    profiles = json.loads(f.read_text(encoding="utf-8"))
                    pid = f.stem
                    items = profiles if isinstance(profiles, list) else [profiles]
                    for p in items:
                        for item in p.get("top_positive", []) + p.get("top_negative", []):
                            if entity_text.upper() in item.get("entity", "").upper():
                                result.setdefault(pid, []).append({
                                    "entity_type": "numeric_hit",
                                    "entity_text": item.get("entity", ""),
                                    "value": item.get("value"),
                                    "column_name": "log2FC/effect_size",
                                    "source": "numeric_profile",
                                })
                except Exception:
                    pass

        papers = list(result.keys())
        return {
            "entity": entity_text,
            "found_in_papers": len(papers),
            "papers": papers,
            "hits": result,
        }

    def compare_dataset_types(self) -> dict[str, int]:
        """Summarize dataset types across all papers."""
        counts: dict[str, int] = {}
        ds_dir = self.root / "03_Assets/dataset_intelligence/cards"
        if ds_dir.exists():
            for f in sorted(ds_dir.glob("*.json")):
                try:
                    cards = json.loads(f.read_text(encoding="utf-8"))
                    for c in (cards if isinstance(cards, list) else []):
                        t = c.get("dataset_type", "unknown")
                        counts[t] = counts.get(t, 0) + 1
                except Exception:
                    pass
        return counts
