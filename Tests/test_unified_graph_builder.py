"""Tests for Graph Builder orchestrator."""

import json
import tempfile
from pathlib import Path

import pytest
from scientra.knowledge.unified_graph.graph_builder import GraphBuilder, V3_OUTPUT


class TestGraphBuilder:
    def test_build_empty_registry(self):
        """Build with no data should still not crash."""
        builder = GraphBuilder()
        result = builder.build(force=True)
        # Should either succeed or fail gracefully
        assert "error" in result or "success" in result
        # No DB_v2 paths
        assert "DB/DB_v2" not in V3_OUTPUT

    def test_v3_paths(self):
        assert V3_OUTPUT.startswith("05_Knowledge")
        assert "DB/DB_v2" not in V3_OUTPUT

    def test_write_json(self, tmp_path):
        data = {"test": True}
        GraphBuilder._wj(tmp_path / "sub" / "file.json", data)
        assert (tmp_path / "sub" / "file.json").exists()
        loaded = json.loads((tmp_path / "sub" / "file.json").read_text(encoding="utf-8"))
        assert loaded["test"] is True

    def test_no_db_v2(self):
        """Confirm no DB/DB_v2 references anywhere in output paths."""
        builder = GraphBuilder()
        out = builder.root / V3_OUTPUT
        path_str = str(out)
        assert "DB/DB_v2" not in path_str
