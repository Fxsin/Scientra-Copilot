"""Recommendation View Builder — convert P6.0 recs to displayable cards."""

from __future__ import annotations
from typing import Any


class RecommendationViewBuilder:
    def build(self, recs: dict[str, list[dict]]) -> list[dict]:
        cards = []
        for level in ["P0", "P1", "P2", "P3"]:
            for item in recs.get(level, []):
                cards.append({
                    "priority": level,
                    "title": item.get("title", ""),
                    "description": item.get("detail", ""),
                    "suggested_action": item.get("fix", ""),
                    "affected_module": item.get("title", "").split(":")[0] if ":" in item.get("title", "") else "",
                })
        return cards
