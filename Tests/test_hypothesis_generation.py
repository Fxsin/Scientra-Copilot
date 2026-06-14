"""Tests for Hypothesis Generation module.

Run: python -m pytest Tests/test_hypothesis_generation.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VALID_HYP_JSON = json.dumps({
    "paper_id": "test",
    "hypotheses": [
        {"hypothesis_id": "test:hyp:0001", "hypothesis_statement": "If X then Y because Z.",
         "rationale": "Based on Gap 1", "linked_gap_id": "test:gap:0001",
         "supporting_evidence": ["C1"], "testable_prediction": "Y will increase",
         "suggested_experiment": "CRISPR KO + RNA-seq", "risk_level": "medium",
         "confidence": 0.8, "warnings": []},
    ]
})


class TestHypothesisPrompt:
    def test_prompt_renders(self):
        from scientra.ai.hypothesis_generation import _render_prompt
        gaps = {"gaps": [{"gap_id": "G1", "gap_statement": "Missing X"}]}
        sv2 = {"core_finding": "Y", "key_evidence": []}
        prompt = _render_prompt("t", gaps, sv2, None, 8)
        assert "Missing X" in prompt
        assert "Y" in prompt

    def test_make_slim(self):
        from scientra.ai.hypothesis_generation import _make_slim
        d = {"a": 1, "b": 2, "c": 3}
        slim = _make_slim(d, ["a", "b"])
        assert "a" in slim
        assert "c" not in slim


class TestHypothesisJSON:
    def test_extract_valid(self):
        from scientra.ai.hypothesis_generation import _extract_json_from_response
        r = _extract_json_from_response(VALID_HYP_JSON)
        assert r is not None
        assert len(r["hypotheses"]) == 1


class TestHypothesisDisabled:
    def test_skipped_when_disabled(self):
        from scientra.ai.hypothesis_generation import generate_hypotheses
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig

        original = get_config()
        try:
            cfg = LLMConfig(enabled=True, provider="deepseek", model="deepseek-chat",
                           api_key="sk-test", enabled_tasks={"hypothesis_generation": False})
            save_config(cfg); reload_config()
            result = generate_hypotheses(paper_id="test")
            assert result["status"] == "skipped"
        finally:
            save_config(original); reload_config()


class TestHypothesisProcessing:
    @patch("scientra.ai.call_llm")
    def test_successful_generation(self, mock_call, tmp_path):
        from scientra.ai.hypothesis_generation import generate_hypotheses
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig
        from scientra.ai.schemas import LLMResponse
        import scientra.ai.hypothesis_generation as hg

        original = get_config()
        try:
            cfg = LLMConfig(enabled=True, provider="deepseek", model="deepseek-chat",
                           api_key="sk-test", enabled_tasks={"hypothesis_generation": True})
            save_config(cfg); reload_config()

            # Create temp files with correct path structure
            assets = tmp_path / "03_Assets" / "ai"
            gaps_dir = assets / "gaps"
            gaps_dir.mkdir(parents=True)
            (gaps_dir / "test.json").write_text(json.dumps({
                "paper_id": "test", "gaps": [{"gap_id": "test:gap:0001", "gap_statement": "Gap 1"}]
            }))
            sv2_dir = assets / "summary_v2"
            sv2_dir.mkdir(parents=True)
            (sv2_dir / "test.json").write_text(json.dumps({
                "paper_id": "test", "core_finding": "Finding", "key_evidence": [], "main_claims": []
            }))

            with patch.object(hg, "OUTPUT_DIR", tmp_path / "out"):
                with patch.object(hg, "PROJECT_ROOT", tmp_path):
                    mock_call.return_value = LLMResponse(
                        success=True, provider="deepseek", model="deepseek-chat",
                        text=VALID_HYP_JSON, input_tokens=80, output_tokens=100, total_tokens=180,
                        cost_estimate=0.00008,
                    )
                    result = generate_hypotheses(paper_id="test", max_hypotheses=5)
                    assert result["status"] == "generated"
                    assert len(result["hypotheses"]) == 1
                    assert result["hypotheses"][0]["risk_level"] == "medium"
        finally:
            save_config(original); reload_config()

    @patch("scientra.ai.call_llm")
    def test_llm_failure(self, mock_call, tmp_path):
        from scientra.ai.hypothesis_generation import generate_hypotheses
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig
        from scientra.ai.schemas import LLMResponse
        import scientra.ai.hypothesis_generation as hg

        original = get_config()
        try:
            cfg = LLMConfig(enabled=True, provider="deepseek", model="deepseek-chat",
                           api_key="sk-test", enabled_tasks={"hypothesis_generation": True})
            save_config(cfg); reload_config()

            assets = tmp_path / "03_Assets" / "ai"
            gaps_dir = assets / "gaps"
            gaps_dir.mkdir(parents=True)
            (gaps_dir / "test.json").write_text(json.dumps({
                "paper_id": "test", "gaps": [{"gap_id": "g1"}]
            }))
            sv2_dir = assets / "summary_v2"
            sv2_dir.mkdir(parents=True)
            (sv2_dir / "test.json").write_text(json.dumps({"core_finding": "F", "key_evidence": [], "main_claims": []}))

            with patch.object(hg, "OUTPUT_DIR", tmp_path / "out"):
                with patch.object(hg, "PROJECT_ROOT", tmp_path):
                    mock_call.return_value = LLMResponse.failure("deepseek", "deepseek-chat", "Error")
                    result = generate_hypotheses(paper_id="test")
                    assert result["status"] == "fallback"
        finally:
            save_config(original); reload_config()


class TestHypothesisOutput:
    def test_save_and_load(self, tmp_path):
        from scientra.ai.hypothesis_generation import _save_output, load_hypotheses
        import scientra.ai.hypothesis_generation as hg

        with patch.object(hg, "OUTPUT_DIR", tmp_path / "hyps"):
            _save_output("t", {"paper_id": "t", "hypotheses": [{"hypothesis_id": "t:hyp:0001"}]})
            loaded = load_hypotheses("t")
            assert loaded is not None
            assert loaded["hypotheses"][0]["hypothesis_id"] == "t:hyp:0001"

    def test_load_missing(self, tmp_path):
        from scientra.ai.hypothesis_generation import load_hypotheses
        import scientra.ai.hypothesis_generation as hg

        with patch.object(hg, "OUTPUT_DIR", tmp_path / "empty"):
            assert load_hypotheses("nope") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
