"""Tests for Supplementary Chunker."""

import pytest
from scientra.assets.supplementary_intelligence.supplementary_chunker import chunk_supplementary, _sliding_window


class TestChunker:
    def test_chunks_created(self):
        sections = [{"section_id": "s1", "section_type": "supplementary_methods", "text": "A" * 500}]
        evidence = [{"section_id": "s1", "evidence_id": "ev1", "evidence_type": "method_detail", "text": "B" * 200}]
        chunks = chunk_supplementary(sections, evidence, "p1", "a1", "supp/s1.pdf")
        assert len(chunks) > 0

    def test_chunk_structure(self):
        sections = [{"section_id": "s1", "section_type": "supplementary_methods", "text": "X" * 500}]
        chunks = chunk_supplementary(sections, [], "p1", "a1", "supp/s1.pdf")
        if chunks:
            c = chunks[0]
            for k in ["chunk_id", "paper_id", "asset_id", "section_id", "chunk_type", "text", "source_relative_path"]:
                assert k in c

    def test_traceability(self):
        sections = [{"section_id": "s_test", "section_type": "supplementary_methods", "text": "X" * 500}]
        chunks = chunk_supplementary(sections, [], "paper_x", "asset_x", "supp/s1.pdf")
        if chunks:
            c = chunks[0]
            assert c["paper_id"] == "paper_x"
            assert c["asset_id"] == "asset_x"
            assert c["section_id"] == "s_test"

    def test_sliding_window(self):
        text = "ABCDEFGHIJ" * 100
        chunks = _sliding_window(text, 200, 50)
        assert len(chunks) > 1
        # Verify overlap
        if len(chunks) >= 2:
            assert chunks[0][-50:] in chunks[1]

    def test_short_text(self):
        chunks = _sliding_window("short", 1200, 150)
        assert len(chunks) == 1
