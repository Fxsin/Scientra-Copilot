"""Tests for Edge Builder."""

import pytest
from scientra.knowledge.unified_graph.edge_builder import EdgeBuilder
from scientra.knowledge.unified_graph.graph_schema import make_node


class TestEdgeBuilder:
    def test_paper_to_evidence(self):
        eb = EdgeBuilder()
        nodes = [
            make_node("paper1", "paper", "p1", "Test"),
            make_node("ev1", "evidence", "p1", "Finding"),
        ]
        edges = eb.build_all({"paper_id": "p1"}, nodes)
        paper_ev = [e for e in edges if e["edge_type"] == "paper_has_evidence"]
        assert len(paper_ev) == 1

    def test_paper_to_figure(self):
        eb = EdgeBuilder()
        nodes = [
            make_node("paper1", "paper", "p1", "Test"),
            make_node("fig1", "figure", "p1", "Fig 1", metadata={"label": "Figure 1"}),
        ]
        edges = eb.build_all({"paper_id": "p1"}, nodes)
        assert any(e["edge_type"] == "paper_has_figure" for e in edges)

    def test_evidence_linked_to_figure(self):
        eb = EdgeBuilder()
        nodes = [
            make_node("paper1", "paper", "p1", "Test"),
            make_node("ev1", "evidence", "p1", "Finding", text="See Figure 1 for the blot results."),
            make_node("fig1", "figure", "p1", "Fig 1", metadata={"label": "Figure 1"}),
        ]
        edges = eb.build_all({"paper_id": "p1"}, nodes)
        assert any(e["edge_type"] == "evidence_linked_to_figure" for e in edges)

    def test_hypothesis_addresses_gap(self):
        eb = EdgeBuilder()
        nodes = [
            make_node("paper1", "paper", "p1", "Test"),
            make_node("gap1", "gap", "p1", "Unknown mechanism"),
            make_node("hyp1", "hypothesis", "p1", "Protein X mediates"),
        ]
        edges = eb.build_all({"paper_id": "p1"}, nodes)
        assert any(e["edge_type"] == "hypothesis_addresses_gap" for e in edges)

    def test_global_edges(self):
        eb = EdgeBuilder()
        nodes = [
            make_node("gap1", "gap", "p1", "Gap A"),
            make_node("gap2", "gap", "p2", "Gap B"),
        ]
        clusters = [{"gap_ids": ["gap1", "gap2"], "coherence": 0.8}]
        edges = eb.build_global_edges(nodes, clusters, [])
        assert len(edges) > 0
