"""Tests for Gap Extraction module.

Run: python -m pytest Tests/test_gap_extraction.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VALID_GAP_JSON = json.dumps({
    "paper_id": "test",
    "gaps": [
        {"gap_id": "test:gap:0001", "gap_statement": "Unknown mechanism", "gap_type": "mechanistic",
         "based_on_evidence": ["C1"], "missing_information": "Kinase pathway", "why_it_matters": "Drug target",
         "confidence": 0.85, "warnings": []},
        {"gap_id": "test:gap:0002", "gap_statement": "Limited to one cell line", "gap_type": "scope",
         "based_on_evidence": ["C3"], "missing_information": "In vivo validation", "why_it_matters": "Translation",
         "confidence": 0.9, "warnings": ["Authors acknowledge this limitation"]},
    ]
})


class TestGapPrompt:
    def test_prompt_renders_variables(self):
        from scientra.ai.gap_extraction import _render_prompt
        prompt = _render_prompt("test", {"title": "T", "core_finding": "X"}, None, 8)
        assert "T" in prompt
        assert "X" in prompt
        assert "test" in prompt
        assert "8" in prompt

    def test_prompt_with_evidence(self):
        from scientra.ai.gap_extraction import _render_prompt
        ee = {"chunks": [{"chunk_id": "C1", "ai_claim": "Y"}]}
        prompt = _render_prompt("t", {"title": "T"}, ee, 5)
        assert "Evidence Enrichment" in prompt


class TestGapJSON:
    def test_extract_valid_json(self):
        from scientra.ai.gap_extraction import _extract_json_from_response
        r = _extract_json_from_response(VALID_GAP_JSON)
        assert r is not None
        assert len(r["gaps"]) == 2

    def test_extract_invalid(self):
        from scientra.ai.gap_extraction import _extract_json_from_response
        assert _extract_json_from_response("not json") is None


class TestGapDisabled:
    def test_skipped_when_disabled(self):
        from scientra.ai.gap_extraction import extract_research_gaps
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig

        original = get_config()
        try:
            cfg = LLMConfig(enabled=True, provider="deepseek", model="deepseek-chat",
                           api_key="sk-test", enabled_tasks={"gap_extraction": False})
            save_config(cfg); reload_config()
            result = extract_research_gaps(paper_id="test")
            assert result["status"] == "skipped"
        finally:
            save_config(original); reload_config()


class TestGapProcessing:
    @patch("scientra.ai.call_llm")
    def test_successful_extraction(self, mock_call):
        from scientra.ai.gap_extraction import extract_research_gaps
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig
        from scientra.ai.schemas import LLMResponse

        original = get_config()
        try:
            cfg = LLMConfig(enabled=True, provider="deepseek", model="deepseek-chat",
                           api_key="sk-test", enabled_tasks={"gap_extraction": True})
            save_config(cfg); reload_config()

            mock_call.return_value = LLMResponse(
                success=True, provider="deepseek", model="deepseek-chat",
                text=VALID_GAP_JSON, input_tokens=100, output_tokens=120, total_tokens=220,
                cost_estimate=0.0001,
            )
            result = extract_research_gaps(paper_id="test", max_gaps=4)
            assert result["status"] == "generated"
            assert len(result["gaps"]) == 2
            assert result["gaps"][0]["gap_type"] == "mechanistic"
        finally:
            save_config(original); reload_config()

    @patch("scientra.ai.call_llm")
    def test_llm_failure_fallback(self, mock_call):
        from scientra.ai.gap_extraction import extract_research_gaps
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig
        from scientra.ai.schemas import LLMResponse

        original = get_config()
        try:
            cfg = LLMConfig(enabled=True, provider="deepseek", model="deepseek-chat",
                           api_key="sk-test", enabled_tasks={"gap_extraction": True})
            save_config(cfg); reload_config()
            mock_call.return_value = LLMResponse.failure("deepseek", "deepseek-chat", "Timeout")
            result = extract_research_gaps(paper_id="test")
            assert result["status"] == "fallback"
            assert result["gaps"] == []
        finally:
            save_config(original); reload_config()


class TestGapOutput:
    def test_save_and_load(self, tmp_path):
        from scientra.ai.gap_extraction import _save_output, load_gaps
        import scientra.ai.gap_extraction as ge

        with patch.object(ge, "OUTPUT_DIR", tmp_path / "gaps"):
            data = {"paper_id": "t", "gaps": [{"gap_id": "t:gap:0001", "gap_statement": "G"}]}
            _save_output("t", data)
            loaded = load_gaps("t")
            assert loaded is not None
            assert loaded["gaps"][0]["gap_statement"] == "G"

    def test_load_missing(self, tmp_path):
        from scientra.ai.gap_extraction import load_gaps
        import scientra.ai.gap_extraction as ge

        with patch.object(ge, "OUTPUT_DIR", tmp_path / "empty"):
            assert load_gaps("nope") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
