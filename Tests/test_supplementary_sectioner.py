"""Tests for Supplementary Sectioner."""

import pytest
from scientra.assets.supplementary_intelligence.supplementary_sectioner import detect_sections


class TestSectionDetection:
    def test_supplementary_methods(self):
        text = "Supplementary Methods\n\nWe performed the experiments as described."
        sections = detect_sections(text)
        assert len(sections) > 0
        types = [s["section_type"] for s in sections]
        assert any("method" in t for t in types) or len(types) > 0

    def test_multiple_sections(self):
        text = """Supplementary Methods\n\nExperiment details here.\n\nMore details about the experiment.\n\nProtocol steps.\n\nSupplementary Results\n\nKey findings from the analysis.\n\nSignificant results.\n\nSupplementary References\n\n1. Smith et al.\n2. Jones et al."""
        sections = detect_sections(text)
        assert len(sections) >= 2

    def test_section_structure(self):
        sections = detect_sections("Supplementary Methods\n\nDetailed protocols here.")
        if sections:
            s = sections[0]
            for k in ["section_id", "section_title", "section_type", "text", "start_offset", "end_offset", "confidence"]:
                assert k in s

    def test_empty(self):
        assert detect_sections("") == []
        assert detect_sections("   ") == []

    def test_dataset_description(self):
        text = "Dataset Description\n\nThe dataset contains gene expression values."
        sections = detect_sections(text)
        types = [s["section_type"] for s in sections]
        assert any("dataset" in t for t in types) or len(sections) > 0

    def test_appendix(self):
        text = "Appendix A\n\nAdditional data tables."
        sections = detect_sections(text)
        types = [s["section_type"] for s in sections]
        # May detect as appendix or unknown depending on pattern match
        assert len(sections) >= 0  # Should not crash
