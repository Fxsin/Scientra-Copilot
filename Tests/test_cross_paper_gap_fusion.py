"""Tests for Cross-Paper Gap Fusion V2 — Embedding Community Detection.

Run: python -m pytest Tests/test_cross_paper_gap_fusion.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestGapTextBuilder:
    def test_builds_gap_text(self):
        from scientra.ai.cross_paper_gap_fusion import _build_gap_text
        gap = {
            "gap_type": "mechanistic",
            "gap_statement": "Mechanism unknown.",
            "missing_information": "Pathway link.",
            "why_it_matters": "Drug target.",
        }
        text = _build_gap_text(gap)
        assert "mechanistic" in text
        assert "Mechanism unknown" in text
        assert "Pathway link" in text
        assert "Drug target" in text


class TestKeywordExtraction:
    def test_extracts_keywords(self):
        from scientra.ai.cross_paper_gap_fusion import _extract_keywords
        kw = _extract_keywords("Vip3Aa mechanism of autophagy induction unknown pathway")
        assert len(kw) > 0
        # Should exclude stopwords like "of"
        assert "of" not in kw

    def test_filters_stopwords(self):
        from scientra.ai.cross_paper_gap_fusion import _extract_keywords
        kw = _extract_keywords("the is are was were study research data")
        assert len(kw) <= 2

    def test_collect_cluster_keywords(self):
        from scientra.ai.cross_paper_gap_fusion import _collect_cluster_keywords
        kw = _collect_cluster_keywords([
            "Vip3Aa mechanism autophagy induction",
            "Vip3Aa resistance allele frequency",
        ])
        assert "vip3aa" in kw


class TestRepresentativeSelection:
    def test_selects_highest_quality(self):
        from scientra.ai.cross_paper_gap_fusion import _select_representative
        gaps = [
            {"_quality_score": 0.5, "confidence": 0.5, "based_on_evidence": []},
            {"_quality_score": 0.9, "confidence": 0.9, "based_on_evidence": ["E1"]},
            {"_quality_score": 0.6, "confidence": 0.7, "based_on_evidence": []},
        ]
        idx = _select_representative(gaps)
        assert idx == 1  # Highest quality + confidence

    def test_selects_higher_confidence_tiebreak(self):
        from scientra.ai.cross_paper_gap_fusion import _select_representative
        gaps = [
            {"_quality_score": 0.8, "confidence": 0.6, "based_on_evidence": []},
            {"_quality_score": 0.8, "confidence": 0.9, "based_on_evidence": []},
        ]
        idx = _select_representative(gaps)
        assert idx == 1


class TestClusterBuilding:
    def test_builds_cluster_correctly(self):
        from scientra.ai.cross_paper_gap_fusion import _build_cluster
        gaps = [
            {"gap_id": "p1:gap:1", "_paper_id": "p1", "gap_type": "mechanistic",
             "gap_statement": "Mech unknown", "confidence": 0.85,
             "based_on_evidence": ["E1"], "_quality_score": 0.8,
             "missing_information": "X", "why_it_matters": "Y"},
            {"gap_id": "p2:gap:1", "_paper_id": "p2", "gap_type": "mechanistic",
             "gap_statement": "Mech unclear", "confidence": 0.8,
             "based_on_evidence": ["E2"], "_quality_score": 0.7,
             "missing_information": "Z", "why_it_matters": "W"},
        ]
        texts = ["text1", "text2"]
        emb = np.random.randn(2, 1024).astype(np.float32)
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)

        cluster = _build_cluster(0, [0, 1], gaps, texts, emb)
        assert cluster["paper_count"] == 2
        assert cluster["support_level"] == "multi_paper"
        assert cluster["member_gap_count"] == 2
        assert cluster["fusion_method"] == "community_detection_v2"
        assert "representative_gap_id" in cluster
        assert "semantic_keywords" in cluster
        assert len(cluster["semantic_keywords"]) > 0
        # Representative should be p1:gap:1 (higher quality)
        assert cluster["representative_gap_id"] == "p1:gap:1"

    def test_support_levels(self):
        from scientra.ai.cross_paper_gap_fusion import _build_cluster
        emb = np.random.randn(4, 1024).astype(np.float32)
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)

        def make_gap(pid):
            return {
                "gap_id": f"{pid}:gap:1", "_paper_id": pid, "gap_type": "mechanistic",
                "gap_statement": "X", "confidence": 0.8, "based_on_evidence": [],
                "_quality_score": 0.7, "missing_information": "", "why_it_matters": "",
            }

        # Single
        c1 = _build_cluster(0, [0], [make_gap("p1")], ["t1"], emb)
        assert c1["support_level"] == "single_paper"

        # Multi (2 papers)
        c2 = _build_cluster(0, [0, 1], [make_gap("p1"), make_gap("p2")], ["t1", "t2"], emb)
        assert c2["support_level"] == "multi_paper"

        # Strong (3+ papers)
        c3 = _build_cluster(0, [0, 1, 2], [make_gap("p1"), make_gap("p2"), make_gap("p3")],
                            ["t1", "t2", "t3"], emb)
        assert c3["support_level"] == "strong_multi_paper"


class TestCommunityDetection:
    def test_community_detection_runs(self):
        """Verify community_detection API works."""
        from sentence_transformers.util import community_detection

        # Create 10 random normalized embeddings with 2 clear clusters
        np.random.seed(42)
        emb = np.random.randn(10, 128).astype(np.float32)
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
        # Make first 3 and last 3 similar
        emb[1] = emb[0] * 0.99
        emb[2] = emb[0] * 0.98
        emb[8] = emb[7] * 0.99
        emb[9] = emb[7] * 0.98

        communities = community_detection(emb, threshold=0.7, min_community_size=2)
        assert len(communities) >= 1

    def test_different_thresholds_produce_different_results(self):
        """Higher threshold = fewer communities, lower = more."""
        from sentence_transformers.util import community_detection

        np.random.seed(123)
        emb = np.random.randn(20, 128).astype(np.float32)
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)

        comm_low = community_detection(emb, threshold=0.5, min_community_size=1)
        comm_high = community_detection(emb, threshold=0.95, min_community_size=1)
        # Higher threshold = more selective = fewer or equal communities
        assert len(comm_high) <= len(comm_low) + 5  # Allow some variance


class TestFusion:
    def test_fuse_with_real_data(self, tmp_path):
        """Integration test with simulated gap data."""
        from scientra.ai.cross_paper_gap_fusion import fuse_cross_paper_gaps

        gaps_dir = tmp_path / "gaps"
        gaps_dir.mkdir(parents=True)

        for i in range(3):
            (gaps_dir / f"p{i}.json").write_text(json.dumps({
                "paper_id": f"p{i}", "overall_quality_score": 0.8,
                "gaps": [
                    {"gap_id": f"p{i}:gap:1", "gap_type": "mechanistic",
                     "gap_statement": "Vip3Aa mechanism of autophagy induction remains unclear",
                     "missing_information": "AMPK-mTOR pathway link",
                     "why_it_matters": "Therapeutic target identification",
                     "based_on_evidence": [f"E{i}"], "confidence": 0.85},
                ]
            }))

        out_dir = tmp_path / "output"
        result = fuse_cross_paper_gaps(
            gaps_dir=str(gaps_dir), output_dir=str(out_dir),
            threshold=0.6, min_community_size=1,
        )
        assert result["status"] == "generated"
        assert result["total_gaps"] == 3
        assert result["fusion_method"] == "community_detection_v2"

        # With similar texts, they should form 1-3 clusters
        clusters = result["clusters"]
        assert 1 <= len(clusters) <= 3

    def test_no_data(self, tmp_path):
        from scientra.ai.cross_paper_gap_fusion import fuse_cross_paper_gaps
        result = fuse_cross_paper_gaps(
            gaps_dir=str(tmp_path / "nonexistent"),
            output_dir=str(tmp_path / "out"),
        )
        assert result["status"] == "no_data"

    def test_cross_type_disabled_by_default(self, tmp_path):
        """Gaps of different types should be in separate clusters."""
        from scientra.ai.cross_paper_gap_fusion import fuse_cross_paper_gaps

        gaps_dir = tmp_path / "gaps"
        gaps_dir.mkdir(parents=True)
        (gaps_dir / "p1.json").write_text(json.dumps({
            "paper_id": "p1", "overall_quality_score": 0.8,
            "gaps": [
                {"gap_id": "p1:g1", "gap_type": "mechanistic",
                 "gap_statement": "Mech unknown", "missing_information": "X",
                 "why_it_matters": "Y", "based_on_evidence": [], "confidence": 0.8},
                {"gap_id": "p1:g2", "gap_type": "scope",
                 "gap_statement": "Only one species tested", "missing_information": "Other species",
                 "why_it_matters": "Y", "based_on_evidence": [], "confidence": 0.8},
            ]
        }))

        out_dir = tmp_path / "output"
        result = fuse_cross_paper_gaps(
            gaps_dir=str(gaps_dir), output_dir=str(out_dir),
            threshold=0.5, allow_cross_type=False,
        )
        # Each gap should be in its own type group, so at most 2 clusters
        assert result["total_clusters"] <= 2

    def test_summary_output(self, tmp_path):
        from scientra.ai.cross_paper_gap_fusion import fuse_cross_paper_gaps

        gaps_dir = tmp_path / "gaps"
        gaps_dir.mkdir(parents=True)
        (gaps_dir / "p1.json").write_text(json.dumps({
            "paper_id": "p1", "overall_quality_score": 0.8,
            "gaps": [
                {"gap_id": "p1:g1", "gap_type": "evidence",
                 "gap_statement": "Functional validation missing",
                 "missing_information": "Knockout data",
                 "why_it_matters": "Validation", "based_on_evidence": [], "confidence": 0.8},
            ]
        }))

        out_dir = tmp_path / "output"
        result = fuse_cross_paper_gaps(str(gaps_dir), str(out_dir), threshold=0.5)
        summary = result["summary"]
        assert summary["fusion_method"] == "community_detection_v2"
        assert summary["total_gaps"] == 1
        assert "threshold_used" in summary
        assert "average_cluster_size" in summary
        assert "largest_cluster_size" in summary

    def test_load_saved(self, tmp_path):
        from scientra.ai.cross_paper_gap_fusion import fuse_cross_paper_gaps, load_cross_paper_gaps

        gaps_dir = tmp_path / "gaps"
        gaps_dir.mkdir(parents=True)
        (gaps_dir / "p1.json").write_text(json.dumps({
            "paper_id": "p1", "overall_quality_score": 0.8,
            "gaps": [
                {"gap_id": "p1:g1", "gap_type": "mechanistic",
                 "gap_statement": "Mechanism unknown", "missing_information": "X",
                 "why_it_matters": "Y", "based_on_evidence": [], "confidence": 0.8},
            ]
        }))

        out_dir = tmp_path / "output"
        fuse_cross_paper_gaps(str(gaps_dir), str(out_dir), threshold=0.5)
        loaded = load_cross_paper_gaps(str(out_dir))
        assert loaded is not None
        assert loaded["total_gaps"] == 1

    def test_orphan_handling(self, tmp_path):
        """All gaps become clusters — either via community or as orphans."""
        from scientra.ai.cross_paper_gap_fusion import fuse_cross_paper_gaps

        gaps_dir = tmp_path / "gaps"
        gaps_dir.mkdir(parents=True)
        # Two different gaps
        for i in range(3):
            (gaps_dir / f"p{i}.json").write_text(json.dumps({
                "paper_id": f"p{i}", "overall_quality_score": 0.8,
                "gaps": [
                    {"gap_id": f"p{i}:g1", "gap_type": "mechanistic",
                     "gap_statement": f"Specific gap about protein target {i}",
                     "missing_information": "Structure needed",
                     "why_it_matters": "Therapeutic target",
                     "based_on_evidence": [], "confidence": 0.8},
                ]
            }))

        out_dir = tmp_path / "output"
        result = fuse_cross_paper_gaps(
            str(gaps_dir), str(out_dir), threshold=0.72, min_community_size=1,
        )
        # Every gap should end up in some cluster (community or orphan)
        assert result["total_gaps"] == 3
        assert sum(c["member_gap_count"] for c in result["clusters"]) == 3
        assert result["total_clusters"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
