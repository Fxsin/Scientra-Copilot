"""Tests for Graph Input Loader."""

import tempfile
from pathlib import Path

import pytest
from scientra.knowledge.unified_graph.graph_input_loader import GraphInputLoader


class TestInputLoader:
    def test_empty_registry(self):
        loader = GraphInputLoader()
        data = loader.load_all()
        assert "paper_registry" in data

    def test_load_paper(self):
        loader = GraphInputLoader()
        data = loader.load_paper("nonexistent_paper")
        assert data["paper_id"] == "nonexistent_paper"
        # Should not crash on missing files
        assert isinstance(data["evidence"], dict)
        assert isinstance(data["figures"], list)

    def test_load_json_missing(self):
        loader = GraphInputLoader()
        result = loader._load_json("nonexistent/path/file.json")
        assert result is None

    def test_no_crash_on_missing_dirs(self):
        loader = GraphInputLoader()
        data = loader.load_paper("paper_xxx_nonexistent")
        for key in ["evidence", "gaps", "hypotheses", "figures", "tables"]:
            assert key in data  # Should have keys even if empty
