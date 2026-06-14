"""Tests for Table Card Builder."""

import pytest
from scientra.assets.table_intelligence.table_card_builder import TableCardBuilder


def _ctx(**kw):
    d = {"table_id": "t_001", "paper_id": "p_test", "asset_id": "a_001", "normalized_label": "Table 1", "asset_path": "/t.xlsx", "caption": "Table 1. DEG analysis results.", "linked_evidence": [{"evidence_id": "ev1"}], "warnings": []}
    d.update(kw)
    return d


def _struct(**kw):
    d = {"table_id": "t_001", "sheets": [{"n_rows": 100, "n_columns": 6}]}
    d.update(kw)
    return d


def _interp(**kw):
    d = {"table_id": "t_001", "table_summary": "DEG results.", "key_finding": "500 DEGs.", "table_type": "differential_expression", "evidence_strength": "strong", "important_columns": ["log2FC", "padj"], "related_claims": ["C1"], "detected_entities": [], "statistical_fields_summary": ["log2FC", "pvalue"], "interpretation_confidence": 0.8, "mode": "rule"}
    d.update(kw)
    return d


def _quality(**kw):
    d = {"table_id": "t_001", "quality_score": 0.85, "warnings": [], "overclaim_risk": "low"}
    d.update(kw)
    return d


class TestCardBuilder:
    def test_structure(self):
        b = TableCardBuilder()
        card = b.build(_ctx(), _struct(), _interp(), _quality())
        for k in ["table_id", "paper_id", "label", "title", "table_type", "n_rows", "n_columns", "important_columns", "table_summary", "key_finding", "evidence_strength", "linked_evidence_ids", "statistical_fields", "quality_score", "overclaim_risk", "mode"]:
            assert k in card

    def test_dimensions(self):
        b = TableCardBuilder()
        card = b.build(_ctx(), _struct(), _interp(), _quality())
        assert card["n_rows"] == 100
        assert card["n_columns"] == 6

    def test_linked_evidence(self):
        b = TableCardBuilder()
        card = b.build(_ctx(), _struct(), _interp(), _quality())
        assert "ev1" in card["linked_evidence_ids"]

    def test_warnings_merged(self):
        b = TableCardBuilder()
        card = b.build(_ctx(warnings=["W1"]), _struct(), _interp(), _quality(warnings=["W2"]))
        assert "W1" in card["warnings"]
        assert "W2" in card["warnings"]

    def test_build_all(self):
        b = TableCardBuilder()
        cards = b.build_all([_ctx(table_id="t1"), _ctx(table_id="t2")], [_struct(), _struct()], [_interp(), _interp()], [_quality(), _quality()])
        assert len(cards) == 2

    def test_mode_preserved(self):
        b = TableCardBuilder()
        assert b.build(_ctx(), _struct(), _interp(mode="llm"), _quality())["mode"] == "llm"
        assert b.build(_ctx(), _struct(), _interp(mode="rule"), _quality())["mode"] == "rule"
