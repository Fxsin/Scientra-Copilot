"""Tests for Node Builder."""

import pytest
from scientra.knowledge.unified_graph.node_builder import NodeBuilder


class TestNodeBuilder:
    def test_empty_paper(self):
        nb = NodeBuilder()
        nodes = nb.build_all({"paper_id": "p_test", "paper_meta": {"title": "Test"}})
        paper_nodes = [n for n in nodes if n["node_type"] == "paper"]
        assert len(paper_nodes) == 1
        assert paper_nodes[0]["title"] == "Test"

    def test_evidence_nodes(self):
        nb = NodeBuilder()
        data = {
            "paper_id": "p1", "paper_meta": {"title": "T"},
            "evidence": {"key_results": [{"result": "Significant increase was observed in treatment group.", "confidence": "high"}],
                          "methods": [{"name": "Quantitative RT-qPCR Analysis", "quote": "RNA was extracted using Trizol reagent and reverse transcribed."}]},
        }
        nodes = nb.build_all(data)
        ev_nodes = [n for n in nodes if n["node_type"] == "evidence"]
        method_nodes = [n for n in nodes if n["node_type"] == "method"]
        assert len(ev_nodes) >= 1
        assert len(method_nodes) >= 1

    def test_figure_nodes(self):
        nb = NodeBuilder()
        data = {
            "paper_id": "p1", "paper_meta": {"title": "T"},
            "figures": [{"figure_id": "f1", "figure_label": "Figure 1", "caption": "Western blot results.", "confidence": 0.8}],
        }
        nodes = nb.build_all(data)
        fig_nodes = [n for n in nodes if n["node_type"] == "figure"]
        assert len(fig_nodes) == 1
        assert "Western blot" in fig_nodes[0]["text"]

    def test_table_nodes(self):
        nb = NodeBuilder()
        data = {
            "paper_id": "p1", "paper_meta": {"title": "T"},
            "tables": [{"table_id": "t1", "table_label": "Table S1", "caption": "DEG list.", "n_rows": 500}],
        }
        nodes = nb.build_all(data)
        tbl_nodes = [n for n in nodes if n["node_type"] == "table"]
        assert len(tbl_nodes) == 1

    def test_gap_hypothesis_nodes(self):
        nb = NodeBuilder()
        data = {
            "paper_id": "p1", "paper_meta": {"title": "T"},
            "gaps": {"gaps": [{"gap": "Mechanism is unclear.", "confidence": 0.7}]},
            "hypotheses": {"hypotheses": [{"hypothesis": "Protein X mediates the effect.", "confidence": 0.6}]},
        }
        nodes = nb.build_all(data)
        assert any(n["node_type"] == "gap" for n in nodes)
        assert any(n["node_type"] == "hypothesis" for n in nodes)

    def test_missing_data_no_crash(self):
        nb = NodeBuilder()
        nodes = nb.build_all({"paper_id": "p1", "paper_meta": {}})
        assert len(nodes) >= 1  # At least paper node
