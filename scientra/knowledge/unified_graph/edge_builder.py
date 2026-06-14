"""Edge Builder — construct unified graph edges connecting nodes."""

from __future__ import annotations

import uuid
from typing import Any

from scientra.knowledge.unified_graph.graph_schema import make_edge, prov


class EdgeBuilder:
    """Build all edge types for the unified evidence graph."""

    def __init__(self, warnings: list[str] | None = None) -> None:
        self.warnings = warnings or []

    def build_all(self, paper_data: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build all edges connecting the given nodes."""
        edges: list[dict[str, Any]] = []
        pid = paper_data.get("paper_id", "")
        nodes_by_type = self._index_by_type(nodes)
        paper_nodes = nodes_by_type.get("paper", [])

        if not paper_nodes:
            return edges
        paper_id = paper_nodes[0]["node_id"]

        # Paper → Evidence/Method
        for ev in nodes_by_type.get("evidence", []) + nodes_by_type.get("method", []):
            edges.append(make_edge(
                self._eid(), paper_id, ev["node_id"], "paper_has_evidence", pid, 0.7,
                provenance=prov("evidence_extraction"),
            ))

        # Paper → Figure
        for f in nodes_by_type.get("figure", []):
            edges.append(make_edge(
                self._eid(), paper_id, f["node_id"], "paper_has_figure", pid, 0.8,
                provenance=prov("figure_intelligence"),
            ))

        # Paper → Table
        for t in nodes_by_type.get("table", []):
            edges.append(make_edge(
                self._eid(), paper_id, t["node_id"], "paper_has_table", pid, 0.8,
                provenance=prov("table_intelligence"),
            ))

        # Paper → Supplementary
        for s in nodes_by_type.get("supplementary", []):
            edges.append(make_edge(
                self._eid(), paper_id, s["node_id"], "paper_has_supplementary", pid, 0.7,
                provenance=prov("supplementary_intelligence"),
            ))

        # Evidence → Claim (text similarity heuristic)
        claims = nodes_by_type.get("claim", [])
        evidence_nodes = nodes_by_type.get("evidence", [])
        for ev in evidence_nodes:
            ev_text = ev.get("text", "").lower()
            for cl in claims:
                cl_text = cl.get("text", "").lower()
                if self._text_overlap(ev_text, cl_text) > 0.3:
                    edges.append(make_edge(
                        self._eid(), ev["node_id"], cl["node_id"], "evidence_supports_claim",
                        pid, 0.5, provenance=prov("graph_construction"),
                    ))

        # Evidence linked → Figure/Table (via label mentions)
        for ev in evidence_nodes:
            ev_text = ev.get("text", "")
            for f in nodes_by_type.get("figure", []):
                label = f.get("metadata", {}).get("label", "")
                if label and label.lower() in ev_text.lower():
                    edges.append(make_edge(
                        self._eid(), ev["node_id"], f["node_id"], "evidence_linked_to_figure",
                        pid, 0.6, evidence_source=ev_text[:100],
                        provenance=prov("asset_linking"),
                    ))
            for t in nodes_by_type.get("table", []):
                label = t.get("metadata", {}).get("label", "")
                if label and label.lower() in ev_text.lower():
                    edges.append(make_edge(
                        self._eid(), ev["node_id"], t["node_id"], "evidence_linked_to_table",
                        pid, 0.6, evidence_source=ev_text[:100],
                        provenance=prov("asset_linking"),
                    ))

        # Figure/Table → Claim (via shared text)
        for asset_type, edge_type in [("figure", "figure_supports_claim"), ("table", "table_supports_claim")]:
            for asset in nodes_by_type.get(asset_type, []):
                asset_text = asset.get("text", "").lower()
                for cl in claims:
                    if self._text_overlap(asset_text, cl.get("text", "").lower()) > 0.2:
                        edges.append(make_edge(
                            self._eid(), asset["node_id"], cl["node_id"], edge_type,
                            pid, 0.4, provenance=prov("graph_construction"),
                        ))

        # Gap → Hypothesis (via same paper)
        gaps = nodes_by_type.get("gap", [])
        hyps = nodes_by_type.get("hypothesis", [])
        for g in gaps:
            for h in hyps:
                edges.append(make_edge(
                    self._eid(), h["node_id"], g["node_id"], "hypothesis_addresses_gap",
                    pid, 0.5, provenance=prov("ai_enrichment"),
                ))

        # Hypothesis → Evidence (via text overlap)
        for h in hyps:
            h_text = h.get("text", "").lower()
            for ev in evidence_nodes:
                if self._text_overlap(h_text, ev.get("text", "").lower()) > 0.2:
                    edges.append(make_edge(
                        self._eid(), h["node_id"], ev["node_id"], "hypothesis_supported_by_evidence",
                        pid, 0.4, provenance=prov("graph_construction"),
                    ))

        return edges

    def build_global_edges(self, all_paper_nodes: list[dict[str, Any]], gap_clusters: Any, hyp_clusters: Any) -> list[dict[str, Any]]:
        """Build global edges (cross-paper connections)."""
        edges: list[dict[str, Any]] = []

        # Cross-paper gap connections from clusters
        if isinstance(gap_clusters, list):
            for cluster in gap_clusters:
                gap_ids = cluster.get("gap_ids", cluster.get("member_ids", []))
                for i in range(len(gap_ids)):
                    for j in range(i + 1, len(gap_ids)):
                        edges.append(make_edge(
                            self._eid(), gap_ids[i], gap_ids[j], "gap_related_to_gap",
                            confidence=float(cluster.get("coherence", 0.5)),
                            provenance=prov("ai_enrichment", "gap_clusters.json"),
                        ))

        # Cross-paper hypothesis connections
        if isinstance(hyp_clusters, list):
            for cluster in hyp_clusters:
                hyp_ids = cluster.get("hypothesis_ids", cluster.get("member_ids", []))
                for i in range(len(hyp_ids)):
                    for j in range(i + 1, len(hyp_ids)):
                        edges.append(make_edge(
                            self._eid(), hyp_ids[i], hyp_ids[j], "hypothesis_related_to_hypothesis",
                            confidence=float(cluster.get("coherence", 0.5)),
                            provenance=prov("ai_enrichment", "hypothesis_clusters.json"),
                        ))

        # Entity co-occurrence edges (shared entities across papers)
        ent_nodes = [n for n in all_paper_nodes if n.get("node_type") == "entity"]
        ent_names: dict[str, list[str]] = {}
        for n in ent_nodes:
            name = n.get("title", "").lower()
            if name:
                ent_names.setdefault(name, []).append(n["node_id"])
        for name, nids in ent_names.items():
            if len(nids) > 1:
                for i in range(len(nids)):
                    for j in range(i + 1, min(len(nids), 5)):
                        edges.append(make_edge(
                            self._eid(), nids[i], nids[j], "entity_shared_across_papers",
                            confidence=0.7, provenance=prov("graph_construction"),
                            metadata={"entity_name": name},
                        ))

        return edges

    @staticmethod
    def _index_by_type(nodes: list[dict]) -> dict[str, list[dict]]:
        idx: dict[str, list[dict]] = {}
        for n in nodes:
            idx.setdefault(n.get("node_type", "unknown"), []).append(n)
        return idx

    @staticmethod
    def _text_overlap(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        a_words = set(a.split())
        b_words = set(b.split())
        if not a_words or not b_words:
            return 0.0
        return len(a_words & b_words) / min(len(a_words), len(b_words))

    @staticmethod
    def _eid() -> str:
        return f"edge_{uuid.uuid4().hex[:10]}"
