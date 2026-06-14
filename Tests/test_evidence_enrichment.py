"""Tests for Evidence Enrichment module.

Run:
    python -m pytest Tests/test_evidence_enrichment.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestEvidenceEnrichmentBatch:
    """Test batch prompt building."""

    def test_build_batch_prompt(self):
        """Batch prompt includes all chunks."""
        from scientra.ai.evidence_enrichment import _build_batch_prompt

        chunks = [
            {"chunk_id": "C001", "text": "Test chunk 1", "chunk_type": "key_result",
             "source_section": "Results", "confidence": "medium"},
            {"chunk_id": "C002", "text": "Test chunk 2", "chunk_type": "claim",
             "source_section": "Discussion", "confidence": "high"},
        ]
        prompt = _build_batch_prompt(chunks, 1)
        assert "C001" in prompt
        assert "C002" in prompt
        assert "Test chunk 1" in prompt
        assert "Test chunk 2" in prompt
        assert "Batch 1" in prompt


class TestEvidenceEnrichmentJSON:
    """Test JSON extraction."""

    def test_extract_enriched_response(self):
        """Extract enriched chunks from LLM response."""
        from scientra.ai.evidence_enrichment import _extract_json_from_response

        text = json.dumps({
            "enriched_chunks": [
                {
                    "chunk_id": "C1",
                    "ai_claim": "Autophagy is induced",
                    "ai_finding": "TEM showed autophagosomes",
                    "method_mentioned": ["TEM"],
                    "entity_mentioned": ["LC3", "Vip3Aa"],
                    "supports_claim": True,
                    "evidence_strength": "strong",
                    "limitations": [],
                    "confidence": 0.9,
                    "warnings": [],
                }
            ]
        })
        result = _extract_json_from_response(text)
        assert result is not None
        assert len(result["enriched_chunks"]) == 1
        assert result["enriched_chunks"][0]["ai_claim"] == "Autophagy is induced"


class TestEvidenceEnrichmentDisabled:
    """Test disabled/skip behavior."""

    def test_enrichment_skipped_when_disabled(self):
        """Returns skipped when task is disabled."""
        from scientra.ai.evidence_enrichment import enrich_evidence_chunks
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig

        original = get_config()
        try:
            # Disable evidence_enrichment
            cfg = LLMConfig(
                enabled=True,
                provider="deepseek",
                model="deepseek-chat",
                api_key="sk-test",
                enabled_tasks={"evidence_enrichment": False, "summary": True},
            )
            save_config(cfg)
            reload_config()

            result = enrich_evidence_chunks(paper_id="test-skip")
            assert result["status"] == "skipped"
            assert "disabled" in result.get("reason", "").lower()
        finally:
            save_config(original)
            reload_config()

    def test_enrichment_chunks_file_not_found(self):
        """Returns failed when chunks file doesn't exist."""
        from scientra.ai.evidence_enrichment import enrich_evidence_chunks
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig

        original = get_config()
        try:
            cfg = LLMConfig(
                enabled=True,
                provider="deepseek",
                model="deepseek-chat",
                api_key="sk-test",
                enabled_tasks={"evidence_enrichment": True, "summary": True},
            )
            save_config(cfg)
            reload_config()

            result = enrich_evidence_chunks(
                paper_id="nonexistent_paper_12345",
                chunks_path="/nonexistent/path/chunks.json",
            )
            assert result["status"] == "failed"
            assert "not found" in result.get("error", "").lower()
        finally:
            save_config(original)
            reload_config()


