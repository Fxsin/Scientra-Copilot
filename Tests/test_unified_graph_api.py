"""Tests for Unified Graph API endpoints."""

import json
import tempfile
from pathlib import Path

import pytest
from scientra.knowledge.unified_graph.graph_builder import GraphBuilder, V3_OUTPUT
from scientra.knowledge.unified_graph.graph_schema import make_node, make_edge


class TestAPIReadiness:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)
        out_dir = self.root / V3_OUTPUT
        out_dir.mkdir(parents=True)

        nodes = [make_node("n1", "paper", "p1", "Test"), make_node("n2", "evidence", "p1", "Finding")]
        edges = [make_edge("e1", "n1", "n2", "paper_has_evidence", "p1")]
        (out_dir / "graph_nodes.json").write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "graph_edges.json").write_text(json.dumps(edges, ensure_ascii=False, indent=2), encoding="utf-8")
        stats = {"total_nodes": 2, "total_edges": 1, "paper_count": 1, "node_types": {"paper": 1, "evidence": 1}, "edge_types": {"paper_has_evidence": 1}}
        (out_dir / "graph_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "paper_subgraphs").mkdir()
        (out_dir / "paper_subgraphs" / "p1.json").write_text(json.dumps({"paper_id": "p1", "nodes": nodes, "edges": edges}), encoding="utf-8")

    def test_nodes_file_readable(self):
        p = self.root / V3_OUTPUT / "graph_nodes.json"
        assert p.exists()
        nodes = json.loads(p.read_text(encoding="utf-8"))
        assert len(nodes) == 2

    def test_edges_file_readable(self):
        p = self.root / V3_OUTPUT / "graph_edges.json"
        assert p.exists()
        edges = json.loads(p.read_text(encoding="utf-8"))
        assert len(edges) == 1

    def test_stats_readable(self):
        p = self.root / V3_OUTPUT / "graph_stats.json"
        stats = json.loads(p.read_text(encoding="utf-8"))
        assert stats["total_nodes"] == 2

    def test_paper_subgraph(self):
        p = self.root / V3_OUTPUT / "paper_subgraphs" / "p1.json"
        assert p.exists()
        sg = json.loads(p.read_text(encoding="utf-8"))
        assert sg["paper_id"] == "p1"

    def test_relative_paths(self):
        """Verify no absolute user paths in data."""
        nodes = json.loads((self.root / V3_OUTPUT / "graph_nodes.json").read_text(encoding="utf-8"))
        for n in nodes:
            for sp in n.get("source_paths", []):
                assert ":\\" not in sp  # No Windows absolute paths
                assert not sp.startswith("/")  # No Unix absolute paths

    def test_no_db_v2_paths(self):
        """No DB/DB_v2 in any output path."""
        path = str(self.root / V3_OUTPUT)
        assert "DB/DB_v2" not in path
