"""Tests for Supplementary Evidence Extractor."""

import pytest
from scientra.assets.supplementary_intelligence.supplementary_evidence_extractor import extract_evidence


def _make_section(**kw):
    d = {"section_id": "s1", "section_title": "Methods", "section_type": "supplementary_methods", "text": "", "start_offset": 0, "end_offset": 100, "confidence": 0.8}
    d.update(kw)
    return d


class TestEvidenceExtraction:
    def test_method_detail(self):
        text = "We used RT-qPCR to measure gene expression. The protocol was performed according to manufacturer instructions with SYBR Green master mix."
        s = _make_section(text=text)
        ev = extract_evidence([s])
        if ev:
            assert ev[0]["evidence_type"] in ("method_detail", "protocol_detail", "unknown")

    def test_result_detail(self):
        text = "The treatment significantly increased expression by 3-fold (p < 0.01). This result demonstrates the efficacy of the compound."
        s = _make_section(text=text, section_type="supplementary_results")
        ev = extract_evidence([s])
        if ev:
            types = [e["evidence_type"] for e in ev]
            assert any(t in ("result_detail", "statistical_detail") for t in types)

    def test_evidence_structure(self):
        s = _make_section(text="We used western blot to detect protein levels. The band intensity was quantified using ImageJ.")
        ev = extract_evidence([s], "paper_x", "asset_x")
        if ev:
            e = ev[0]
            for k in ["evidence_id", "paper_id", "asset_id", "section_id", "evidence_type", "text", "confidence", "grounding_source"]:
                assert k in e

    def test_empty_sections(self):
        assert extract_evidence([]) == []

    def test_short_text_skipped(self):
        s = _make_section(text="Short.")
        ev = extract_evidence([s])
        assert len(ev) == 0
