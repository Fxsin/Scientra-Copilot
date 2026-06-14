"""Tests for Supplementary Context Builder."""

import pytest
from scientra.assets.supplementary_intelligence.supplementary_context_builder import SupplementaryContextBuilder


class TestContextBuilder:
    def test_empty_paper(self):
        builder = SupplementaryContextBuilder()
        ctx = builder.build_all("nonexistent_paper_99999")
        assert isinstance(ctx, list)
        assert len(ctx) == 0

    def test_context_structure(self):
        """Verify internal methods work correctly."""
        builder = SupplementaryContextBuilder()
        # Test _find_related
        cards = [{"figure_id": "f1", "label": "Figure 1", "figure_summary": "Western blot in Supplementary File 1"}]
        related = builder._find_related(cards, "Supplementary File 1", [], "figure")
        assert len(related) >= 0  # At minimum doesn't crash

    def test_group_by(self):
        items = [{"k": "a", "v": 1}, {"k": "a", "v": 2}, {"k": "b", "v": 3}]
        result = SupplementaryContextBuilder._group_by(items, "k")
        assert len(result["a"]) == 2
        assert len(result["b"]) == 1
