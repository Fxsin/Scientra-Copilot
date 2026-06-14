"""Tests for Table Interpreter."""

import pytest
from scientra.assets.table_intelligence.table_interpreter import TableInterpreter


def _ctx(**kw):
    d = {
        "table_id": "tbl_001", "paper_id": "p_test", "asset_id": "a_001",
        "normalized_label": "Table 1", "asset_path": "/t.xlsx", "asset_filename": "Table_1.xlsx",
        "caption": "Table 1. Differential expression analysis of treated vs control.",
        "body_mentions": [{"mention_id": "m1", "sentence": "DE genes are listed in Table 1.", "section": "results", "source_type": "body_text", "citation_text": "Table 1"}],
        "linked_evidence": [{"evidence_id": "ev1", "text": "500 genes DE.", "claim": "Treatment alters expression.", "finding": "500 DEGs identified.", "method": "DESeq2"}],
        "related_claims": ["Treatment alters expression."], "related_methods": ["DESeq2"],
        "context_completeness": {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True, "has_readable_table": True},
        "warnings": [],
    }
    d.update(kw)
    return d


def _struct(**kw):
    d = {"table_id": "tbl_001", "asset_id": "a_001", "parse_status": "parsed", "file_type": "xlsx",
         "sheets": [{"sheet_name": "S1", "n_rows": 500, "n_columns": 6, "headers": ["Gene", "log2FC", "pvalue", "padj", "baseMean", "stat"], "sample_rows": [["GeneA", "2.5", "0.001", "0.01", "100", "5.2"]], "detected_empty_rows": 0, "detected_merged_cells": False}],
         "parse_warnings": []}
    d.update(kw)
    return d


def _schema(**kw):
    d = {"table_id": "tbl_001", "table_type": "differential_expression", "confidence": 0.9, "key_columns": {"log2fc": ["log2FC"], "padj": ["padj"]}, "reason": "Matched: log2FC, padj"}
    d.update(kw)
    return d


def _stat(**kw):
    d = {"table_id": "tbl_001", "statistical_fields": [{"field": "log2FC", "category": "effect_size"}, {"field": "p_value", "category": "significance"}], "significance_columns": ["pvalue", "padj"], "effect_size_columns": ["log2FC"], "detected_thresholds": {}, "confidence": 0.5}
    d.update(kw)
    return d


class TestRuleMode:
    def test_structure(self):
        interp = TableInterpreter(mode="rule")
        r = interp.interpret(_ctx(), _struct(), _schema(), _stat())
        for k in ["table_summary", "key_finding", "table_type", "evidence_strength", "important_columns", "grounding_sources", "limitations", "mode"]:
            assert k in r
        assert r["mode"] == "rule"

    def test_large_table_warning(self):
        interp = TableInterpreter(mode="rule")
        r = interp.interpret(_ctx(), _struct(), _schema(), _stat())
        if r.get("is_large_table"):
            assert any("sample" in l.lower() for l in r.get("limitations", []))

    def test_minimal_context(self):
        interp = TableInterpreter(mode="rule")
        ctx = _ctx(caption="", body_mentions=[], linked_evidence=[], related_claims=[], related_methods=[],
                   context_completeness={"has_caption": False, "has_body_mention": False, "has_linked_evidence": False, "has_readable_table": False})
        r = interp.interpret(ctx, None, _schema(), _stat())
        assert r["evidence_strength"] in ("weak", "unclear")
        assert r["interpretation_confidence"] < 0.5

    def test_no_api_key_needed(self):
        interp = TableInterpreter(mode="rule")
        r = interp.interpret(_ctx(), _struct(), _schema(), _stat())
        assert r["mode"] == "rule"

    def test_interpret_all(self):
        interp = TableInterpreter(mode="rule")
        results = interp.interpret_all([_ctx(table_id="t1"), _ctx(table_id="t2")])
        assert len(results) == 2


class TestLLMMode:
    def test_auto_mode(self):
        interp = TableInterpreter(mode="auto")
        assert interp._resolve_mode() in ("rule", "llm")
