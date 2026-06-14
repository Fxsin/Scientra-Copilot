"""Tests for Research Opportunity Ranking (Phase 3.3)."""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestScoring:
    def test_evidence_score(self):
        from scientra.ai.opportunity_ranking import _score_evidence
        gc = {"paper_count": 30, "member_gap_count": 40, "support_level": "strong_multi_paper", "confidence_mean": 0.9}
        hcs = [{"quality_score_mean": 0.85}]
        s = _score_evidence(gc, hcs)
        assert 0.7 <= s <= 1.0

    def test_evidence_score_low(self):
        from scientra.ai.opportunity_ranking import _score_evidence
        gc = {"paper_count": 1, "member_gap_count": 1, "support_level": "single_paper", "confidence_mean": 0.3}
        s = _score_evidence(gc, [])
        assert s < 0.5

    def test_feasibility_score(self):
        from scientra.ai.opportunity_ranking import _score_feasibility
        gc = {}
        hcs = [{"risk_level_distribution": {"low": 8, "medium": 2, "high": 0},
                "testable_predictions": ["P1"], "suggested_experiments": ["E1"]}]
        s = _score_feasibility(gc, hcs)
        assert s >= 0.7

    def test_novelty_mechanistic(self):
        from scientra.ai.opportunity_ranking import _score_novelty
        gc = {"gap_type": "mechanistic", "paper_count": 10}
        s = _score_novelty(gc, [])
        assert s >= 0.7

    def test_impact_score(self):
        from scientra.ai.opportunity_ranking import _score_impact
        gc = {"paper_count": 20, "support_level": "strong_multi_paper",
              "why_it_matters_merged": "Critical for resistance management" * 3,
              "gap_type": "translation"}
        s = _score_impact(gc, [])
        assert s >= 0.7

    def test_risk_penalty(self):
        from scientra.ai.opportunity_ranking import _score_risk_penalty
        gc = {}
        hcs = [{"risk_level_distribution": {"high": 10, "medium": 0, "low": 0}, "overclaim_risk_count": 3}]
        p = _score_risk_penalty(gc, hcs)
        assert p > 0.3

    def test_risk_penalty_low(self):
        from scientra.ai.opportunity_ranking import _score_risk_penalty
        hcs = [{"risk_level_distribution": {"low": 10, "medium": 0, "high": 0}, "overclaim_risk_count": 0}]
        p = _score_risk_penalty({}, hcs)
        assert p < 0.1


class TestClassification:
    def test_mechanistic_underexplored(self):
        from scientra.ai.opportunity_ranking import _classify_opportunity
        gc = {"gap_type": "mechanistic", "support_level": "strong_multi_paper", "paper_count": 5}
        scores = {"evidence_score": 0.8, "novelty_score": 0.8, "feasibility_score": 0.7, "opportunity_score": 0.75}
        assert _classify_opportunity(gc, [], scores) == "underexplored_mechanism"

    def test_translation_gap(self):
        from scientra.ai.opportunity_ranking import _classify_opportunity
        gc = {"gap_type": "translation", "support_level": "multi_paper", "paper_count": 3}
        assert _classify_opportunity(gc, [], {}) == "translation_gap"

    def test_contradiction(self):
        from scientra.ai.opportunity_ranking import _classify_opportunity
        assert _classify_opportunity({"gap_type": "contradiction"}, [], {}) == "contradiction_to_resolve"

    def test_high_confidence(self):
        from scientra.ai.opportunity_ranking import _classify_opportunity
        gc = {"gap_type": "evidence", "support_level": "multi_paper", "paper_count": 4}
        scores = {"evidence_score": 0.8, "novelty_score": 0.5, "feasibility_score": 0.8, "opportunity_score": 0.75}
        assert _classify_opportunity(gc, [], scores) == "high_confidence_next_step"


