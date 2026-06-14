"""Support Chain Builder — build evidence chains for ranked results."""

from __future__ import annotations

import uuid
from typing import Any


class SupportChainBuilder:
    """Build support chains from graph and asset data."""

    def build_chains(self, hits: list[dict], graph_retriever: Any = None) -> list[dict]:
        """Build support chains for top-ranked hits."""
        chains: list[dict] = []

        # For claim/graph node hits, build chain via graph
        if graph_retriever and graph_retriever.is_available():
            for h in hits[:5]:
                ntype = h.get("metadata", {}).get("node_type", h.get("asset_type", ""))
                nid = h.get("asset_id", "")
                if ntype == "claim" and nid:
                    chain = graph_retriever.get_support_chain(nid, "claim_support")
                    if chain and chain.get("nodes"):
                        chains.append(self._format_chain(chain, "claim_evidence_asset"))
                elif ntype == "gap" and nid:
                    chain = graph_retriever.get_support_chain(nid, "gap_hypothesis")
                    if chain and chain.get("nodes"):
                        chains.append(self._format_chain(chain, "gap_hypothesis_evidence"))

        # For figure/table hits, show linked evidence
        for h in hits[:5]:
            atype = h.get("asset_type", "")
            if atype in ("figure", "table"):
                chain = self._build_asset_chain(h, hits)
                if chain:
                    chains.append(chain)

        return chains

    def _build_asset_chain(self, hit: dict, all_hits: list[dict]) -> dict | None:
        """Build a simple asset→evidence chain."""
        linked_ev = [h for h in all_hits if h.get("asset_type") == "evidence" and h.get("paper_id") == hit.get("paper_id")]
        if not linked_ev:
            return None
        return {
            "chain_id": f"chain_{uuid.uuid4().hex[:8]}",
            "chain_type": "asset_evidence",
            "nodes": [{"id": hit["asset_id"], "type": hit["asset_type"], "title": hit["title"]},
                       {"id": linked_ev[0]["asset_id"], "type": "evidence", "title": linked_ev[0]["title"]}],
            "edges": [{"source": hit["asset_id"], "target": linked_ev[0]["asset_id"], "type": "supported_by"}],
            "summary": f"{hit['title']} is supported by evidence: {linked_ev[0]['title'][:100]}",
            "confidence": 0.5,
            "warnings": [],
        }

    @staticmethod
    def _format_chain(chain: dict, ctype: str) -> dict:
        nodes = [{"id": n.get("node_id", ""), "type": n.get("node_type", ""), "title": n.get("title", "")} for n in chain.get("nodes", [])]
        edges = [{"source": e.get("source_node_id", ""), "target": e.get("target_node_id", ""), "type": e.get("edge_type", "")} for e in chain.get("edges", [])]
        return {
            "chain_id": f"chain_{uuid.uuid4().hex[:8]}",
            "chain_type": ctype, "nodes": nodes, "edges": edges,
            "summary": f"Chain with {len(nodes)} nodes, {len(edges)} edges.",
            "confidence": 0.6, "warnings": [],
        }
