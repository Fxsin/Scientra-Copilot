"""Tests for Table Quality Checker."""

import pytest
from scientra.assets.table_intelligence.table_quality_checker import TableQualityChecker


def _ctx(**kw):
    d = {"table_id": "t_001", "caption": "Table 1. DEG analysis.", "body_mentions": [{"s": "x"}], "linked_evidence": [{"e": "ev1"}], "context_completeness": {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True, "has_readable_table": True}, "warnings": []}
    d.update(kw)
    return d


def _struct(**kw):
    d = {"table_id": "t_001", "parse_status": "parsed", "sheets": [{}]}
    d.update(kw)
    return d


def _interp(**kw):
    d = {"table_id": "t_001", "table_summary": "DEG results.", "key_finding": "500 DEGs found.", "table_type": "differential_expression", "evidence_strength": "strong", "statistical_fields_summary": ["log2FC", "pvalue"], "is_large_table": False, "mode": "rule"}
    d.update(kw)
    return d


class TestQualityChecker:
    def test_full_context(self):
        c = TableQualityChecker()
        r = c.check(_ctx(), _struct(), _interp())
        assert r["quality_score"] > 0.5
        assert r["overclaim_risk"] == "low"

    def test_no_caption(self):
        c = TableQualityChecker()
        r = c.check(_ctx(caption="", context_completeness={"has_caption": False, "has_body_mention": True, "has_linked_evidence": True, "has_readable_table": True}), _struct(), _interp())
        assert "caption_missing_or_short" in r["issues"]

    def test_overclaim_detection(self):
        c = TableQualityChecker()
        r = c.check(_ctx(context_completeness={"has_caption": True, "has_body_mention": False, "has_linked_evidence": False, "has_readable_table": False}), _struct(), _interp(key_finding="This definitively proves the novel breakthrough discovery, establishing the mechanism conclusively."))
        assert r["overclaim_risk"] in ("medium", "high")

    def test_large_table_sampled(self):
        c = TableQualityChecker()
        r = c.check(_ctx(), _struct(), _interp(is_large_table=True))
        assert "large_table_sampled" in r["issues"]

    def test_unparseable_structure(self):
        c = TableQualityChecker()
        r = c.check(_ctx(), {"parse_status": "unsupported"}, _interp())
        assert "structure_unparseable" in r["issues"]

    def test_check_all(self):
        c = TableQualityChecker()
        results = c.check_all([_ctx(table_id="t1"), _ctx(table_id="t2")], [_struct(), _struct()], [_interp(), _interp()])
        assert len(results) == 2
