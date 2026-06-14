"""Result Merger — merge and deduplicate results from multiple retrievers."""

from __future__ import annotations

from typing import Any


class ResultMerger:
    """Merge keyword, vector, and graph results with deduplication."""

    def merge(self, keyword_hits: list[dict], vector_hits: list[dict], graph_hits: list[dict]) -> list[dict]:
        """Merge results from all retrievers, deduplicate, and combine scores."""
        merged: dict[str, dict] = {}  # key: asset_type:asset_id

        for hits, source in [(keyword_hits, "keyword"), (vector_hits, "vector"), (graph_hits, "graph")]:
            for h in hits:
                aid = h.get("asset_id", "")
                atype = h.get("asset_type", "")
                key = f"{atype}:{aid}"

                if key in merged:
                    existing = merged[key]
                    # Merge matched fields and scores
                    existing["matched_fields"] = list(set(existing.get("matched_fields", []) + h.get("matched_fields", [])))
                    existing["score"] = max(existing.get("score", 0), h.get("score", 0))
                    bd = dict(existing.get("score_breakdown", {}))
                    bd.update(h.get("score_breakdown", {}))
                    existing["score_breakdown"] = bd
                    existing["sources"] = existing.get("sources", []) + [source]
                else:
                    h["sources"] = [source]
                    merged[key] = h

        # Also deduplicate by title similarity
        result = list(merged.values())
        result = self._dedup_by_title(result)
        return result

    @staticmethod
    def _dedup_by_title(hits: list[dict]) -> list[dict]:
        """Remove near-duplicate hits based on title overlap."""
        seen: list[str] = []
        unique: list[dict] = []
        for h in sorted(hits, key=lambda x: x.get("score", 0), reverse=True):
            title = h.get("title", "").lower()
            is_dup = False
            for s in seen:
                if ResultMerger._overlap(title, s) > 0.8:
                    is_dup = True
                    break
            if not is_dup:
                seen.append(title)
                unique.append(h)
        return unique

    @staticmethod
    def _overlap(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        aw = set(a.split())
        bw = set(b.split())
        if not aw or not bw:
            return 0.0
        return len(aw & bw) / min(len(aw), len(bw))
