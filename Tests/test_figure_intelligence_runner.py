"""Tests for Figure Intelligence Runner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from scientra.assets.figure_intelligence.figure_intelligence_runner import FigureIntelligenceRunner


class TestRunner:
    def test_run_empty_paper(self):
        runner = FigureIntelligenceRunner(mode="rule")
        result = runner.run("nonexistent_paper_99999")
        assert result["success"] is False
        assert "error" in result

    def test_get_figures_no_data(self):
        runner = FigureIntelligenceRunner()
        result = runner.get_figures("nonexistent_paper_99999")
        assert result["available"] is False
        assert "figures" in result

    def test_get_figure_card_no_data(self):
        runner = FigureIntelligenceRunner()
        result = runner.get_figure_card("nonexistent_paper_99999", "fig_xxx")
        assert result["available"] is False

    def test_get_summary_no_data(self):
        runner = FigureIntelligenceRunner()
        result = runner.get_summary("nonexistent_paper_99999")
        assert result["available"] is False
        assert result["figure_count"] == 0

    def test_write_json(self, tmp_path):
        data = [{"key": "value"}]
        path = tmp_path / "test.json"
        FigureIntelligenceRunner._write_json(path, data)
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == data

    def test_output_exists(self, tmp_path):
        # Create required files
        for f in ["figure_contexts.json", "figure_interpretations.json", "figure_cards.json"]:
            (tmp_path / f).write_text("{}")
        assert FigureIntelligenceRunner._output_exists(tmp_path)

    def test_output_not_exists(self, tmp_path):
        assert not FigureIntelligenceRunner._output_exists(tmp_path)

    def test_build_summary_structure(self):
        summary = FigureIntelligenceRunner._build_summary(
            "paper_test",
            [{"figure_id": "fig_1"}],
            [
                {
                    "figure_id": "fig_1",
                    "evidence_type": "western_blot",
                    "mode": "rule",
                }
            ],
            [
                {
                    "figure_id": "fig_1",
                    "quality_score": 0.85,
                    "overclaim_risk": "low",
                }
            ],
            "rule",
        )
        assert summary["success"] is True
        assert summary["figure_count"] == 1
        assert summary["mode_used"] == "rule"
        assert "western_blot" in summary["evidence_types"]
        assert summary["quality_distribution"]["high"] == 1

    def test_write_summary_md(self, tmp_path):
        summary = {
            "paper_id": "paper_test",
            "generated_at": "2026-06-14T00:00:00Z",
            "figure_count": 2,
            "mode_used": "rule",
            "evidence_types": {"western_blot": 1, "microscopy": 1},
            "quality_distribution": {"high": 1, "medium": 1, "low": 0},
            "overclaim_summary": {"low": 2, "medium": 0, "high": 0},
            "modes": {"rule": 2},
        }
        cards = [
            {
                "label": "Figure 1",
                "evidence_type": "western_blot",
                "quality_score": 0.85,
                "overclaim_risk": "low",
                "mode": "rule",
                "warnings": [],
            },
            {
                "label": "Figure 2",
                "evidence_type": "microscopy",
                "quality_score": 0.55,
                "overclaim_risk": "low",
                "mode": "rule",
                "warnings": ["No body citation."],
            },
        ]
        quality_reports: list = []

        path = tmp_path / "figure_intelligence_summary.md"
        FigureIntelligenceRunner._write_summary_md(path, summary, cards, quality_reports)

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "paper_test" in content
        assert "Figure 1" in content
        assert "western_blot" in content
        assert "No body citation" in content
