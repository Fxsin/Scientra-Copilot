"""Evidence Chain Assembler — build evidence chains from tool results."""

from __future__ import annotations
import uuid
from typing import Any


class EvidenceChainAssembler:
    def assemble(self, tool_results: list[dict]) -> list[dict]:
        chains: list[dict] = []
        all_hits = []
        for tr in tool_results:
            d = tr.get("data", [])
            if isinstance(d, list):
                all_hits.extend(d)

        if not all_hits:
            return chains

        # Chain 1: Claim → Evidence
        claims = [h for h in all_hits if h.get("asset_type") in ("claim", "graph_node") and h.get("metadata", {}).get("node_type") == "claim"]
        evidence = [h for h in all_hits if h.get("asset_type") == "evidence"]
        if claims and evidence:
            chains.append(self._make_chain("claim_evidence_asset", [
                {"id": claims[0].get("asset_id", ""), "type": "claim", "title": claims[0].get("title", "")},
                {"id": evidence[0].get("asset_id", ""), "type": "evidence", "title": evidence[0].get("title", "")},
            ], f"Claim supported by evidence: {evidence[0].get('title', '')[:100]}"))

        # Chain 2: Entity → Dataset → Paper
        entities = [h for h in all_hits if h.get("asset_type") in ("dataset", "graph_node") and "entity" in str(h.get("metadata", {})).lower()]
        if entities:
            chains.append(self._make_chain("entity_dataset_paper", [
                {"id": entities[0].get("asset_id", ""), "type": "dataset", "title": entities[0].get("title", "")},
            ], f"Entity found in: {entities[0].get('title', '')[:100]}"))

        # Chain 3: Figure/Table → Evidence
        figs = [h for h in all_hits if h.get("asset_type") in ("figure", "table")]
        if figs and evidence:
            chains.append(self._make_chain("asset_evidence", [
                {"id": figs[0].get("asset_id", ""), "type": figs[0].get("asset_type", ""), "title": figs[0].get("title", "")},
                {"id": evidence[0].get("asset_id", ""), "type": "evidence", "title": evidence[0].get("title", "")},
            ], f"Asset linked to evidence: {evidence[0].get('title', '')[:100]}"))

        return chains

    @staticmethod
    def _make_chain(ctype: str, nodes: list[dict], summary: str) -> dict:
        return {"chain_id": f"chain_{uuid.uuid4().hex[:8]}", "chain_type": ctype,
                "nodes": nodes, "edges": [], "summary": summary, "confidence": 0.6, "warnings": []}
