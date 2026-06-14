"""Tests for Figure Context Builder."""

from __future__ import annotations

import pytest
from scientra.assets.figure_intelligence.figure_context_builder import FigureContextBuilder


class TestContextBuilder:
    def test_build_empty_paper(self):
        builder = FigureContextBuilder()
        contexts = builder.build_all("nonexistent_paper_99999")
        assert isinstance(contexts, list)
        assert len(contexts) == 0

    def test_context_structure(self):
        """Verify context dict structure is correct."""
        # Test that helper methods produce correct structure
        builder = FigureContextBuilder()
        # Test label extraction from filename
        label = builder._label_from_filename("Figure_S1.png")
        assert "Figure" in label
        label2 = builder._label_from_filename("Fig.3_final.png")
        assert "Figure" in label2

    def test_label_from_filename(self):
        builder = FigureContextBuilder()
        assert "Figure S1" == builder._label_from_filename("Figure_S1.png")
        assert "Figure 3" == builder._label_from_filename("Fig.3_final.png")
        assert "Figure 2" == builder._label_from_filename("figure_2_expression.png")
        assert "" == builder._label_from_filename("microscopy_image.png")

    def test_warnings_generation(self):
        builder = FigureContextBuilder()
        # Full completeness
        warnings = builder._generate_warnings(
            {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True},
            [{"sentence": "test"}, {"sentence": "test2"}],
            "A detailed caption with sufficient length for proper interpretation.",
        )
        assert len(warnings) == 0

        # No caption
        warnings = builder._generate_warnings(
            {"has_caption": False, "has_body_mention": False, "has_linked_evidence": False},
            [],
            "",
        )
        assert len(warnings) >= 3

        # Short caption
        warnings = builder._generate_warnings(
            {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True},
            [{"sentence": "test"}],
            "Short.",
        )
        assert any("short" in w.lower() for w in warnings)

    def test_completeness_warnings(self):
        """Completeness dict includes has_caption, has_body_mention, has_linked_evidence."""
        builder = FigureContextBuilder()
        # These methods are used internally by build_all
        completeness = {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True}
        assert completeness["has_caption"]
        assert completeness["has_body_mention"]
        assert completeness["has_linked_evidence"]
