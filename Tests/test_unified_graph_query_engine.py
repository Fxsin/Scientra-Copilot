"""Tests for Graph Query Engine."""

import pytest
from scientra.knowledge.unified_graph.graph_query_engine import GraphQueryEngine
from scientra.knowledge.unified_graph.graph_schema import make_node, make_edge


class TestQueryEngine:
    def setup_method(self):
        self.nodes = [
            make_node("p1", "paper", "paper_x", "Paper"),
            make_node("ev1", "evidence", "paper_x", "Finding"),
            make_node("cl1", "claim", "paper_x", "Claim"),
            make_node("fig1", "figure", "paper_x", "Fig 1"),
            make_node("gap1", "gap", "paper_x", "Gap"),
            make_node("hyp1", "hypothesis", "paper_x", "Hypothesis"),
        ]
        self.edges = [
            make_edge("e1", "p1", "ev1", "paper_has_evidence", "paper_x"),
            make_edge("e2", "ev1", "cl1", "evidence_supports_claim", "paper_x"),
            make_edge("e3", "ev1", "fig1", "evidence_linked_to_figure", "paper_x"),
            make_edge("e4", "hyp1", "gap1", "hypothesis_addresses_gap", "paper_x"),
            make_edge("e5", "hyp1", "ev1", "hypothesis_supported_by_evidence", "paper_x"),
        ]
        self.engine = GraphQueryEngine(self.nodes, self.edges)

    def test_get_node(self):
        assert self.engine.get_node("p1") is not None
        assert self.engine.get_node("nonexistent") is None

    def test_neighborhood(self):
        r = self.engine.get_neighborhood("ev1", depth=1)
        assert len(r["nodes"]) >= 1  # ev1 itself + neighbors

    def test_paper_subgraph(self):
        r = self.engine.get_paper_subgraph("paper_x")
        assert r["paper_id"] == "paper_x"
        assert len(r["nodes"]) == 6

    def test_claim_support_chain(self):
        r = self.engine.get_claim_support_chain("cl1")
        assert len(r["nodes"]) >= 1

    def test_gap_hypothesis_chain(self):
        r = self.engine.get_gap_hypothesis_chain("gap1")
        assert len(r["nodes"]) >= 1

    def test_search(self):
        results = self.engine.search(node_type="evidence")
        assert len(results) >= 1

    def test_stats(self):
        s = self.engine.get_stats()
        assert s["total_nodes"] == 6
        assert s["total_edges"] == 5
