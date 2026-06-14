"""Tests for Summary V2 generation module.

Run:
    python -m pytest Tests/test_summary_v2.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSummaryV2Prompt:
    """Test the Summary V2 prompt rendering."""

    def test_prompt_renders_variables(self):
        """Prompt template substitutes paper data correctly."""
        from scientra.ai.summary_v2 import _render_prompt

        prompt = _render_prompt(
            paper_id="test-001",
            text="This is a test paper about autophagy.",
            metadata={"title": "Test Paper", "authors": "Smith et al.", "year": 2024, "doi": "10.1234/test"},
        )
        assert "Test Paper" in prompt
        assert "Smith et al." in prompt
        assert "2024" in prompt
        assert "10.1234/test" in prompt
        assert "test paper about autophagy" in prompt
        assert "test-001" in prompt

    def test_prompt_includes_evidence_chunks(self):
        """Prompt renders evidence chunks section when chunks provided."""
        from scientra.ai.summary_v2 import _render_prompt

        chunks = [
            {"chunk_id": "C1", "chunk_type": "key_result", "confidence": "medium",
             "text": "Autophagy was observed via TEM."},
            {"chunk_id": "C2", "chunk_type": "claim", "confidence": "high",
             "text": "Vip3Aa induces autophagy in Sf9 cells."},
        ]
        prompt = _render_prompt(
            paper_id="test",
            text="Paper text here.",
            evidence_chunks=chunks,
        )
        assert "C1" in prompt
        assert "TEM" in prompt
        assert "Vip3Aa" in prompt

    def test_prompt_without_evidence_chunks(self):
        """Prompt renders fine without evidence chunks."""
        from scientra.ai.summary_v2 import _render_prompt

        prompt = _render_prompt(
            paper_id="test",
            text="Paper text.",
            evidence_chunks=None,
        )
        # No evidence_chunks section when none provided
        assert "Available Evidence Chunks" not in prompt
        assert "Paper text." in prompt


class TestSummaryV2JSONExtraction:
    """Test JSON extraction from LLM responses."""

    def test_extract_direct_json(self):
        """Direct JSON object is parsed correctly."""
        from scientra.ai.summary_v2 import _extract_json_from_response

        text = '{"paper_id": "test", "title": "Foo", "core_finding": "Bar"}'
        result = _extract_json_from_response(text)
        assert result is not None
        assert result["paper_id"] == "test"
        assert result["core_finding"] == "Bar"

    def test_extract_from_code_block(self):
        """JSON inside markdown code block is extracted."""
        from scientra.ai.summary_v2 import _extract_json_from_response

        text = 'Here is the result:\n```json\n{"paper_id": "test", "title": "Foo"}\n```\nHope this helps.'
        result = _extract_json_from_response(text)
        assert result is not None
        assert result["paper_id"] == "test"

    def test_extract_nested_braces(self):
        """JSON with nested braces is correctly extracted."""
        from scientra.ai.summary_v2 import _extract_json_from_response

        text = 'Prefix {"key_evidence": [{"claim": "X", "evidence": "Y"}]} Suffix'
        result = _extract_json_from_response(text)
        assert result is not None
        assert len(result["key_evidence"]) == 1
        assert result["key_evidence"][0]["claim"] == "X"

    def test_extract_invalid_json_returns_none(self):
        """Invalid JSON returns None."""
        from scientra.ai.summary_v2 import _extract_json_from_response

        text = "This is not JSON at all."
        result = _extract_json_from_response(text)
        assert result is None


class TestSummaryV2Fallback:
    """Test fallback behavior on LLM failure."""

    def test_fallback_returns_minimal_structure(self):
        """Fallback generates minimal valid output."""
        from scientra.ai.summary_v2 import _build_fallback_summary_v2

        result = _build_fallback_summary_v2("test-id", {"title": "Test"})
        assert result["paper_id"] == "test-id"
        assert result["status"] == "fallback"
        assert "fallback" in str(result["warnings"]).lower()
        assert result["confidence"] == 0.0

    @patch("scientra.ai.call_llm")
    def test_generate_summary_v2_llm_failure(self, mock_call):
        """When LLM fails, fallback is returned."""
        from scientra.ai.summary_v2 import generate_summary_v2
        from scientra.ai.schemas import LLMResponse

        mock_call.return_value = LLMResponse.failure("deepseek", "deepseek-chat", "Network error")

        result = generate_summary_v2(
            paper_id="test",
            text="Some paper text.",
            metadata={"title": "Test"},
        )
        assert result["status"] == "fallback"
        assert result["paper_id"] == "test"

    @patch("scientra.ai.call_llm")
    def test_generate_summary_v2_success(self, mock_call):
        """Successful LLM call produces valid output."""
        from scientra.ai.summary_v2 import generate_summary_v2
        from scientra.ai.schemas import LLMResponse

        valid_json = json.dumps({
            "research_question": "What is X?",
            "core_finding": "X causes Y.",
            "method_summary": ["TEM", "Western blot"],
            "key_evidence": [{"claim": "X", "evidence": "Data", "evidence_type": "experimental"}],
            "main_claims": ["Claim 1"],
            "limitations": ["Small sample"],
            "future_directions": ["More studies"],
            "important_entities": [{"name": "GeneX", "type": "gene", "role": "regulator"}],
            "confidence": 0.85,
            "warnings": [],
        })
        mock_call.return_value = LLMResponse(
            success=True, provider="deepseek", model="deepseek-chat",
            text=valid_json, input_tokens=100, output_tokens=200, total_tokens=300,
            cost_estimate=0.0001,
        )

        result = generate_summary_v2(
            paper_id="test",
            text="Paper about X and Y.",
        )
        assert result["status"] == "generated"
        assert result["core_finding"] == "X causes Y."
        assert len(result["method_summary"]) == 2
        assert result["confidence"] == 0.85


class TestSummaryV2Output:
    """Test output file saving and loading."""

    def test_save_and_load(self, tmp_path):
        """Save output then load it back."""
        from scientra.ai.summary_v2 import _save_output, load_summary_v2
        import scientra.ai.summary_v2 as sv2

        with patch.object(sv2, "OUTPUT_DIR", tmp_path / "summary_v2"):
            data = {
                "paper_id": "test-load",
                "status": "generated",
                "core_finding": "Test finding",
                "confidence": 0.9,
            }
            _save_output("test-load", data)

            loaded = load_summary_v2("test-load")
            assert loaded is not None
            assert loaded["paper_id"] == "test-load"
            assert loaded["core_finding"] == "Test finding"

    def test_load_missing_returns_none(self, tmp_path):
        """Loading nonexistent file returns None."""
        from scientra.ai.summary_v2 import load_summary_v2
        import scientra.ai.summary_v2 as sv2

        with patch.object(sv2, "OUTPUT_DIR", tmp_path / "empty_dir"):
            result = load_summary_v2("nonexistent")
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
