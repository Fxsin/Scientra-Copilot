"""Tests for Graph Schema."""

import pytest
from scientra.knowledge.unified_graph.graph_schema import (
    make_node, make_edge, prov, NODE_TYPES, EDGE_TYPES,
)


class TestSchema:
    def test_make_node(self):
        n = make_node("n1", "paper", "p1", "Test Paper", "text", ["src1"], ["path1"], {"k": "v"}, 0.9, prov("test"))
        assert n["node_id"] == "n1"
        assert n["node_type"] == "paper"
        assert n["confidence"] == 0.9
        assert "k" in n["metadata"]

    def test_make_edge(self):
        e = make_edge("e1", "n1", "n2", "paper_has_evidence", "p1", 0.8, "source", prov("test"))
        assert e["edge_id"] == "e1"
        assert e["source_node_id"] == "n1"
        assert e["target_node_id"] == "n2"
        assert e["edge_type"] == "paper_has_evidence"

    def test_prov(self):
        p = prov("test_module", "test.json", "relative/test.json", "llm")
        assert p["source_module"] == "test_module"
        assert p["created_by"] == "llm"
        assert p["source_relative_path"] == "relative/test.json"

    def test_node_types_valid(self):
        for t in NODE_TYPES:
            assert isinstance(t, str) and len(t) > 0

    def test_edge_types_valid(self):
        for t in EDGE_TYPES:
            assert isinstance(t, str) and len(t) > 0
