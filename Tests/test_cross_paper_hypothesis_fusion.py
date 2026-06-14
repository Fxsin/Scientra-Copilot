"""Tests for Cross-Paper Hypothesis Fusion (Phase 3.2).

Run: python -m pytest Tests/test_cross_paper_hypothesis_fusion.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestHypothesisMap:
    def test_builds_map(self, tmp_path):
        from scientra.ai.cross_paper_hypothesis_fusion import _build_hypothesis_map
        (tmp_path / "p1.json").write_text(json.dumps({
            "paper_id": "p1", "hypotheses": [
                {"hypothesis_id": "p1:h1", "linked_gap_id": "g1",
                 "hypothesis_statement": "If X then Y.", "confidence": 0.8},
                {"hypothesis_id": "p1:h2", "linked_gap_id": "g2",
                 "hypothesis_statement": "If A then B.", "confidence": 0.7},
            ]
        }))
        m = _build_hypothesis_map(str(tmp_path))
        assert len(m) == 2
        assert m["p1:h1"]["linked_gap_id"] == "g1"


class TestHypothesisText:
    def test_builds_text(self):
        from scientra.ai.cross_paper_hypothesis_fusion import _build_hypothesis_text
        hyp = {"hypothesis_statement": "If X then Y.", "rationale": "Because Z.",
               "testable_prediction": "Y increases.", "suggested_experiment": "RNAi + qPCR.",
               "linked_gap_id": "g1"}
        t = _build_hypothesis_text(hyp)
        assert "If X then Y" in t
        assert "Because Z" in t
        assert "RNAi" in t
        assert "g1" in t


class TestRepresentativeSelection:
    def test_selects_best(self):
        from scientra.ai.cross_paper_hypothesis_fusion import _select_representative_hypothesis
        hyps = [
            {"hypothesis_id": "h1", "confidence": 0.5, "risk_level": "high"},
            {"hypothesis_id": "h2", "confidence": 0.9, "risk_level": "low"},
            {"hypothesis_id": "h3", "confidence": 0.8, "risk_level": "medium"},
        ]
        qmap = {"h1": {"weighted_score": 0.5}, "h2": {"weighted_score": 0.9}, "h3": {"weighted_score": 0.7}}
        idx = _select_representative_hypothesis(hyps, qmap)
        assert idx == 1


class TestClusterBuilding:
    def test_builds_cluster(self):
        from scientra.ai.cross_paper_hypothesis_fusion import _build_hypothesis_cluster
        hyps = [
            {"hypothesis_id": "h1", "hypothesis_statement": "If X then Y.", "_paper_id": "p1",
             "linked_gap_id": "g1", "confidence": 0.85, "risk_level": "medium",
             "testable_prediction": "X decreases.", "suggested_experiment": "RNAi.", "supporting_evidence": ["E1"]},
            {"hypothesis_id": "h2", "hypothesis_statement": "If X then Z.", "_paper_id": "p2",
             "linked_gap_id": "g2", "confidence": 0.80, "risk_level": "low",
             "testable_prediction": "X increases.", "suggested_experiment": "Western.", "supporting_evidence": ["E2"]},
        ]
        gap_cluster = {"cluster_id": "gc1", "member_gap_ids": ["g1", "g2"]}
        qmap = {"h1": {"weighted_score": 0.8}, "h2": {"weighted_score": 0.7}}
        texts = ["t1", "t2"]
        emb = np.random.randn(2, 128).astype(np.float32)
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)

        c = _build_hypothesis_cluster(0, hyps, gap_cluster, qmap, [0, 1], texts, emb)
        assert c["paper_count"] == 2
        assert c["support_level"] == "multi_paper"
        assert c["linked_gap_cluster_id"] == "gc1"
        assert "testable_predictions" in c
        assert len(c["suggested_experiments"]) > 0
        rd = c["risk_level_distribution"]
        assert rd["low"] + rd["medium"] + rd["high"] == 2


class TestQualitySummary:
    def test_builds_quality(self):
        from scientra.ai.cross_paper_hypothesis_fusion import _build_quality_summary
        clusters = [
            {"linked_gap_cluster_id": "gc1", "risk_level_distribution": {"low":1,"medium":1,"high":0},
             "overclaim_risk_count": 0, "confidence_mean": 0.85, "testable_predictions": ["P1"],
             "quality_score_mean": 0.8},
            {"linked_gap_cluster_id": "", "risk_level_distribution": {"low":0,"medium":0,"high":1},
             "overclaim_risk_count": 1, "confidence_mean": 0.4, "testable_predictions": [],
             "quality_score_mean": 0.3},
        ]
        q = _build_quality_summary(clusters, [])
        assert q["invalid_gap_cluster_links"] == 1
        assert q["high_risk_hypothesis_count"] == 1
        assert q["low_confidence_cluster_count"] == 1
        assert q["missing_testable_prediction_count"] == 1
        assert q["average_quality_score"] > 0


class TestFusion:
    def test_fuse_with_temp_data(self, tmp_path):
        from scientra.ai.cross_paper_hypothesis_fusion import fuse_cross_paper_hypotheses

        # Gap clusters
        gc_dir = tmp_path / "gc"
        gc_dir.mkdir(parents=True)
        gap_clusters_data = {
            "clusters": [{
                "cluster_id": "gc1", "gap_type": "mechanistic",
                "member_gap_ids": ["p1:g1", "p2:g1"],
                "paper_ids": ["p1", "p2"], "paper_count": 2,
                "confidence_mean": 0.85, "support_level": "multi_paper",
            }]
        }
        gc_path = gc_dir / "gap_clusters.json"
        gc_path.write_text(json.dumps(gap_clusters_data))

        # Hypotheses
        hyp_dir = tmp_path / "hyps"
        hyp_dir.mkdir(parents=True)
        (hyp_dir / "p1.json").write_text(json.dumps({
            "paper_id": "p1", "hypotheses": [
                {"hypothesis_id": "p1:h1", "hypothesis_statement": "If Vip3Aa then autophagy.",
                 "rationale": "Based on TEM evidence.", "linked_gap_id": "p1:g1",
                 "testable_prediction": "Autophagy markers increase.",
                 "suggested_experiment": "RNAi knockdown + TEM.", "risk_level": "medium",
                 "confidence": 0.85, "supporting_evidence": ["E1"], "warnings": []},
            ]
        }))
        (hyp_dir / "p2.json").write_text(json.dumps({
            "paper_id": "p2", "hypotheses": [
                {"hypothesis_id": "p2:h1", "hypothesis_statement": "If Vip3Aa induces autophagy then cell death.",
                 "rationale": "Autophagy linked to death.", "linked_gap_id": "p2:g1",
                 "testable_prediction": "Cell viability decreases.",
                 "suggested_experiment": "MTT assay + TEM.", "risk_level": "medium",
                 "confidence": 0.80, "supporting_evidence": ["E2"], "warnings": []},
            ]
        }))

        out_dir = tmp_path / "out"
        result = fuse_cross_paper_hypotheses(
            gap_clusters_path=str(gc_path),
            hypotheses_dir=str(hyp_dir),
            gaps_dir=str(tmp_path / "gaps"),
            quality_dir=str(tmp_path / "quality"),
            output_dir=str(out_dir),
            threshold=0.6,
        )
        assert result["status"] == "generated"
        assert result["total_hypotheses"] == 2
        assert result["total_hypothesis_clusters"] >= 1

    def test_no_data(self, tmp_path):
        from scientra.ai.cross_paper_hypothesis_fusion import fuse_cross_paper_hypotheses
        r = fuse_cross_paper_hypotheses(
            gap_clusters_path=str(tmp_path / "nonexistent.json"),
            hypotheses_dir=str(tmp_path / "nonexistent"),
            output_dir=str(tmp_path / "out"),
        )
        assert r["status"] == "no_data"

    def test_quality_computed(self, tmp_path):
        from scientra.ai.cross_paper_hypothesis_fusion import fuse_cross_paper_hypotheses

        gc_dir = tmp_path / "gc"
        gc_dir.mkdir(parents=True)
        (gc_dir / "gap_clusters.json").write_text(json.dumps({
            "clusters": [{"cluster_id": "gc1", "member_gap_ids": ["p1:g1"], "paper_ids": ["p1"],
                          "paper_count": 1, "confidence_mean": 0.7, "support_level": "single_paper"}]
        }))
        hyp_dir = tmp_path / "hyps"
        hyp_dir.mkdir(parents=True)
        (hyp_dir / "p1.json").write_text(json.dumps({
            "paper_id": "p1", "hypotheses": [
                {"hypothesis_id": "p1:h1", "hypothesis_statement": "Test.",
                 "rationale": "R.", "linked_gap_id": "p1:g1",
                 "testable_prediction": "T.", "suggested_experiment": "E.",
                 "risk_level": "low", "confidence": 0.9, "supporting_evidence": [], "warnings": []},
            ]
        }))
        out_dir = tmp_path / "out"
        gc_path_abs = str(gc_dir / "gap_clusters.json")
        r = fuse_cross_paper_hypotheses(gc_path_abs, str(hyp_dir), str(tmp_path/"gaps"),
                                        str(tmp_path/"quality"), str(out_dir), threshold=0.5)
        assert "quality" in r
        q = r["quality"]
        assert "recommendation" in q
        assert "average_quality_score" in q


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
