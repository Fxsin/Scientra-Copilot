"""Tests for Table Intelligence Runner."""

import json
import tempfile
from pathlib import Path

import pytest
from scientra.assets.table_intelligence.table_intelligence_runner import TableIntelligenceRunner


class TestRunner:
    def test_empty_paper(self):
        runner = TableIntelligenceRunner(mode="rule")
        result = runner.run("nonexistent_paper_99999")
        assert result["success"] is False

    def test_get_tables_no_data(self):
        runner = TableIntelligenceRunner()
        result = runner.get_tables("nonexistent_paper_99999")
        assert result["available"] is False

    def test_get_table_card_no_data(self):
        runner = TableIntelligenceRunner()
        result = runner.get_table_card("nonexistent_paper_99999", "tbl_xxx")
        assert result["available"] is False

    def test_get_summary_no_data(self):
        runner = TableIntelligenceRunner()
        result = runner.get_summary("nonexistent_paper_99999")
        assert result["available"] is False
        assert result["table_count"] == 0

    def test_write_json(self, tmp_path):
        data = [{"k": "v"}]
        p = tmp_path / "test.json"
        TableIntelligenceRunner._wj(p, data)
        assert p.exists()
        assert json.loads(p.read_text()) == data

    def test_output_exists(self, tmp_path):
        for f in ["table_contexts.json", "table_cards.json"]:
            (tmp_path / f).write_text("{}")
        assert TableIntelligenceRunner._output_exists(tmp_path)

    def test_output_not_exists(self, tmp_path):
        assert not TableIntelligenceRunner._output_exists(tmp_path)

    def test_build_summary(self):
        s = TableIntelligenceRunner._build_summary(
            "p_test", [{"table_id": "t1"}],
            [{"table_id": "t1", "table_type": "differential_expression", "mode": "rule"}],
            [{"table_id": "t1", "quality_score": 0.85, "overclaim_risk": "low"}],
            "rule",
        )
        assert s["success"]
        assert s["table_count"] == 1
        assert s["quality_distribution"]["high"] == 1

    def test_write_summary_md(self, tmp_path):
        s = {"paper_id": "p_test", "generated_at": "2026-06-14T00:00:00Z", "table_count": 1, "mode_used": "rule", "table_types": {"differential_expression": 1}, "quality_distribution": {"high": 1, "medium": 0, "low": 0}, "overclaim_summary": {"low": 1}}
        cards = [{"label": "Table 1", "table_type": "differential_expression", "n_rows": 100, "n_columns": 6, "quality_score": 0.85, "overclaim_risk": "low", "mode": "rule"}]
        p = tmp_path / "summary.md"
        TableIntelligenceRunner._write_summary_md(p, s, cards)
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert "p_test" in content
        assert "Table 1" in content
        assert "differential_expression" in content
