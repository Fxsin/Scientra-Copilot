"""Cross-Asset Query Schema — type definitions for P5.2 query engine."""

from __future__ import annotations

from typing import Any


def make_query(
    query: str, paper_id: str = "", asset_types: list[str] | None = None,
    top_k: int = 20, use_vector: bool = True, use_graph: bool = True,
    use_llm: bool = False, min_confidence: float = 0.0,
) -> dict[str, Any]:
    return {
        "query": query, "paper_id": paper_id,
        "intent": "auto",
        "asset_types": asset_types or ["evidence", "figure", "table", "supplementary", "dataset", "graph", "gap", "hypothesis"],
        "top_k": top_k, "use_vector": use_vector, "use_graph": use_graph,
        "use_llm": use_llm, "min_confidence": min_confidence,
    }


def make_hit(
    hit_id: str, asset_type: str, paper_id: str, title: str = "", text: str = "",
    asset_id: str = "", matched_fields: list[str] | None = None,
    source_module: str = "", source_relative_path: str = "",
    score: float = 0.0, score_breakdown: dict | None = None,
    confidence: float = 0.5, provenance: dict | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    return {
        "hit_id": hit_id, "asset_type": asset_type, "paper_id": paper_id,
        "asset_id": asset_id, "title": title, "text": text[:500],
        "matched_fields": matched_fields or [], "source_module": source_module,
        "source_relative_path": source_relative_path,
        "score": round(score, 3), "score_breakdown": score_breakdown or {},
        "confidence": round(confidence, 2), "provenance": provenance or {},
        "metadata": metadata or {},
    }


def make_search_result(
    query: str, resolved_intent: str = "", answer: str = "",
    hits: list[dict] | None = None, support_chains: list[dict] | None = None,
    warnings: list[str] | None = None, stats: dict | None = None,
    mode: str = "evidence_only",
) -> dict[str, Any]:
    hits = hits or []
    grouped: dict[str, list[dict]] = {}
    for h in hits:
        at = h.get("asset_type", "unknown")
        grouped.setdefault(at, []).append(h)

    return {
        "query": query, "resolved_intent": resolved_intent,
        "answer": answer, "hits": hits, "grouped_hits": grouped,
        "support_chains": support_chains or [], "warnings": warnings or [],
        "stats": stats or {"total_hits": len(hits)},
        "mode": mode,
    }
