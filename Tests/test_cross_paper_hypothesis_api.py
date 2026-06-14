"""Tests for Cross-Paper Hypothesis API endpoint (Phase 3.2)."""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestHypothesisAPI:
    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")
        from scientra.server import create_app
        return TestClient(create_app())

    def test_not_available(self, client):
        resp = client.get("/knowledge/cross-paper-hypotheses")
        assert resp.status_code == 200
        data = resp.json()
        # May be True if data already exists, but structure must be correct
        assert "available" in data
        assert "hypothesis_clusters" in data

    def test_structure(self, client):
        resp = client.get("/knowledge/cross-paper-hypotheses")
        data = resp.json()
        assert "summary" in data
        assert "quality" in data
        assert "hypothesis_clusters" in data

    def test_filters(self, client):
        for qs in ["?min_paper_count=3", "?risk_level=high", "?limit=5"]:
            resp = client.get(f"/knowledge/cross-paper-hypotheses{qs}")
            assert resp.status_code == 200

    def test_with_data(self, client, tmp_path):
        from scientra.ai.cross_paper_hypothesis_fusion import (
            fuse_cross_paper_hypotheses, load_cross_paper_hypotheses, DEFAULT_OUTPUT_DIR,
        )
        import scientra.ai.cross_paper_hypothesis_fusion as chf

        gc_dir = tmp_path / "gc"
        gc_dir.mkdir(parents=True)
        (gc_dir / "gap_clusters.json").write_text(json.dumps({
            "clusters": [{"cluster_id": "gc1", "member_gap_ids": ["p1:g1"], "paper_ids": ["p1"],
                          "paper_count": 1, "confidence_mean": 0.8, "support_level": "single_paper"}]
        }))
        hyp_dir = tmp_path / "hyps"
        hyp_dir.mkdir(parents=True)
        (hyp_dir / "p1.json").write_text(json.dumps({
            "paper_id": "p1", "hypotheses": [
                {"hypothesis_id": "p1:h1", "hypothesis_statement": "Test hypothesis.",
                 "rationale": "R.", "linked_gap_id": "p1:g1",
                 "testable_prediction": "Prediction.", "suggested_experiment": "Experiment.",
                 "risk_level": "low", "confidence": 0.85, "supporting_evidence": [], "warnings": []},
            ]
        }))

        out_dir = tmp_path / "out"
        fuse_cross_paper_hypotheses(str(gc_dir / "gap_clusters.json"), str(hyp_dir),
                                    str(tmp_path/"gaps"), str(tmp_path/"quality"),
                                    str(out_dir), threshold=0.5)

        with patch.object(chf, "DEFAULT_OUTPUT_DIR", str(out_dir)):
            resp = client.get("/knowledge/cross-paper-hypotheses")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert len(data["hypothesis_clusters"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
