"""Tests for Graph Exporter."""

import json
import tempfile
from pathlib import Path

import pytest
from scientra.knowledge.unified_graph.graph_exporter import GraphExporter
from scientra.knowledge.unified_graph.graph_schema import make_node, make_edge


class TestExporter:
    def setup_method(self):
        self.nodes = [make_node("n1", "paper", "p1", "Test Paper")]
        self.edges = [make_edge("e1", "n1", "n1", "paper_has_evidence")]

    def test_export_json(self, tmp_path):
        exporter = GraphExporter(self.nodes, self.edges, tmp_path)
        exporter.export_all(json_f=True)
        p = tmp_path / "unified_evidence_graph.json"
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert len(data["nodes"]) == 1

    def test_export_graphml(self, tmp_path):
        exporter = GraphExporter(self.nodes, self.edges, tmp_path)
        exporter.export_all(graphml=True)
        p = tmp_path / "unified_evidence_graph.graphml"
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert "<graphml" in content

    def test_export_cyjs(self, tmp_path):
        exporter = GraphExporter(self.nodes, self.edges, tmp_path)
        exporter.export_all(cyjs=True)
        p = tmp_path / "unified_evidence_graph.cyjs"
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "elements" in data
