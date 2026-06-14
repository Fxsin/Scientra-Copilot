"""Tests for Graph Validator."""

import pytest
from scientra.knowledge.unified_graph.graph_validator import GraphValidator
from scientra.knowledge.unified_graph.graph_schema import make_node, make_edge


class TestValidator:
    def test_valid_graph(self):
        v = GraphValidator()
        nodes = [make_node("n1", "paper", "p1"), make_node("n2", "evidence", "p1")]
        edges = [make_edge("e1", "n1", "n2", "paper_has_evidence", "p1")]
        r = v.validate(nodes, edges)
        assert r["valid"]
        assert r["error_count"] == 0

    def test_orphan_detection(self):
        v = GraphValidator()
        nodes = [make_node("n1", "paper", "p1"), make_node("n2", "evidence", "p1", "Orphan")]
        edges = [make_edge("e1", "n1", "n1", "paper_has_evidence", "p1")]  # Self-referencing, n2 is orphan
        r = v.validate(nodes, edges)
        assert r["orphan_count"] >= 1

    def test_invalid_edge(self):
        v = GraphValidator()
        nodes = [make_node("n1", "paper", "p1")]
        edges = [make_edge("e1", "n1", "nonexistent", "paper_has_evidence")]
        r = v.validate(nodes, edges)
        assert not r["valid"]
        assert r["error_count"] >= 1
