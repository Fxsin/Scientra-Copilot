"""Keyword Retriever — text-based search across all loaded assets."""

from __future__ import annotations

import re
from typing import Any


class KeywordRetriever:
    """Search loaded assets by keyword matching."""

    def search(self, query: str, assets: dict[str, list[dict]], top_k: int = 20) -> list[dict]:
        """Search across all asset types.

        Returns list of scored hit dicts.
        """
        hits: list[dict] = []
        query_lower = query.lower()
        query_terms = set(re.findall(r"[a-zA-Z0-9]+", query_lower))

        for atype, items in assets.items():
            if atype in ("supplementary_chunks",):
                continue  # Searched separately
            for item in items:
                score, matched = self._score(item, query_lower, query_terms)
                if score > 0:
                    hits.append(self._make_hit(item, score, matched))

        # Sort by score descending, take top_k
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]

    def _score(self, item: dict, query_lower: str, query_terms: set[str]) -> tuple[float, list[str]]:
        """Score an item against the query. Returns (score, matched_fields)."""
        score = 0.0
        matched: list[str] = []

        # Search text fields
        searchable = [
            ("title", item.get("title", ""), 2.0),
            ("text", item.get("text", ""), 1.0),
            ("key_finding", item.get("key_finding", ""), 1.5),
            ("table_summary", item.get("table_summary", ""), 1.0),
            ("evidence_type", item.get("evidence_type", ""), 0.5),
            ("table_type", item.get("table_type", ""), 0.5),
            ("node_type", item.get("node_type", ""), 0.5),
        ]

        for field_name, text, weight in searchable:
            if not text:
                continue
            text_lower = text.lower()
            if query_lower in text_lower:
                score += weight * 3.0
                matched.append(f"{field_name}_exact")
            else:
                term_matches = sum(1 for t in query_terms if t in text_lower)
                if term_matches > 0:
                    score += weight * term_matches * 0.5
                    matched.append(f"{field_name}_partial")

        return (score, matched)

    @staticmethod
    def _make_hit(item: dict, score: float, matched: list[str]) -> dict:
        return {
            "hit_id": f"kw_{item.get('asset_type', '')}_{item.get('asset_id', '')[:20]}",
            "asset_type": item.get("asset_type", "unknown"),
            "paper_id": item.get("paper_id", ""),
            "asset_id": item.get("asset_id", ""),
            "title": item.get("title", ""),
            "text": (item.get("text", ""))[:500],
            "matched_fields": matched,
            "source_module": "keyword_retriever",
            "source_relative_path": item.get("source_relative_path", ""),
            "score": round(score, 3),
            "score_breakdown": {"keyword_score": round(score, 3)},
            "confidence": item.get("confidence", 0.5),
            "provenance": {"source_module": "cross_asset_query", "created_by": "rule"},
            "metadata": {
                "key_finding": item.get("key_finding", ""),
                "table_type": item.get("table_type", ""),
                "evidence_type": item.get("evidence_type", ""),
                "node_type": item.get("node_type", ""),
            },
        }
