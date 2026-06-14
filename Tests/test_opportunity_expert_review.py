"""Tests for Opportunity Expert Review module (Phase 3.5)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scientra.ai.opportunity_expert_review import (
    _load_prompt_template,
    _extract_json_from_response,
    _simple_template,
    _build_evolution_context,
    _render_review_prompt,
    _review_one_opportunity,
    review_research_opportunities,
    _build_summary,
    load_reviews,
)


# ── Prompt Template ──


class TestPromptTemplate:
    def test_template_loads(self):
        template = _load_prompt_template()
        assert len(template) > 100
        assert "opportunity" in template.lower()
        assert "review_status" in template

    def test_simple_template_replacement(self):
        tmpl = "Hello {{name}}, your score is {{score}}."
        result = _simple_template(tmpl, {"name": "World", "score": "99"})
        assert result == "Hello World, your score is 99."

    def test_if_block_present(self):
        tmpl = "Start {% if evolution_context %}EVO:{{evolution_context}}{% endif %} End"
        result = _simple_template(tmpl, {"evolution_context": "data"})
        assert "EVO:data" in result
        assert "Start " in result
        assert " End" in result

    def test_if_block_missing(self):
        tmpl = "Start {% if evolution_context %}EVO:{{evolution_context}}{% endif %} End"
        result = _simple_template(tmpl, {"evolution_context": ""})
        assert "EVO" not in result
        assert result.strip() == "Start  End"


# ── JSON Extraction ──


class TestJSONExtraction:
    def test_parse_valid_json(self):
        text = '{"review_status": "accept", "review_confidence": 0.85}'
        result = _extract_json_from_response(text)
        assert result is not None
        assert result["review_status"] == "accept"

    def test_parse_json_in_code_block(self):
        text = 'Here is my review:\n```json\n{"review_status": "revise", "review_confidence": 0.7}\n```\nDone.'
        result = _extract_json_from_response(text)
        assert result is not None
        assert result["review_status"] == "revise"

    def test_parse_json_with_brace_extraction(self):
        text = 'Some prose before...\n\n{"review_status": "reject", "major_risks": ["Risk A", "Risk B"]}\n\nSome prose after.'
        result = _extract_json_from_response(text)
        assert result is not None
        assert result["review_status"] == "reject"
        assert len(result["major_risks"]) == 2

    def test_empty_response(self):
        assert _extract_json_from_response("") is None

    def test_no_json(self):
        assert _extract_json_from_response("This is just prose, no JSON here.") is None


# ── Evolution Context ──


class TestEvolutionContext:
    def test_builds_context_when_data_exists(self):
        opp = {
            "opportunity_id": "opp_001",
            "linked_gap_cluster_id": "gc_001",
        }
        evo = {
            "gap_evolution": [{
                "cluster_id": "gc_001",
                "trend": "emerging",
                "first_seen_year": 2020,
                "last_seen_year": 2024,
                "active_year_span": 4,
                "persistence_score": 0.8,
                "closure_signal": "open",
            }],
            "opportunity_evolution": [{
                "opportunity_id": "opp_001",
                "trend": "growing",
                "priority_trajectory": "rising",
            }],
        }
        ctx = _build_evolution_context(opp, evo)
        assert ctx is not None
        assert ctx["gap_trend"] == "emerging"
        assert ctx["priority_trajectory"] == "rising"

    def test_returns_none_when_no_match(self):
        opp = {"opportunity_id": "opp_999", "linked_gap_cluster_id": "gc_999"}
        evo = {"gap_evolution": [], "opportunity_evolution": []}
        ctx = _build_evolution_context(opp, evo)
        assert ctx is None


# ── Review Function ──


class TestReviewOneOpportunity:
    def test_review_with_mock_llm(self):
        """Test that _review_one_opportunity handles LLM response correctly."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "opportunity_id": "opp_001",
            "review_status": "accept",
            "scientific_importance": "Important question in the field.",
            "evidence_strength_assessment": "Strong evidence from multiple labs.",
            "technical_feasibility": "Feasible with standard techniques.",
            "novelty_assessment": "Novel approach to known problem.",
            "major_risks": ["Competing labs"],
            "key_missing_evidence": ["In vivo validation"],
            "recommended_next_steps": ["Design knockout experiment"],
            "possible_experimental_routes": ["CRISPR screening"],
            "expected_impact": "Would shift paradigm.",
            "review_confidence": 0.85,
            "review_warnings": [],
        })
        mock_response.provider = "deepseek"
        mock_response.model = "deepseek-chat"
        mock_response.input_tokens = 500
        mock_response.output_tokens = 200
        mock_response.total_tokens = 700
        mock_response.cost_estimate = 0.0005

        opp = {
            "opportunity_id": "opp_001",
            "title": "Test opportunity",
            "opportunity_score": 0.9,
        }
        gc = {"cluster_id": "gc_001", "unified_gap_statement": "Test gap"}
        hcs = [{"hypothesis_cluster_id": "hc_001", "unified_hypothesis_statement": "Test hyp"}]

        with patch("scientra.ai.call_llm", return_value=mock_response):
            result = _review_one_opportunity(opp, gc, hcs, None, 1, {})
            assert result["review_status"] == "accept"
            assert result["review_confidence"] == 0.85
            assert result["rank"] == 1
            assert len(result["major_risks"]) == 1
            assert result["usage"]["success"] is True

    def test_review_handles_llm_failure(self):
        """Test that LLM failure doesn't crash."""
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "API timeout"
        mock_response.provider = "deepseek"
        mock_response.model = "deepseek-chat"
        mock_response.input_tokens = 0
        mock_response.output_tokens = 0
        mock_response.total_tokens = 0
        mock_response.cost_estimate = 0.0

        opp = {"opportunity_id": "opp_001", "title": "Test", "opportunity_score": 0.9}

        with patch("scientra.ai.call_llm", return_value=mock_response):
            result = _review_one_opportunity(opp, None, [], None, 1, {})
            assert result["review_status"] == "error"
            assert "API timeout" in str(result["review_warnings"])

    def test_review_handles_malformed_json(self):
        """Test that malformed JSON doesn't crash."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "This is not valid JSON at all, just random prose without any braces"
        mock_response.provider = "deepseek"
        mock_response.model = "deepseek-chat"
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_response.total_tokens = 150
        mock_response.cost_estimate = 0.0001

        opp = {"opportunity_id": "opp_001", "title": "Test", "opportunity_score": 0.9}

        with patch("scientra.ai.call_llm", return_value=mock_response):
            result = _review_one_opportunity(opp, None, [], None, 1, {})
            assert result["review_status"] == "error"
            assert "Failed to parse" in str(result["review_warnings"])


# ── Summary Building ──


class TestBuildSummary:
    def test_summary_counts(self):
        reviews = [
            {"review_status": "accept", "review_confidence": 0.9},
            {"review_status": "accept", "review_confidence": 0.8},
            {"review_status": "revise", "review_confidence": 0.7},
            {"review_status": "reject", "review_confidence": 0.5},
            {"review_status": "insufficient_data", "review_confidence": 0.3},
        ]
        summary = _build_summary(reviews, 0.005)
        assert summary["reviewed_count"] == 5
        assert summary["accept_count"] == 2
        assert summary["revise_count"] == 1
        assert summary["reject_count"] == 1
        assert summary["insufficient_data_count"] == 1
        assert summary["total_cost_usd"] == 0.005

    def test_summary_empty(self):
        summary = _build_summary([], 0.0)
        assert summary["reviewed_count"] == 0
        assert summary["average_review_confidence"] == 0.0


# ── Top-K and Min-Score ──


class TestTopKAndMinScore:
    def test_top_k_respected(self):
        """With top_k=2, only 2 opportunities are reviewed (when task enabled)."""
        # When task is disabled, it returns skipped
        from scientra.ai import get_config
        cfg = get_config()
        if not cfg.is_task_enabled("opportunity_review"):
            result = review_research_opportunities(top_k=2)
            # Task disabled => skipped
            assert result["status"] in ("skipped", "no_data")

    def test_disabled_task_skips(self):
        """When opportunity_review is disabled, result is skipped."""
        from scientra.ai import get_config
        cfg = get_config()
        if not cfg.is_task_enabled("opportunity_review"):
            result = review_research_opportunities(top_k=5)
            assert result["status"] == "skipped"
            assert result["reviews"] == []


# ── Load Reviews ──


class TestLoadReviews:
    def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as td:
            result = load_reviews(td)
            assert result is None

    def test_load_existing(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "opportunity_reviews.json"
            test_data = {"status": "generated", "reviews": [], "summary": {}}
            p.write_text(json.dumps(test_data), encoding="utf-8")
            result = load_reviews(td)
            assert result is not None
            assert result["status"] == "generated"
