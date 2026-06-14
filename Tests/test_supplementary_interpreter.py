"""Tests for Supplementary Interpreter."""

import pytest
from scientra.assets.supplementary_intelligence.supplementary_interpreter import SupplementaryInterpreter


def _ctx(**kw):
    d = {"supplementary_id": "supp_1", "paper_id": "p1", "asset_id": "a1", "normalized_label": "Supplementary File 1",
         "asset_path": "/f.pdf", "source_relative_path": "assets/supp/f.pdf", "caption": "",
         "body_mentions": [{"mention_id": "m1", "sentence": "See Supplementary File 1 for methods.", "section": "methods", "source_type": "body_text"}],
         "linked_evidence": [], "related_figures": [], "related_tables": [], "related_datasets": [],
         "context_completeness": {"has_parseable_text": True, "has_sections": True, "has_body_mention": True, "has_linked_evidence": False, "has_related_assets": False}}
    d.update(kw)
    return d


class TestRuleMode:
    def test_structure(self):
        i = SupplementaryInterpreter(mode="rule")
        r = i.interpret(_ctx(), [{"section_title": "Supplementary Methods", "section_type": "supplementary_methods"}], [{"evidence_type": "method_detail"}])
        for k in ["supplementary_summary", "key_contents", "main_evidence_types", "grounding_sources", "limitations", "mode"]:
            assert k in r
        assert r["mode"] == "rule"

    def test_no_api_key(self):
        i = SupplementaryInterpreter(mode="rule")
        r = i.interpret(_ctx())
        assert "grounding_sources" in r

    def test_empty_sections(self):
        i = SupplementaryInterpreter(mode="rule")
        r = i.interpret(_ctx(context_completeness={"has_body_mention": False, "has_parseable_text": True, "has_sections": False, "has_linked_evidence": False, "has_related_assets": False}), [], [])
        assert "No sections detected" in str(r.get("limitations", []))


class TestLLMMode:
    def test_auto_mode(self):
        i = SupplementaryInterpreter(mode="auto")
        assert i._resolve_mode() in ("rule", "llm")

    def test_rule_mode_forced(self):
        i = SupplementaryInterpreter(mode="rule")
        assert i._resolve_mode() == "rule"
