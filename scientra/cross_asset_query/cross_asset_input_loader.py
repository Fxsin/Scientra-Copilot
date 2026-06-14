"""Cross-Asset Input Loader — load all asset types for querying."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CrossAssetInputLoader:
    """Load all available asset data for cross-asset querying."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.warnings: list[str] = []

    def load_all(self) -> dict[str, list[dict]]:
        """Load all asset types. Returns dict of asset_type → list of items."""
        data: dict[str, list[dict]] = {}

        data["evidence"] = self._load_evidence()
        data["figure"] = self._load_figures()
        data["table"] = self._load_tables()
        data["supplementary"] = self._load_supplementaries()
        data["supplementary_chunks"] = self._load_supp_chunks()
        data["graph"] = self._load_graph_nodes()
        data["gap"] = self._load_gaps()
        data["hypothesis"] = self._load_hypotheses()

        return data

    def _load_evidence(self) -> list[dict]:
        items: list[dict] = []
        ev_dir = self.root / "03_Evidence"
        if not ev_dir.exists():
            self.warnings.append("03_Evidence/ not found")
            return items
        for d in sorted(ev_dir.iterdir()):
            if d.is_dir():
                f = d / "evidence.json"
                if f.exists():
                    try:
                        ev = json.loads(f.read_text(encoding="utf-8"))
                        pid = d.name
                        for field in ["key_results", "core_findings", "discussion_points", "methods"]:
                            for i, item in enumerate(ev.get(field, []) if isinstance(ev.get(field), list) else []):
                                if isinstance(item, dict):
                                    txt = str(item.get("result", item.get("finding", item.get("name", item.get("quote", "")))))
                                    if txt and len(txt) > 20:
                                        items.append({
                                            "asset_type": "evidence", "paper_id": pid,
                                            "asset_id": f"{pid}:evidence:{field}:{i}",
                                            "title": txt[:100], "text": txt,
                                            "source_relative_path": f"03_Evidence/{pid}/evidence.json",
                                            "field": field, "confidence": 0.7 if item.get("confidence") == "high" else 0.5,
                                        })
                    except Exception:
                        pass
        return items

    def _load_figures(self) -> list[dict]:
        items: list[dict] = []
        # Try P4.1 figure cards first
        for loc in ["01_Sources/papers", "03_Assets/figure_assets"]:
            d = self.root / loc
            if not d.exists():
                continue
            for sub in d.iterdir():
                if sub.is_dir():
                    f = sub / "figure_intelligence/figure_cards.json" if loc == "01_Sources/papers" else sub / "figures.json"
                    if f.exists():
                        try:
                            cards = json.loads(f.read_text(encoding="utf-8"))
                            for c in (cards if isinstance(cards, list) else []):
                                items.append({
                                    "asset_type": "figure", "paper_id": sub.name,
                                    "asset_id": c.get("figure_id", c.get("asset_id", "")),
                                    "title": c.get("label", c.get("figure_label", "")),
                                    "text": c.get("caption", "")[:500],
                                    "key_finding": c.get("key_finding", ""),
                                    "source_relative_path": str(f.relative_to(self.root)),
                                    "confidence": float(c.get("confidence", 0.5)) if isinstance(c.get("confidence"), (int, float)) else 0.5,
                                    "evidence_type": c.get("evidence_type", ""),
                                })
                        except Exception:
                            pass
        if not items:
            self.warnings.append("No figure data found")
        return items

    def _load_tables(self) -> list[dict]:
        items: list[dict] = []
        for loc in ["01_Sources/papers", "03_Assets/table_assets"]:
            d = self.root / loc
            if not d.exists():
                continue
            for sub in d.iterdir():
                if sub.is_dir():
                    f = sub / "table_intelligence/table_cards.json" if loc == "01_Sources/papers" else sub / "tables.json"
                    if f.exists():
                        try:
                            cards = json.loads(f.read_text(encoding="utf-8"))
                            for c in (cards if isinstance(cards, list) else []):
                                items.append({
                                    "asset_type": "table", "paper_id": sub.name,
                                    "asset_id": c.get("table_id", c.get("asset_id", "")),
                                    "title": c.get("label", c.get("table_label", "")),
                                    "text": c.get("caption", "")[:500],
                                    "table_summary": c.get("table_summary", c.get("key_finding", "")),
                                    "source_relative_path": str(f.relative_to(self.root)),
                                    "table_type": c.get("table_type", ""),
                                    "confidence": 0.5,
                                })
                        except Exception:
                            pass
        if not items:
            self.warnings.append("No table data found")
        return items

    def _load_supplementaries(self) -> list[dict]:
        items: list[dict] = []
        d = self.root / "03_Assets/supplementary_intelligence/cards"
        if d.exists():
            for f in sorted(d.glob("*.json")):
                try:
                    cards = json.loads(f.read_text(encoding="utf-8"))
                    for c in (cards if isinstance(cards, list) else []):
                        items.append({
                            "asset_type": "supplementary", "paper_id": f.stem,
                            "asset_id": c.get("asset_id", ""),
                            "title": c.get("title", c.get("label", "")),
                            "text": c.get("supplementary_summary", "")[:500],
                            "source_relative_path": str(f.relative_to(self.root)),
                            "confidence": c.get("confidence", 0.5),
                        })
                except Exception:
                    pass
        if not items:
            self.warnings.append("No supplementary cards found")
        return items

    def _load_supp_chunks(self) -> list[dict]:
        items: list[dict] = []
        d = self.root / "03_Assets/supplementary_intelligence/chunks"
        if d.exists():
            for f in sorted(d.glob("*.json")):
                try:
                    chunks = json.loads(f.read_text(encoding="utf-8"))
                    for c in (chunks if isinstance(chunks, list) else []):
                        items.append({
                            "asset_type": "supplementary_chunk", "paper_id": f.stem,
                            "asset_id": c.get("asset_id", ""),
                            "title": c.get("chunk_type", ""),
                            "text": c.get("text", "")[:500],
                            "source_relative_path": str(f.relative_to(self.root)),
                            "confidence": 0.5,
                        })
                except Exception:
                    pass
        return items

    def _load_graph_nodes(self) -> list[dict]:
        f = self.root / "05_Knowledge/unified_evidence_graph/graph_nodes.json"
        if not f.exists():
            self.warnings.append("Unified graph not found")
            return []
        try:
            nodes = json.loads(f.read_text(encoding="utf-8"))
            return [{
                "asset_type": "graph_node", "paper_id": n.get("paper_id", ""),
                "asset_id": n.get("node_id", ""),
                "title": n.get("title", ""), "text": n.get("text", "")[:500],
                "source_relative_path": "05_Knowledge/unified_evidence_graph/graph_nodes.json",
                "node_type": n.get("node_type", ""), "confidence": n.get("confidence", 0.5),
            } for n in (nodes if isinstance(nodes, list) else [])]
        except Exception:
            self.warnings.append("Failed to load graph nodes")
            return []

    def _load_gaps(self) -> list[dict]:
        return self._load_ai_dir("03_Assets/ai/gaps", "gap", "gap")

    def _load_hypotheses(self) -> list[dict]:
        return self._load_ai_dir("03_Assets/ai/hypotheses", "hypothesis", "hypothesis")

    def _load_ai_dir(self, rel_dir: str, atype: str, key: str) -> list[dict]:
        items: list[dict] = []
        d = self.root / rel_dir
        if not d.exists():
            return items
        for f in sorted(d.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                lst = data.get(f"{key}s", data.get(key, []))
                for item in (lst if isinstance(lst, list) else []):
                    if isinstance(item, dict):
                        items.append({
                            "asset_type": atype, "paper_id": f.stem,
                            "asset_id": item.get(f"{key}_id", f"{f.stem}_{len(items)}"),
                            "title": str(item.get(key, ""))[:100],
                            "text": str(item.get(key, item.get("description", "")))[:500],
                            "source_relative_path": str(f.relative_to(self.root)),
                            "confidence": float(item.get("confidence", 0.5)) if isinstance(item.get("confidence"), (int, float)) else 0.5,
                        })
            except Exception:
                pass
        return items
