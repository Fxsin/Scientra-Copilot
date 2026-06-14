"""Tests for Supplementary Card Builder."""

import pytest
from scientra.assets.supplementary_intelligence.supplementary_card_builder import SupplementaryCardBuilder


def _ctx(**kw):
    d = {"supplementary_id": "supp_1", "paper_id": "p1", "asset_id": "a1", "normalized_label": "Supplementary File 1",
         "asset_path": "/f.pdf", "source_relative_path": "assets/supp/f.pdf",
         "related_figures": ["fig_1"], "related_tables": ["tbl_1"], "related_datasets": []}
    d.update(kw)
    return d


class TestCardBuilder:
    def test_structure(self):
        b = SupplementaryCardBuilder()
        card = b.build(_ctx(), {"parse_status": "parsed", "file_type": "pdf", "text_length": 1000, "supplementary_id": "supp_1"},
                       [{"section_title": "Methods", "section_type": "supplementary_methods"}],
                       [{"evidence_id": "ev1", "evidence_type": "method_detail"}],
                       {"supplementary_summary": "Test summary", "key_contents": ["Methods"], "main_evidence_types": ["method_detail"], "grounding_sources": ["section_titles"], "mode": "rule", "interpretation_confidence": 0.7},
                       {"quality_score": 0.8, "warnings": [], "overclaim_risk": "low"})
        for k in ["supplementary_id", "paper_id", "asset_id", "label", "title", "file_type", "parse_status", "section_count", "evidence_count", "linked_figure_ids", "linked_table_ids", "quality_score", "mode"]:
            assert k in card

    def test_counts(self):
        b = SupplementaryCardBuilder()
        card = b.build(_ctx(), {"parse_status": "parsed", "file_type": "pdf", "supplementary_id": "supp_1"}, [{"section_type": "m"}, {"section_type": "r"}, {"section_type": "ref"}], [{"evidence_id": "e1"}, {"evidence_id": "e2"}, {"evidence_id": "e3"}, {"evidence_id": "e4"}], {"supplementary_summary": "", "key_contents": [], "main_evidence_types": [], "grounding_sources": [], "mode": "rule"}, {"quality_score": 0.5, "warnings": [], "overclaim_risk": "low"})
        assert card["section_count"] == 3
        assert card["evidence_count"] == 4

    def test_linked_ids(self):
        b = SupplementaryCardBuilder()
        card = b.build(_ctx(), {"parse_status": "parsed", "file_type": "pdf", "supplementary_id": "supp_1"}, [], [], {"grounding_sources": [], "key_contents": [], "main_evidence_types": [], "supplementary_summary": "", "mode": "rule"}, {"quality_score": 0.5, "warnings": [], "overclaim_risk": "low"})
        assert "fig_1" in card["linked_figure_ids"]
        assert "tbl_1" in card["linked_table_ids"]
