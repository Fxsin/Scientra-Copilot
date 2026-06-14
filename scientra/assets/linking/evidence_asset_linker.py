"""Evidence-Asset Linker — link evidence chunks to matched assets.

For each evidence chunk that mentions an asset, creates a relation record.
For each asset, tracks which evidence IDs reference it.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


# Relation types
RELATION_TYPES = [
    "supports",       # Evidence supports/confirms the figure/table finding
    "illustrates",    # Figure/table illustrates the evidence
    "reports_data",   # Figure/table reports data described in evidence
    "method_detail",  # Supplementary material provides method details
    "unknown",        # Unclear relationship
]


class EvidenceAssetLinker:
    """Link evidence chunks to matched assets based on citation mentions."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()

    def link(
        self,
        paper_id: str,
        mentions: list[dict[str, Any]],
        asset_links: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create evidence-asset relation links.

        Args:
            paper_id: The paper ID.
            mentions: All citation mentions (from CitationParser).
            asset_links: Matched asset links (from AssetMatcher).

        Returns:
            List of evidence-asset link dicts.
        """
        evidence_links: list[dict[str, Any]] = []

        # Build lookup: mention_id -> asset_id + confidence
        mention_to_asset: dict[str, dict[str, Any]] = {}
        for link in asset_links:
            mid = link.get("citation_mention_id", "")
            if mid:
                mention_to_asset[mid] = {
                    "asset_id": link.get("asset_id", ""),
                    "confidence": link.get("confidence", 0.0),
                    "normalized_label": link.get("normalized_label", ""),
                }

        # Find mentions from evidence chunks
        for mention in mentions:
            if mention.get("source_type") != "evidence_chunk":
                continue

            mid = mention.get("mention_id", "")
            asset_info = mention_to_asset.get(mid)

            if not asset_info:
                continue

            asset_id = asset_info["asset_id"]
            if not asset_id:
                continue

            # Determine relation type
            relation = self._infer_relation(mention)

            ev_link = {
                "evidence_id": mention.get("source_id", ""),
                "asset_id": asset_id,
                "mention_id": mid,
                "relation": relation,
                "confidence": asset_info["confidence"],
                "citation_text": mention.get("citation_text", ""),
                "normalized_label": asset_info["normalized_label"],
                "sentence": mention.get("sentence", ""),
                "evidence_field": mention.get("evidence_field", ""),
                "evidence_index": mention.get("evidence_index", -1),
            }

            evidence_links.append(ev_link)

        return evidence_links

    def build_asset_evidence_index(
        self,
        evidence_links: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        """Build reverse index: asset_id -> list of evidence_ids.

        Args:
            evidence_links: Output from link().

        Returns:
            dict mapping asset_id to list of evidence_ids.
        """
        index: dict[str, list[str]] = {}
        for link in evidence_links:
            asset_id = link.get("asset_id", "")
            evidence_id = link.get("evidence_id", "")
            if asset_id and evidence_id:
                if asset_id not in index:
                    index[asset_id] = []
                if evidence_id not in index[asset_id]:
                    index[asset_id].append(evidence_id)
        return index

    @staticmethod
    def _infer_relation(mention: dict[str, Any]) -> str:
        """Infer the relation type from the mention context."""
        sentence = mention.get("sentence", "").lower()
        context_before = mention.get("context_before", "").lower()
        context = sentence + " " + context_before

        # Method-related keywords
        method_keywords = [
            "method", "protocol", "procedure", "detailed in",
            "described in", "see supplementary", "see si",
        ]
        if any(kw in context for kw in method_keywords):
            return "method_detail"

        # Data reporting keywords
        data_keywords = [
            "data shown", "data presented", "summarizes", "reports",
            "lists", "provides", "contains", "dataset",
        ]
        if any(kw in context for kw in data_keywords):
            return "reports_data"

        # Illustration keywords
        illustrate_keywords = [
            "shown in", "illustrated", "depicted", "presented in",
            "see figure", "see fig", "plotted", "visualized",
        ]
        if any(kw in context for kw in illustrate_keywords):
            return "illustrates"

        # Support keywords
        support_keywords = [
            "support", "confirm", "validate", "consistent with",
            "demonstrate", "reveal", "indicate", "suggest",
        ]
        if any(kw in context for kw in support_keywords):
            return "supports"

        return "unknown"
