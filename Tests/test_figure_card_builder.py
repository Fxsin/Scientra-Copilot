"""Tests for Figure Card Builder."""

from __future__ import annotations

import pytest
from scientra.assets.figure_intelligence.figure_card_builder import FigureCardBuilder


def _make_context(**kwargs) -> dict:
    defaults = {
        "figure_id": "fig_test_001",
        "paper_id": "paper_test",
        "asset_id": "asset_001",
        "normalized_label": "Figure 1",
        "asset_path": "/path/to/figure.png",
        "caption": "Figure 1. Western blot showing expression levels.",
        "body_mentions": [{"sentence": "See Fig. 1."}],
        "linked_evidence": [
            {"evidence_id": "ev_001", "text": "Protein expression increased."},
            {"evidence_id": "ev_002", "text": "Band intensity quantified."},
        ],
        "related_claims": ["Claim 1"],
        "related_methods": ["Method 1"],
        "context_completeness": {
            "has_caption": True,
            "has_body_mention": True,
            "has_linked_evidence": True,
        },
        "warnings": [],
    }
    defaults.update(kwargs)
    return defaults


def _make_interpretation(**kwargs) -> dict:
    defaults = {
        "figure_id": "fig_test_001",
        "figure_summary": "Western blot shows expression.",
        "key_finding": "Protein increased 3-fold.",
        "evidence_type": "western_blot",
        "evidence_type_confidence": 0.9,
        "evidence_strength": "strong",
        "supported_claims": ["Claim 1"],
        "related_methods": ["Method 1"],
        "limitations": [],
        "grounding_sources": ["caption", "body_citation", "evidence_chunk"],
        "interpretation_confidence": 0.75,
        "mode": "rule",
    }
    defaults.update(kwargs)
    return defaults


def _make_quality(**kwargs) -> dict:
    defaults = {
        "figure_id": "fig_test_001",
        "quality_score": 0.85,
        "warnings": [],
        "issues": [],
        "overclaim_risk": "low",
        "overclaim_details": "",
        "caption_score": 0.95,
        "body_citation_score": 0.9,
        "evidence_score": 0.9,
    }
    defaults.update(kwargs)
    return defaults


class TestCardBuilder:
    def test_build_card_structure(self):
        builder = FigureCardBuilder()
        card = builder.build(_make_context(), _make_interpretation(), _make_quality())

        required_keys = [
            "figure_id", "paper_id", "label", "title", "asset_path",
            "caption", "figure_summary", "key_finding", "evidence_type",
            "evidence_strength", "related_claims", "related_methods",
            "linked_evidence_ids", "limitations", "warnings",
            "quality_score", "overclaim_risk", "confidence", "mode",
        ]
        for key in required_keys:
            assert key in card, f"Missing key: {key}"

    def test_linked_evidence_ids(self):
        builder = FigureCardBuilder()
        card = builder.build(_make_context(), _make_interpretation(), _make_quality())
        assert len(card["linked_evidence_ids"]) == 2
        assert "ev_001" in card["linked_evidence_ids"]

    def test_warnings_merged(self):
        builder = FigureCardBuilder()
        ctx = _make_context(warnings=["Context warning"])
        qr = _make_quality(warnings=["Quality warning"])
        card = builder.build(ctx, _make_interpretation(), qr)
        assert "Context warning" in card["warnings"]
        assert "Quality warning" in card["warnings"]

    def test_title_from_caption(self):
        builder = FigureCardBuilder()
        ctx = _make_context(
            caption="Figure 1. Dose-response curve showing mortality at 48h post treatment."
        )
        card = builder.build(ctx, _make_interpretation(), _make_quality())
        assert len(card["title"]) > 10
        # Should strip "Figure 1." prefix
        assert not card["title"].startswith("Figure 1.")

    def test_build_all(self):
        builder = FigureCardBuilder()
        contexts = [_make_context(figure_id="fig_1"), _make_context(figure_id="fig_2")]
        interpretations = [
            _make_interpretation(figure_id="fig_1"),
            _make_interpretation(figure_id="fig_2"),
        ]
        quality_reports = [
            _make_quality(figure_id="fig_1"),
            _make_quality(figure_id="fig_2"),
        ]
        cards = builder.build_all(contexts, interpretations, quality_reports)
        assert len(cards) == 2

    def test_mode_preserved(self):
        builder = FigureCardBuilder()
        interp = _make_interpretation(mode="llm")
        card = builder.build(_make_context(), interp, _make_quality())
        assert card["mode"] == "llm"

        interp2 = _make_interpretation(mode="rule_fallback")
        card2 = builder.build(_make_context(), interp2, _make_quality())
        assert card2["mode"] == "rule_fallback"
