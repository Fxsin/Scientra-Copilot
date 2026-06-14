"""Cross-Asset Ranker — score and rank merged results."""

from __future__ import annotations

from typing import Any


class CrossAssetRanker:
    """Rank merged hits by multi-factor scoring."""

    def rank(self, hits: list[dict]) -> list[dict]:
        """Compute final scores and sort."""
        for h in hits:
            factors = h.get("score_breakdown", {})

            # Base score from retrieval
            base = h.get("score", 0.0)

            # Source diversity bonus
            sources = len(h.get("sources", ["keyword"]))
            diversity = min(sources * 0.05, 0.15)

            # Confidence bonus
            conf = h.get("confidence", 0.5)
            conf_bonus = conf * 0.1

            # Matched fields bonus
            n_fields = len(h.get("matched_fields", []))
            field_bonus = min(n_fields * 0.03, 0.15)

            final = base + diversity + conf_bonus + field_bonus

            h["score"] = round(final, 3)
            h["score_breakdown"] = {
                "base_score": round(base, 3),
                "source_diversity": round(diversity, 3),
                "confidence_bonus": round(conf_bonus, 3),
                "field_bonus": round(field_bonus, 3),
                "final_score": round(final, 3),
            }

        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits
