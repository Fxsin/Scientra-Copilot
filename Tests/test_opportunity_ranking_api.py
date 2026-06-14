"""Tests for Research Opportunity Ranking API (Phase 3.3)."""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestOppAPI:
    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")
        from scientra.server import create_app
        return TestClient(create_app())

    def test_not_available(self, client):
        resp = client.get("/knowledge/research-opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "opportunities" in data

    def test_structure(self, client):
        resp = client.get("/knowledge/research-opportunities")
        data = resp.json()
        assert "summary" in data
        assert "opportunities" in data

    def test_filters(self, client):
        for qs in ["?category=underexplored_mechanism", "?min_score=0.5",
                    "?min_paper_count=3", "?risk_level=low", "?limit=10"]:
            resp = client.get(f"/knowledge/research-opportunities{qs}")
            assert resp.status_code == 200

    def test_with_data(self, client, tmp_path):
        from scientra.ai.opportunity_ranking import rank_research_opportunities, load_opportunities, DEFAULT_OUTPUT_DIR
        import scientra.ai.opportunity_ranking as oppr

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
        rank_research_opportunities(str(gc_dir / "gap_clusters.json"),
                                    str(hc_dir / "hypothesis_clusters.json"),
                                    str(out_dir), top_k=10)

        with patch.object(oppr, "DEFAULT_OUTPUT_DIR", str(out_dir)):
            resp = client.get("/knowledge/research-opportunities")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert len(data["opportunities"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
