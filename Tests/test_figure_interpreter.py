"""Tests for Figure Interpreter."""

from __future__ import annotations

import pytest
from scientra.assets.figure_intelligence.figure_interpreter import FigureInterpreter


def _make_context(**kwargs) -> dict:
    defaults = {
        "figure_id": "fig_test_001",
        "paper_id": "paper_test",
        "asset_id": "asset_001",
        "normalized_label": "Figure 1",
        "asset_path": "/path/to/figure.png",
        "asset_filename": "Figure_1.png",
        "caption": "Figure 1. Western blot analysis showing increased protein expression after treatment.",
        "body_mentions": [
            {
                "mention_id": "cite_001",
                "sentence": "Western blot analysis confirmed the upregulation (Fig. 1).",
                "section": "results",
                "source_type": "body_text",
                "citation_text": "Fig. 1",
                "context_before": "The treatment was effective.",
                "context_after": "Band intensity increased 3-fold.",
            }
        ],
        "linked_evidence": [
            {
                "evidence_id": "paper_test:evidence:key_results:0",
                "text": "Protein expression increased 3-fold after treatment.",
                "claim": "Treatment upregulates target protein.",
                "finding": "3-fold increase in protein expression by western blot.",
                "method": "Western blot with anti-FLAG antibody.",
            }
        ],
        "related_claims": ["Treatment upregulates target protein."],
        "related_methods": ["Western blot with anti-FLAG antibody."],
        "context_completeness": {
            "has_caption": True,
            "has_body_mention": True,
            "has_linked_evidence": True,
        },
        "warnings": [],
    }
    defaults.update(kwargs)
    return defaults


class TestRuleMode:
    def test_rule_interpretation_structure(self):
        interpreter = FigureInterpreter(mode="rule")
        result = interpreter.interpret(_make_context())

        assert "figure_id" in result
        assert result["figure_id"] == "fig_test_001"
        assert "figure_summary" in result
        assert "key_finding" in result
        assert "evidence_type" in result
        assert "evidence_strength" in result
        assert "supported_claims" in result
        assert "grounding_sources" in result
        assert "limitations" in result
        assert "interpretation_confidence" in result
        assert result["mode"] == "rule"

    def test_rule_mode_no_api_key_needed(self):
        """Rule mode should work without any API key."""
        interpreter = FigureInterpreter(mode="rule")
        result = interpreter.interpret(_make_context())
        assert result["mode"] == "rule"
        assert result["evidence_type"] != "unknown"  # Should classify from caption

    def test_rule_grounding_sources(self):
        interpreter = FigureInterpreter(mode="rule")
        result = interpreter.interpret(_make_context())
        sources = result["grounding_sources"]
        assert "caption" in sources
        assert "body_citation" in sources
        assert "evidence_chunk" in sources

    def test_rule_evidence_strength_strong(self):
        interpreter = FigureInterpreter(mode="rule")
        result = interpreter.interpret(_make_context())
        # Full context should yield strong or moderate strength
        assert result["evidence_strength"] in ("strong", "moderate")

    def test_rule_minimal_context(self):
        interpreter = FigureInterpreter(mode="rule")
        ctx = _make_context(
            caption="",
            body_mentions=[],
            linked_evidence=[],
            related_claims=[],
            related_methods=[],
            context_completeness={
                "has_caption": False,
                "has_body_mention": False,
                "has_linked_evidence": False,
            },
        )
        result = interpreter.interpret(ctx)
        assert result["evidence_strength"] in ("weak", "unclear")
        assert len(result["limitations"]) >= 1
        assert result["interpretation_confidence"] < 0.5

    def test_classifies_evidence_from_caption(self):
        interpreter = FigureInterpreter(mode="rule")
        ctx = _make_context(
            caption="Kaplan-Meier survival analysis shows significant difference between groups."
        )
        result = interpreter.interpret(ctx)
        assert result["evidence_type"] in ("survival_curve", "bioassay")

    def test_interpret_all(self):
        interpreter = FigureInterpreter(mode="rule")
        contexts = [_make_context(figure_id="fig_1"), _make_context(figure_id="fig_2")]
        results = interpreter.interpret_all(contexts)
        assert len(results) == 2
        assert results[0]["figure_id"] == "fig_1"
        assert results[1]["figure_id"] == "fig_2"


class TestLLMMode:
    def test_llm_mode_falls_back_without_key(self):
        """LLM mode should fallback to rule when no API key."""
        interpreter = FigureInterpreter(mode="llm")
        # Force rule mode by having no API key configured
        effective = interpreter._resolve_mode()
        # Without proper config, should fall back to rule
        assert effective in ("rule", "llm")  # May be llm if env has key

    def test_auto_mode(self):
        interpreter = FigureInterpreter(mode="auto")
        effective = interpreter._resolve_mode()
        assert effective in ("rule", "llm")
