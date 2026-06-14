"""Tests for Asset Graph Builder."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from scientra.assets.linking.asset_graph_builder import AssetGraphBuilder


class TestAssetGraphBuilder:
    def test_build_no_registry(self):
        """Building for a paper with no registry should return error."""
        builder = AssetGraphBuilder()
        result = builder.build("nonexistent_paper_99999")
        assert result["success"] is False
        assert "error" in result

    def test_get_asset_links_no_data(self):
        """Getting asset links for paper with no data."""
        builder = AssetGraphBuilder()
        result = builder.get_asset_links("nonexistent_paper_99999")
        assert result["available"] is False
        assert result["citation_mentions"] == []

    def test_get_unmatched_assets_no_data(self):
        """Getting unmatched assets for paper with no data."""
        builder = AssetGraphBuilder()
        result = builder.get_unmatched_assets("nonexistent_paper_99999")
        assert result["available"] is False

    def test_summary_structure(self):
        """Summary dict has required keys."""
        builder = AssetGraphBuilder()
        result = builder.build("nonexistent_paper_99999")
        required_keys = [
            "paper_id", "success", "citation_count", "link_count",
            "evidence_link_count", "unmatched_asset_count",
            "unmatched_mention_count", "low_confidence_count",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_error_result_keys(self):
        """Error result includes all required keys."""
        builder = AssetGraphBuilder()
        result = builder.build("nonexistent_paper_99999")
        assert "error" in result
        assert result["citation_count"] == 0
        assert result["link_count"] == 0

    def test_count_methods(self):
        """_count_methods correctly aggregates match methods."""
        links = [
            {"match_method": "filename"},
            {"match_method": "filename"},
            {"match_method": "notes"},
            {"match_method": "fuzzy"},
        ]
        counts = AssetGraphBuilder._count_methods(links)
        assert counts == {"filename": 2, "notes": 1, "fuzzy": 1}

    def test_count_relations(self):
        """_count_relations correctly aggregates relation types."""
        ev_links = [
            {"relation": "supports"},
            {"relation": "illustrates"},
            {"relation": "supports"},
        ]
        counts = AssetGraphBuilder._count_relations(ev_links)
        assert counts == {"supports": 2, "illustrates": 1}

    def test_write_json(self, tmp_path):
        """_write_json writes valid JSON."""
        data = [{"key": "value", "number": 42}]
        path = tmp_path / "test.json"
        AssetGraphBuilder._write_json(path, data)
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == data

    def test_write_summary_md(self, tmp_path):
        """_write_summary_md writes a valid markdown file."""
        summary = {
            "paper_id": "paper_test",
            "generated_at": "2026-06-14T00:00:00Z",
            "citation_count": 10,
            "link_count": 8,
            "evidence_link_count": 5,
            "unmatched_asset_count": 2,
            "unmatched_mention_count": 2,
            "low_confidence_count": 1,
            "match_methods": {"filename": 6, "notes": 2},
            "relation_types": {"supports": 3, "illustrates": 2},
        }
        mentions = [
            {
                "mention_id": "cite_01",
                "citation_text": "Fig. 1",
                "normalized_label": "Figure 1",
                "asset_type": "figure",
                "source_type": "body_text",
                "section": "results",
                "sentence": "See Fig. 1.",
            }
        ]
        links = [
            {
                "link_id": "link_01",
                "paper_id": "paper_test",
                "asset_id": "asset_01",
                "normalized_label": "Figure 1",
                "match_method": "filename",
                "confidence": 0.95,
                "linked_evidence_ids": [],
            }
        ]
        evidence_links = [
            {
                "evidence_id": "paper_test:evidence:key_results:0",
                "asset_id": "asset_01",
                "relation": "illustrates",
                "confidence": 0.95,
                "citation_text": "Figure 1",
            }
        ]
        unmatched_assets: list = []
        unmatched_mentions: list = []
        low_confidence: list = []

        path = tmp_path / "asset_graph_summary.md"
        AssetGraphBuilder._write_summary_md(
            path, summary, mentions, links, evidence_links,
            unmatched_assets, unmatched_mentions, low_confidence,
        )

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "paper_test" in content
        assert "Statistics" in content
        assert "10" in content
        assert "Linked Assets" in content
        assert "Figure 1" in content
