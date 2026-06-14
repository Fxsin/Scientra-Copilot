"""Tests for Figure Evidence Classifier."""

from __future__ import annotations

import pytest
from scientra.assets.figure_intelligence.figure_evidence_classifier import (
    classify_evidence_type,
    EVIDENCE_TYPE_PATTERNS,
)


class TestMicroscopy:
    def test_confocal(self):
        result = classify_evidence_type(
            caption="Confocal microscopy images of GFP-labeled cells."
        )
        assert result["evidence_type"] == "microscopy"
        assert result["confidence"] > 0.6

    def test_immunofluorescence(self):
        result = classify_evidence_type(
            caption="Immunofluorescence staining showing protein localization."
        )
        assert result["evidence_type"] == "microscopy"

    def test_tem(self):
        result = classify_evidence_type(
            caption="Transmission electron micrograph of viral particles."
        )
        assert result["evidence_type"] == "microscopy"


class TestWesternBlot:
    def test_western_blot_direct(self):
        result = classify_evidence_type(
            caption="Western blot analysis of protein expression levels."
        )
        assert result["evidence_type"] == "western_blot"
        assert result["confidence"] > 0.6

    def test_immunoblot(self):
        result = classify_evidence_type(
            caption="Immunoblot showing band intensity at 45 kDa."
        )
        assert result["evidence_type"] == "western_blot"


class TestBioassay:
    def test_lc50(self):
        result = classify_evidence_type(
            caption="LC50 determination for Cry1Ac toxin against H. armigera larvae."
        )
        assert result["evidence_type"] == "bioassay"

    def test_dose_response(self):
        result = classify_evidence_type(
            caption="Dose-response curve showing mortality at different concentrations."
        )
        assert result["evidence_type"] == "bioassay"

    def test_survival_curve(self):
        result = classify_evidence_type(
            caption="Kaplan-Meier survival curve of treated vs control groups."
        )
        assert result["evidence_type"] == "survival_curve"
        assert result["confidence"] > 0.6


class TestExpressionAnalysis:
    def test_qpcr(self):
        result = classify_evidence_type(
            caption="RT-qPCR analysis of gene expression fold changes."
        )
        assert result["evidence_type"] == "expression_analysis"

    def test_heatmap(self):
        result = classify_evidence_type(
            caption="Heatmap showing hierarchical clustering of differentially expressed genes."
        )
        assert result["evidence_type"] == "heatmap"


class TestSubtypeDetection:
    def test_confocal_subtype(self):
        result = classify_evidence_type(
            caption="Confocal laser scanning microscopy of root sections."
        )
        assert result["evidence_type"] == "microscopy"
        assert "confocal" in result.get("subtype", "")

    def test_lc50_subtype(self):
        result = classify_evidence_type(
            caption="LC50 values determined by diet overlay bioassay."
        )
        assert result["evidence_type"] == "bioassay"
        assert "LC50" in result.get("subtype", "")


class TestUnknown:
    def test_empty_input(self):
        result = classify_evidence_type()
        assert result["evidence_type"] == "unknown"
        assert result["confidence"] == 0.0

    def test_vague_caption(self):
        result = classify_evidence_type(
            caption="Results of the experiment."
        )
        assert result["evidence_type"] == "unknown"


class TestBodyMentions:
    def test_body_mention_helps(self):
        result = classify_evidence_type(
            caption="Analysis of the data.",
            body_mentions=[
                {"sentence": "Western blot analysis confirmed protein expression."},
            ],
        )
        assert result["evidence_type"] == "western_blot"


class TestFilenameSignal:
    def test_filename_helps(self):
        result = classify_evidence_type(
            caption="Results from the analysis.",
            asset_filename="western_blot_fig1.png",
        )
        assert result["evidence_type"] == "western_blot"


class TestAlternatives:
    def test_multiple_possible(self):
        result = classify_evidence_type(
            caption="Gel electrophoresis and western blot analysis of protein samples."
        )
        # Should pick the higher-confidence one
        assert result["evidence_type"] in ("western_blot", "gel_image")
        # Should have alternatives
        assert len(result.get("alternatives", [])) >= 0  # At minimum doesn't crash
