"""Graph Retriever — query P5.1 Unified Evidence Graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GraphRetriever:
    """Query the unified evidence graph."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.warnings: list[str] = []
        self._engine = None

    def is_available(self) -> bool:
        p = self.root / "05_Knowledge/unified_evidence_graph/graph_nodes.json"
        return p.exists()

    def _get_engine(self):
        if self._engine is None and self.is_available():
            try:
                from scientra.knowledge.unified_graph.graph_query_engine import GraphQueryEngine
                nodes = json.loads((self.root / "05_Knowledge/unified_evidence_graph/graph_nodes.json").read_text(encoding="utf-8"))
                ep = self.root / "05_Knowledge/unified_evidence_graph/graph_edges.json"
                edges = json.loads(ep.read_text(encoding="utf-8")) if ep.exists() else []
                self._engine = GraphQueryEngine(nodes, edges)
            except Exception as e:
                self.warnings.append(f"Graph load error: {e}")
        return self._engine

    def search_nodes(self, query: str, top_k: int = 20) -> list[dict]:
        """Search graph nodes by keyword."""
        engine = self._get_engine()
        if not engine:
            self.warnings.append("Graph not available — graph search skipped.")
            return []

        results = engine.search(keyword=query, limit=top_k)
        return [{
            "hit_id": f"graph_{n.get('node_id', '')[:20]}",
            "asset_type": "graph_node", "paper_id": n.get("paper_id", ""),
            "asset_id": n.get("node_id", ""),
            "title": n.get("title", ""), "text": n.get("text", "")[:500],
            "matched_fields": ["graph_search"],
            "source_module": "graph_retriever",
            "source_relative_path": "05_Knowledge/unified_evidence_graph/graph_nodes.json",
            "score": 0.7,
            "score_breakdown": {"graph_score": 0.7},
            "confidence": n.get("confidence", 0.5),
            "provenance": n.get("provenance", {}),
            "metadata": {"node_type": n.get("node_type", ""), "source_ids": n.get("source_ids", [])},
        } for n in results]

    def get_support_chain(self, node_id: str, chain_type: str = "claim_support") -> dict[str, Any] | None:
        """Get a support chain for a graph node."""
        engine = self._get_engine()
        if not engine:
            return None
        if chain_type == "claim_support":
            return engine.get_claim_support_chain(node_id)
        elif chain_type == "gap_hypothesis":
            return engine.get_gap_hypothesis_chain(node_id)
        return engine.get_neighborhood(node_id, depth=1)