class TestRanking:
    def test_ranks_with_temp_data(self, tmp_path):
        from scientra.ai.opportunity_ranking import rank_research_opportunities

        gc_dir = tmp_path / "gc"; gc_dir.mkdir(parents=True)
        (gc_dir / "gap_clusters.json").write_text(json.dumps({
            "clusters": [
                {"cluster_id": "gc1", "gap_type": "mechanistic", "paper_count": 20,
                 "member_gap_count": 30, "support_level": "strong_multi_paper",
                 "confidence_mean": 0.85, "unified_gap_statement": "Mechanism X unknown.",
                 "why_it_matters_merged": "Important for drug development.",
                 "representative_gap": "Gap text.", "paper_ids": ["p1", "p2"]},
                {"cluster_id": "gc2", "gap_type": "scope", "paper_count": 2,
                 "member_gap_count": 2, "support_level": "multi_paper",
                 "confidence_mean": 0.6, "unified_gap_statement": "Scope limited.",
                 "why_it_matters_merged": "Generalizability.", "representative_gap": "Gap2.",
                 "paper_ids": ["p3"]},
            ]
        }))
        hc_dir = tmp_path / "hc"; hc_dir.mkdir(parents=True)
        (hc_dir / "hypothesis_clusters.json").write_text(json.dumps({
            "hypothesis_clusters": [
                {"hypothesis_cluster_id": "h1", "linked_gap_cluster_id": "gc1",
                 "unified_hypothesis_statement": "If X then Y.", "paper_count": 15,
                 "quality_score_mean": 0.85, "testable_predictions": ["P1"],
                 "suggested_experiments": ["E1"],
                 "risk_level_distribution": {"low": 5, "medium": 3, "high": 1},
                 "overclaim_risk_count": 0},
                {"hypothesis_cluster_id": "h2", "linked_gap_cluster_id": "gc2",
                 "unified_hypothesis_statement": "Test more species.",
                 "paper_count": 2, "quality_score_mean": 0.5,
                 "testable_predictions": [], "suggested_experiments": [],
                 "risk_level_distribution": {"low": 0, "medium": 1, "high": 2},
                 "overclaim_risk_count": 2},
            ]
        }))
        out_dir = tmp_path / "out"
        r = rank_research_opportunities(str(gc_dir / "gap_clusters.json"),
                                        str(hc_dir / "hypothesis_clusters.json"),
                                        str(out_dir), top_k=10)
        assert r["status"] == "generated"
        assert r["total_opportunities"] == 2
        opps = r["opportunities"]
        # Mechanistic should rank higher than scope
        assert opps[0]["linked_gap_cluster_id"] == "gc1"
        assert opps[0]["opportunity_score"] > opps[1]["opportunity_score"]
        assert opps[0]["category"] == "underexplored_mechanism"

    def test_top_k(self, tmp_path):
        from scientra.ai.opportunity_ranking import rank_research_opportunities
        gc_dir = tmp_path / "gc"; gc_dir.mkdir(parents=True)
        clusters = []
        for i in range(10):
            clusters.append({"cluster_id": f"gc{i}", "gap_type": "mechanistic",
                           "paper_count": i + 1, "member_gap_count": i + 1,
                           "support_level": "single_paper", "confidence_mean": 0.7,
                           "unified_gap_statement": f"Gap {i}", "why_it_matters_merged": "",
                           "representative_gap": "", "paper_ids": [f"p{i}"]})
        (gc_dir / "gap_clusters.json").write_text(json.dumps({"clusters": clusters}))
        hc_dir = tmp_path / "hc"; hc_dir.mkdir(parents=True)
        (hc_dir / "hypothesis_clusters.json").write_text(json.dumps({"hypothesis_clusters": []}))
        out_dir = tmp_path / "out"
        r = rank_research_opportunities(str(gc_dir / "gap_clusters.json"),
                                        str(hc_dir / "hypothesis_clusters.json"),
                                        str(out_dir), top_k=5)
        assert len(r["opportunities"]) == 5

    def test_min_paper_count(self, tmp_path):
        from scientra.ai.opportunity_ranking import rank_research_opportunities
        gc_dir = tmp_path / "gc"; gc_dir.mkdir(parents=True)
        (gc_dir / "gap_clusters.json").write_text(json.dumps({
            "clusters": [{"cluster_id": "gc1", "gap_type": "mechanistic", "paper_count": 1,
                          "member_gap_count": 1, "support_level": "single_paper",
                          "confidence_mean": 0.7, "unified_gap_statement": "X",
                          "why_it_matters_merged": "", "representative_gap": "", "paper_ids": ["p1"]}]
        }))
        hc_dir = tmp_path / "hc"; hc_dir.mkdir(parents=True)
        (hc_dir / "hypothesis_clusters.json").write_text(json.dumps({"hypothesis_clusters": []}))
        out_dir = tmp_path / "out"
        r = rank_research_opportunities(str(gc_dir / "gap_clusters.json"),
                                        str(hc_dir / "hypothesis_clusters.json"),
                                        str(out_dir), min_paper_count=2)
        assert len(r["opportunities"]) == 0

    def test_summary_generated(self, tmp_path):
        from scientra.ai.opportunity_ranking import rank_research_opportunities
        gc_dir = tmp_path / "gc"; gc_dir.mkdir(parents=True)
        (gc_dir / "gap_clusters.json").write_text(json.dumps({
            "clusters": [{"cluster_id": "gc1", "gap_type": "mechanistic", "paper_count": 10,
                          "member_gap_count": 15, "support_level": "strong_multi_paper",
                          "confidence_mean": 0.85, "unified_gap_statement": "Mech unknown.",
                          "why_it_matters_merged": "Important.", "representative_gap": "G.",
                          "paper_ids": ["p1", "p2"]}]
        }))
        hc_dir = tmp_path / "hc"; hc_dir.mkdir(parents=True)
        (hc_dir / "hypothesis_clusters.json").write_text(json.dumps({"hypothesis_clusters": []}))
        out_dir = tmp_path / "out"
        r = rank_research_opportunities(str(gc_dir / "gap_clusters.json"),
                                        str(hc_dir / "hypothesis_clusters.json"),
                                        str(out_dir), top_k=10)
        s = r["summary"]
        assert "category_distribution" in s
        assert "average_opportunity_score" in s
        assert "scoring_weights" in s

    def test_no_data(self, tmp_path):
        from scientra.ai.opportunity_ranking import rank_research_opportunities
        r = rank_research_opportunities(str(tmp_path / "nonexistent.json"),
                                        str(tmp_path / "nonexistent2.json"),
                                        str(tmp_path / "out"))
        assert r["status"] == "no_data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
