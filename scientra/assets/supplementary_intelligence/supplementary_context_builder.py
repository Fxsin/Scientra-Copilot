"""Supplementary Context Builder — build context for each supplementary asset.

Reuses P4.0.4 asset graph, P4.1 figure cards, P4.2 table cards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.assets.asset_registry import get_paper_dir
from scientra.assets.linking import AssetGraphBuilder


class SupplementaryContextBuilder:
    """Build comprehensive context for each supplementary asset."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def build_all(self, paper_id: str) -> list[dict[str, Any]]:
        builder = AssetGraphBuilder(self.root)
        links_data = builder.get_asset_links(paper_id)
        if not links_data.get("available"):
            return []

        registry = self._load_registry(paper_id)
        if not registry:
            return []

        asset_by_id = {a.get("asset_id", ""): a for a in (registry.assets if hasattr(registry, 'assets') else [])}
        links_by_asset = self._group_by(links_data.get("asset_links", []), "asset_id")
        mentions_by_id = {m.get("mention_id", ""): m for m in links_data.get("citation_mentions", [])}

        # Load related figure/table cards
        figure_cards = self._load_cards(paper_id, "figure_intelligence", "figure_cards.json")
        table_cards = self._load_cards(paper_id, "table_intelligence", "table_cards.json")

        contexts: list[dict[str, Any]] = []
        for asset_id, asset_info in asset_by_id.items():
            atype = asset_info.get("asset_type", "")
            # Target supplementary-type assets
            if atype not in ("supplementary_pdf", "attachment"):
                continue

            asset_links = links_by_asset.get(asset_id, [])
            norm_label = next((l.get("normalized_label", "") for l in asset_links if l.get("normalized_label")), "")
            if not norm_label:
                norm_label = asset_info.get("filename", "Supplementary File")

            body_mentions = []
            for link in asset_links:
                mid = link.get("citation_mention_id", "")
                m = mentions_by_id.get(mid)
                if m:
                    body_mentions.append({
                        "mention_id": m.get("mention_id", ""),
                        "sentence": m.get("sentence", ""),
                        "section": m.get("section", ""),
                        "source_type": m.get("source_type", ""),
                    })

            paper_dir = get_paper_dir(paper_id)
            asset_path = str(paper_dir / asset_info.get("relative_path", ""))

            # Match related figures and tables
            related_figures = self._find_related(figure_cards, norm_label, body_mentions, "figure")
            related_tables = self._find_related(table_cards, norm_label, body_mentions, "table")
            related_datasets: list[str] = []

            completeness = {
                "has_parseable_text": True,  # Will be validated by parser
                "has_sections": False,  # Will be updated after sectioning
                "has_body_mention": len(body_mentions) > 0,
                "has_linked_evidence": False,
                "has_related_assets": len(related_figures) + len(related_tables) > 0,
            }

            supp_id = f"supp_{asset_id}"
            contexts.append({
                "supplementary_id": supp_id,
                "paper_id": paper_id,
                "asset_id": asset_id,
                "normalized_label": norm_label,
                "asset_path": asset_path,
                "source_relative_path": asset_info.get("relative_path", ""),
                "caption": "",
                "body_mentions": body_mentions,
                "linked_evidence": [],
                "related_figures": related_figures,
                "related_tables": related_tables,
                "related_datasets": related_datasets,
                "context_completeness": completeness,
            })

        return contexts

    @staticmethod
    def _load_registry(paper_id: str):
        from scientra.assets.asset_registry import load_registry
        return load_registry(paper_id)

    @staticmethod
    def _load_cards(paper_id: str, subdir: str, filename: str) -> list[dict]:
        paper_dir = get_paper_dir(paper_id)
        fpath = paper_dir / subdir / filename
        if fpath.exists():
            try:
                return json.loads(fpath.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    @staticmethod
    def _group_by(items: list[dict], key: str) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for item in items:
            k = item.get(key, "")
            result.setdefault(k, []).append(item)
        return result

    @staticmethod
    def _find_related(cards: list[dict], supp_label: str, mentions: list[dict], prefix: str) -> list[str]:
        """Find figure/table cards related to this supplementary."""
        related: list[str] = []
        mention_text = " ".join(m.get("sentence", "") for m in mentions).lower()
        for card in cards:
            card_label = card.get("label", "").lower()
            card_text = (card.get("figure_summary", "") + card.get("table_summary", "")).lower()
            # Check if supplementary is mentioned in card or card label appears in mentions
            if supp_label.lower() in card_text or card_label in mention_text:
                cid = card.get("figure_id", card.get("table_id", ""))
                if cid:
                    related.append(cid)
        return related[:10]
