"""Tests for Supplementary Intelligence Runner.

Uses Storage Layout v3 paths only. No DB/DB_v2.
"""

import json
import tempfile
from pathlib import Path

import pytest
from scientra.assets.supplementary_intelligence.supplementary_intelligence_runner import (
    SupplementaryIntelligenceRunner, V3_OUTPUT_ROOT,
)


class TestRunner:
    def test_empty_paper(self):
        runner = SupplementaryIntelligenceRunner(mode="rule")
        r = runner.run("nonexistent_paper_99999")
        assert r["success"] is False

    def test_get_supplementaries_no_data(self):
        runner = SupplementaryIntelligenceRunner()
        r = runner.get_supplementaries("nonexistent_paper_99999")
        assert r["available"] is False

    def test_get_summary_no_data(self):
        runner = SupplementaryIntelligenceRunner()
        r = runner.get_summary("nonexistent_paper_99999")
        assert r["available"] is False

    def test_get_evidence_no_data(self):
        runner = SupplementaryIntelligenceRunner()
        r = runner.get_evidence("nonexistent_paper_99999")
        assert r["available"] is False

    def test_get_chunks_no_data(self):
        runner = SupplementaryIntelligenceRunner()
        r = runner.get_chunks("nonexistent_paper_99999")
        assert r["available"] is False

    def test_v3_path(self):
        runner = SupplementaryIntelligenceRunner()
        p = runner._v3_path(V3_OUTPUT_ROOT)
        assert V3_OUTPUT_ROOT.replace("/", "\\") in str(p) or V3_OUTPUT_ROOT in str(p)

    def test_write_json(self, tmp_path):
        data = [{"k": "v"}]
        runner = SupplementaryIntelligenceRunner()
        runner._wj(tmp_path / "test.json", data)
        assert (tmp_path / "test.json").exists()
        assert json.loads((tmp_path / "test.json").read_text(encoding="utf-8")) == data

    def test_no_db_v2_paths(self):
        """Verify no DB/DB_v2 paths are used."""
        assert "DB/DB_v2" not in V3_OUTPUT_ROOT
        runner = SupplementaryIntelligenceRunner()
        # Check that get_supplementary_card doesn't reference DB_v2
        result = runner.get_supplementary_card("x", "y")
        assert "DB/DB_v2" not in str(result)

    def test_summary_md(self, tmp_path):
        runner = SupplementaryIntelligenceRunner()
        summary = {"paper_id": "p1", "generated_at": "2026-01-01", "mode_used": "rule", "supplementary_count": 1, "total_sections": 2, "total_evidence": 3, "total_chunks": 5, "embedded": False}
        cards = [{"label": "S1", "file_type": "pdf", "parse_status": "parsed", "section_count": 2, "evidence_count": 3, "quality_score": 0.8}]
        runner._write_summary_md(tmp_path / "summary.md", summary, cards)
        content = (tmp_path / "summary.md").read_text(encoding="utf-8")
        assert "p1" in content
        assert "S1" in content