class TestEvidenceEnrichmentProcessing:
    """Test batch processing with mocks."""

    def test_single_batch_processing(self, tmp_path):
        """Process a single batch successfully."""
        from scientra.ai.evidence_enrichment import enrich_evidence_chunks
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig
        from scientra.ai.schemas import LLMResponse

        original = get_config()
        try:
            cfg = LLMConfig(
                enabled=True,
                provider="deepseek",
                model="deepseek-chat",
                api_key="sk-test",
                enabled_tasks={"evidence_enrichment": True},
            )
            save_config(cfg)
            reload_config()

            # Create a temp chunks file
            chunks_file = tmp_path / "evidence_chunks.json"
            chunks_data = {
                "paper_id": "test-paper",
                "chunks": [
                    {"chunk_id": "C1", "text": "Long enough chunk text " * 10,
                     "chunk_type": "key_result", "source_section": "Results",
                     "confidence": "medium"},
                    {"chunk_id": "C2", "text": "Another long chunk text " * 10,
                     "chunk_type": "claim", "source_section": "Discussion",
                     "confidence": "high"},
                ],
            }
            chunks_file.write_text(json.dumps(chunks_data))

            with patch("scientra.ai.call_llm") as mock_call:
                mock_response = LLMResponse(
                    success=True, provider="deepseek", model="deepseek-chat",
                    text=json.dumps({
                        "enriched_chunks": [
                            {"chunk_id": "C1", "ai_claim": "Claim 1", "ai_finding": "Finding 1",
                             "method_mentioned": ["TEM"], "entity_mentioned": ["LC3"],
                             "supports_claim": True, "evidence_strength": "strong",
                             "limitations": [], "confidence": 0.9, "warnings": []},
                            {"chunk_id": "C2", "ai_claim": "Claim 2", "ai_finding": "Finding 2",
                             "method_mentioned": ["Western"], "entity_mentioned": ["Actin"],
                             "supports_claim": True, "evidence_strength": "moderate",
                             "limitations": [], "confidence": 0.8, "warnings": []},
                        ]
                    }),
                    input_tokens=50, output_tokens=30, total_tokens=80,
                    cost_estimate=0.00005,
                )
                mock_call.return_value = mock_response

                result = enrich_evidence_chunks(
                    paper_id="test-paper",
                    chunks_path=str(chunks_file),
                    batch_size=5,
                )

                assert result["status"] == "enriched"
                assert result["enriched_chunks"] == 2
                assert result["batch_count"] == 1
                assert result["failed_batches"] == 0
                assert len(result["chunks"]) == 2
                assert result["chunks"][0]["ai_claim"] == "Claim 1"

        finally:
            save_config(original)
            reload_config()

    def test_batch_failure_does_not_block(self, tmp_path):
        """A failed batch doesn't block other batches from processing."""
        from scientra.ai.evidence_enrichment import enrich_evidence_chunks
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig
        from scientra.ai.schemas import LLMResponse

        original = get_config()
        try:
            cfg = LLMConfig(
                enabled=True,
                provider="deepseek",
                model="deepseek-chat",
                api_key="sk-test",
                enabled_tasks={"evidence_enrichment": True},
            )
            save_config(cfg)
            reload_config()

            # Create chunks: 2 batches of 2 chunks each
            chunks = []
            for i in range(4):
                chunks.append({
                    "chunk_id": f"C{i}",
                    "text": f"Chunk text number {i} " * 10,
                    "chunk_type": "claim",
                    "source_section": "Results",
                    "confidence": "medium",
                })

            chunks_file = tmp_path / "evidence_chunks.json"
            chunks_file.write_text(json.dumps({"paper_id": "test", "chunks": chunks}))

            with patch("scientra.ai.call_llm") as mock_call:
                call_count = [0]

                def side_effect(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        # First batch fails
                        return LLMResponse.failure("deepseek", "deepseek-chat", "Timeout")
                    else:
                        # Second batch succeeds
                        return LLMResponse(
                            success=True, provider="deepseek", model="deepseek-chat",
                            text=json.dumps({
                                "enriched_chunks": [
                                    {"chunk_id": "C2", "ai_claim": "OK", "ai_finding": "OK",
                                     "method_mentioned": [], "entity_mentioned": [],
                                     "supports_claim": True, "evidence_strength": "moderate",
                                     "limitations": [], "confidence": 0.7, "warnings": []},
                                    {"chunk_id": "C3", "ai_claim": "OK2", "ai_finding": "OK2",
                                     "method_mentioned": [], "entity_mentioned": [],
                                     "supports_claim": True, "evidence_strength": "moderate",
                                     "limitations": [], "confidence": 0.7, "warnings": []},
                                ]
                            }),
                            input_tokens=20, output_tokens=10, total_tokens=30,
                            cost_estimate=0.00001,
                        )

                mock_call.side_effect = side_effect

                result = enrich_evidence_chunks(
                    paper_id="test",
                    chunks_path=str(chunks_file),
                    batch_size=2,
                )

                # Should still complete with some enriched chunks
                assert result["status"] == "enriched"
                assert result["failed_batches"] == 1
                assert len(result["chunks"]) == 4  # 2 from failed batch + 2 from success

        finally:
            save_config(original)
            reload_config()


class TestEvidenceEnrichmentOutput:
    """Test output saving and loading."""

    def test_save_and_load(self, tmp_path):
        """Save then load enrichment output."""
        from scientra.ai.evidence_enrichment import _save_output, load_evidence_enrichment
        import scientra.ai.evidence_enrichment as ee

        with patch.object(ee, "OUTPUT_DIR", tmp_path / "enrichment"):
            data = {
                "paper_id": "test-ee",
                "status": "enriched",
                "chunks": [{"chunk_id": "C1", "ai_claim": "Test"}],
            }
            _save_output("test-ee", data)

            loaded = load_evidence_enrichment("test-ee")
            assert loaded is not None
            assert loaded["paper_id"] == "test-ee"
            assert loaded["chunks"][0]["ai_claim"] == "Test"

    def test_load_missing_returns_none(self, tmp_path):
        """Load nonexistent returns None."""
        from scientra.ai.evidence_enrichment import load_evidence_enrichment
        import scientra.ai.evidence_enrichment as ee

        with patch.object(ee, "OUTPUT_DIR", tmp_path / "empty"):
            assert load_evidence_enrichment("nonexistent") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
