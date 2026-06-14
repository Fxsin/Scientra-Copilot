"""Cross-Asset Answer Builder — generate deterministic answer from results (no LLM)."""

from __future__ import annotations

from typing import Any


class CrossAssetAnswerBuilder:
    """Build evidence-only deterministic answers without LLM."""

    def build_answer(self, query: str, hits: list[dict], support_chains: list[dict], resolved_intent: str) -> dict[str, Any]:
        """Build a deterministic answer from search results.

        Returns dict with answer, grouped_results, citations, warnings.
        """
        grouped = self._group_hits(hits)
        answer = self._compose_answer(query, hits, resolved_intent, grouped)
        citations = self._build_citations(hits[:10])

        warnings: list[str] = []
        if not hits:
            warnings.append("No results found for this query.")
        if all(h.get("score", 0) < 0.3 for h in hits):
            warnings.append("All results have low relevance scores — query may need refinement.")
        if not support_chains:
            warnings.append("No support chains could be built — graph data may be unavailable.")

        return {
            "answer": answer,
            "grouped_results": {k: v[:5] for k, v in grouped.items() if v},
            "citations": citations,
            "warnings": warnings,
        }

    @staticmethod
    def _group_hits(hits: list[dict]) -> dict[str, list[dict]]:
        g: dict[str, list[dict]] = {}
        for h in hits:
            at = h.get("asset_type", "unknown")
            g.setdefault(at, []).append(h)
        return g

    @staticmethod
    def _compose_answer(query: str, hits: list[dict], intent: str, grouped: dict) -> str:
        if not hits:
            return f"No results found for query: '{query}'."

        top = hits[0]
        total = len(hits)
        parts = [f"Found {total} result(s) for '{query}'."]

        # Top hit info
        parts.append(f"Top result: {top.get('title', '')[:120]} (score: {top.get('score', 0):.2f})")

        # Grouped summary
        for atype, items in sorted(grouped.items()):
            if items:
                parts.append(f"  - {atype}: {len(items)} hit(s)")

        # Source diversity
        papers = {h.get("paper_id", "") for h in hits if h.get("paper_id")}
        if papers:
            parts.append(f"Across {len(papers)} paper(s).")

        return " ".join(parts)

    @staticmethod
    def _build_citations(hits: list[dict]) -> list[dict]:
        return [{
            "ref_id": f"cite_{i + 1}",
            "asset_type": h.get("asset_type", ""),
            "paper_id": h.get("paper_id", ""),
            "title": h.get("title", ""),
            "source_relative_path": h.get("source_relative_path", ""),
            "score": h.get("score", 0),
        } for i, h in enumerate(hits[:10])]
