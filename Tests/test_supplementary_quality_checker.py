"""Tests for Supplementary Quality Checker."""

import pytest
from scientra.assets.supplementary_intelligence.supplementary_quality_checker import SupplementaryQualityChecker


class TestQualityChecker:
    def test_parsed_ok(self):
        c = SupplementaryQualityChecker()
        r = c.check({"supplementary_id": "s1", "parse_status": "parsed", "text_length": 1000}, [{"section_type": "supplementary_methods"}], {"supplementary_summary": "test", "grounding_sources": ["section_titles"], "key_contents": ["Methods"], "main_evidence_types": ["method_detail"]})
        assert r["quality_score"] > 0.5

    def test_unsupported(self):
        c = SupplementaryQualityChecker()
        r = c.check({"supplementary_id": "s2", "parse_status": "unsupported", "text_length": 10}, [], {})
        assert "unsupported_format" in r["issues"]

    def test_low_information(self):
        c = SupplementaryQualityChecker()
        r = c.check({"supplementary_id": "s3", "parse_status": "parsed", "text_length": 50}, [{"section_type": "supplementary_references"}], {"grounding_sources": [], "key_contents": [], "main_evidence_types": []})
        assert "low_information" in r["issues"]

    def test_overclaim(self):
        c = SupplementaryQualityChecker()
        r = c.check({"supplementary_id": "s4", "parse_status": "parsed", "text_length": 1000}, [{"section_type": "supplementary_methods"}], {"supplementary_summary": "This definitively proves the novel breakthrough.", "key_contents": [], "grounding_sources": ["section_titles"], "main_evidence_types": [], "mode": "rule"})
        assert r["overclaim_risk"] in ("medium", "high")

    def test_references_only(self):
        c = SupplementaryQualityChecker()
        r = c.check({"supplementary_id": "s5", "parse_status": "parsed", "text_length": 500}, [{"section_type": "supplementary_references", "section_title": "References", "confidence": 0.8}], {"grounding_sources": [], "key_contents": [], "main_evidence_types": [], "mode": "rule"})
        assert "references_only" in r["issues"]
