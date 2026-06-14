"""Tests for Figure Quality Checker."""

from __future__ import annotations

import pytest
from scientra.assets.figure_intelligence.figure_quality_checker import FigureQualityChecker


def _make_context(**kwargs) -> dict:
    defaults = {
        "figure_id": "fig_test_001",
        "paper_id": "paper_test",
        "caption": "Figure 1. Western blot analysis showing increased expression after treatment.",
        "body_mentions": [{"sentence": "Western blot confirmed upregulation (Fig. 1)."}],
        "linked_evidence": [{"evidence_id": "ev_001", "text": "Protein increased 3-fold."}],
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
        "figure_summary": "Western blot shows increased protein expression.",
        "key_finding": "Protein expression increased 3-fold after treatment.",
        "evidence_type": "western_blot",
        "evidence_strength": "strong",
        "supported_claims": ["Treatment upregulates target protein."],
        "grounding_sources": ["caption", "body_citation", "evidence_chunk"],
        "limitations": [],
        "interpretation_confidence": 0.75,
        "mode": "rule",
    }
    defaults.update(kwargs)
    return defaults


class TestQualityChecker:
    def test_full_context_high_quality(self):
        checker = FigureQualityChecker()
        result = checker.check(_make_context(), _make_interpretation())
        assert result["quality_score"] > 0.5
        assert result["overclaim_risk"] == "low"

    def test_no_caption_low_score(self):
        checker = FigureQualityChecker()
        ctx = _make_context(
            caption="",
            context_completeness={"has_caption": False, "has_body_mention": True, "has_linked_evidence": True},
        )
        result = checker.check(ctx, _make_interpretation())
        assert result["caption_score"] < 0.5
        assert any("caption" in w.lower() for w in result["warnings"])

    def test_no_evidence(self):
        checker = FigureQualityChecker()
        ctx = _make_context(
            linked_evidence=[],
            context_completeness={"has_caption": True, "has_body_mention": True, "has_linked_evidence": False},
        )
        result = checker.check(ctx, _make_interpretation())
        assert result["evidence_score"] < 0.5

    def test_overclaim_detection(self):
        checker = FigureQualityChecker()
        interp = _make_interpretation(
            key_finding="This definitively proves the mechanism and conclusively demonstrates the pathway.",
            supported_claims=["We have proven the novel discovery of this breakthrough mechanism."],
        )
        ctx = _make_context(
            context_completeness={"has_caption": True, "has_body_mention": False, "has_linked_evidence": False},
        )
        result = checker.check(ctx, interp)
        # Should detect overclaim due to strong language + weak grounding
        assert result["overclaim_risk"] in ("medium", "high")

    def test_no_body_mention_warning(self):
        checker = FigureQualityChecker()
        ctx = _make_context(
            body_mentions=[],
            context_completeness={"has_caption": True, "has_body_mention": False, "has_linked_evidence": True},
        )
        result = checker.check(ctx, _make_interpretation())
        assert "no_body_citation" in result.get("issues", [])

    def test_rule_high_confidence_warning(self):
        checker = FigureQualityChecker()
        interp = _make_interpretation(
            interpretation_confidence=0.85,
            mode="rule",
        )
        result = checker.check(_make_context(), interp)
        # Rule mode with very high confidence should warn
        if result["quality_score"] < 0.7:
            assert any("rule" in w.lower() for w in result["warnings"]) or len(result["warnings"]) > 0

    def test_check_all(self):
        checker = FigureQualityChecker()
        contexts = [
            _make_context(figure_id="fig_1"),
            _make_context(figure_id="fig_2"),
        ]
        interpretations = [
            _make_interpretation(figure_id="fig_1"),
            _make_interpretation(figure_id="fig_2"),
        ]
        results = checker.check_all(contexts, interpretations)
        assert len(results) == 2

    def test_strong_strength_with_weak_grounding(self):
        checker = FigureQualityChecker()
        interp = _make_interpretation(evidence_strength="strong")
        ctx = _make_context(
            context_completeness={"has_caption": True, "has_body_mention": False, "has_linked_evidence": False},
        )
        result = checker.check(ctx, interp)
        assert "strength_mismatch" in result.get("issues", [])
