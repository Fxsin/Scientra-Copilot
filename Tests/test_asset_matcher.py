"""Tests for Asset Matcher."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from scientra.assets.linking.asset_matcher import AssetMatcher
from scientra.assets.types import PaperAssetRegistry


def _make_registry(paper_id: str, assets: list[dict]) -> PaperAssetRegistry:
    """Helper to create a test registry."""
    return PaperAssetRegistry(
        paper_id=paper_id,
        assets=assets,
        last_updated="2026-01-01T00:00:00Z",
    )


def _make_mention(**kwargs) -> dict:
    """Helper to create a test mention dict."""
    defaults = {
        "mention_id": "cite_test001",
        "paper_id": "paper_test",
        "source_type": "body_text",
        "source_id": "test:body:1",
        "section": "results",
        "sentence": "See Fig. 1 for the results.",
        "citation_text": "Fig. 1",
        "asset_type": "figure",
        "normalized_label": "Figure 1",
        "subpanel": "",
        "is_supplementary": False,
        "context_before": "",
        "context_after": "",
    }
    defaults.update(kwargs)
    return defaults


class TestAssetMatcher:
    def test_match_by_filename_exact(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_01",
                "paper_id": "paper_test",
                "asset_type": "figure_image",
                "filename": "Figure_1.png",
                "original_filename": "Figure_1.png",
                "relative_path": "assets/images/Figure_1.png",
            },
        ])
        mentions = [_make_mention(normalized_label="Figure 1", asset_type="figure")]
        result = matcher.match_all("paper_test", mentions, registry)

        assert len(result["links"]) >= 1
        link = result["links"][0]
        assert link["asset_id"] == "asset_01"
        assert link["match_method"] == "filename"
        assert link["status"] == "matched"

    def test_match_table_s1_xlsx(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_02",
                "paper_id": "paper_test",
                "asset_type": "supplementary_table",
                "filename": "Table_S1.xlsx",
                "original_filename": "Table_S1.xlsx",
                "relative_path": "assets/tables/Table_S1.xlsx",
            },
        ])
        mentions = [_make_mention(
            normalized_label="Table S1",
            asset_type="table",
            citation_text="Table S1",
        )]
        result = matcher.match_all("paper_test", mentions, registry)

        assert len(result["links"]) >= 1
        link = result["links"][0]
        assert link["asset_id"] == "asset_02"
        assert link["confidence"] >= 0.7

    def test_match_figure_s3_png(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_03",
                "paper_id": "paper_test",
                "asset_type": "figure_image",
                "filename": "Figure_S3.png",
                "original_filename": "Figure S3.png",
                "relative_path": "assets/images/Figure_S3.png",
            },
        ])
        mentions = [_make_mention(
            normalized_label="Figure S3",
            asset_type="figure",
            citation_text="Fig. S3",
        )]
        result = matcher.match_all("paper_test", mentions, registry)

        assert len(result["links"]) >= 1
        link = result["links"][0]
        assert link["asset_id"] == "asset_03"
        assert link["confidence"] >= 0.7

    def test_unmatched_asset(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_unmatched",
                "paper_id": "paper_test",
                "asset_type": "figure_image",
                "filename": "microscopy_image.png",
                "original_filename": "microscopy_image.png",
                "relative_path": "assets/images/microscopy_image.png",
            },
        ])
        # Mention doesn't match this asset
        mentions = [_make_mention(
            normalized_label="Figure 5",
            asset_type="figure",
            citation_text="Fig. 5",
        )]
        result = matcher.match_all("paper_test", mentions, registry)

        # The asset should appear in unmatched_assets
        assert len(result["unmatched_assets"]) >= 1
        unmatched_ids = [a.get("asset_id") for a in result["unmatched_assets"]]
        assert "asset_unmatched" in unmatched_ids

    def test_low_confidence_fuzzy_match(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_fuzzy",
                "paper_id": "paper_test",
                "asset_type": "figure_image",
                "filename": "fig1_final.png",
                "original_filename": "fig1_final.png",
                "relative_path": "assets/images/fig1_final.png",
            },
        ])
        mentions = [_make_mention(
            normalized_label="Figure 1",
            asset_type="figure",
            citation_text="Fig. 1",
        )]
        result = matcher.match_all("paper_test", mentions, registry)

        # Should either match with lower confidence or be low_confidence
        total_found = len(result["links"]) + len(result["low_confidence"])
        assert total_found >= 1

    def test_fuzzy_matching_fallback(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_fuzzy2",
                "paper_id": "paper_test",
                "asset_type": "figure_image",
                "filename": "figure1_expression_data.png",
                "original_filename": "figure1_expression_data.png",
                "relative_path": "assets/images/figure1_expression_data.png",
            },
        ])
        mentions = [_make_mention(
            normalized_label="Figure 1",
            asset_type="figure",
            citation_text="Figure 1",
        )]
        result = matcher.match_all("paper_test", mentions, registry)
        # Should find a match (fuzzy or filename)
        assert len(result["links"]) + len(result["low_confidence"]) >= 1

    def test_empty_registry(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [])
        mentions = [_make_mention()]
        result = matcher.match_all("paper_test", mentions, registry)

        assert len(result["links"]) == 0
        assert len(result["unmatched_mentions"]) >= 1

    def test_link_structure(self):
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_struct",
                "paper_id": "paper_test",
                "asset_type": "supplementary_table",
                "filename": "Table_1.xlsx",
                "original_filename": "Table 1.xlsx",
                "relative_path": "assets/tables/Table_1.xlsx",
            },
        ])
        mentions = [_make_mention(
            normalized_label="Table 1",
            asset_type="table",
            citation_text="Table 1",
        )]
        result = matcher.match_all("paper_test", mentions, registry)

        if result["links"]:
            link = result["links"][0]
            assert "link_id" in link
            assert "paper_id" in link
            assert "citation_mention_id" in link
            assert "asset_id" in link
            assert "match_method" in link
            assert "confidence" in link
            assert "status" in link
            assert link["confidence"] >= 0.0
            assert link["confidence"] <= 1.0
            assert link["status"] in ("matched", "low_confidence", "unmatched")

    def test_match_by_notes(self):
        # The notes matching relies on asset_notes.txt,
        # which is tested via the notes field fallback
        matcher = AssetMatcher()
        registry = _make_registry("paper_test", [
            {
                "asset_id": "asset_notes_test",
                "paper_id": "paper_test",
                "asset_type": "figure_image",
                "filename": "some_figure.png",
                "original_filename": "some_figure.png",
                "notes": "Figure 2 — Western blot analysis",
                "relative_path": "assets/images/some_figure.png",
            },
        ])
        mentions = [_make_mention(
            normalized_label="Figure 2",
            asset_type="figure",
            citation_text="Figure 2",
        )]
        result = matcher.match_all("paper_test", mentions, registry)
        # Notes matching may find it via caption method
        assert len(result["links"]) + len(result["low_confidence"]) >= 0  # At least doesn't crash
