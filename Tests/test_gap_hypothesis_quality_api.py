"""Tests for Gap-Hypothesis Quality API endpoint.

Run: python -m pytest Tests/test_gap_hypothesis_quality_api.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestQualityAPI:
    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")
        from scientra.server import create_app
        return TestClient(create_app())

    def test_not_available(self, client):
        resp = client.get("/paper/nonexistent_999/ai-gap-hypothesis-quality")
        assert resp.status_code == 200
        data = resp.json()
        assert data["paper_id"] == "nonexistent_999"
        assert data["available"] is False
        assert "message" in data

    def test_structure(self, client):
        resp = client.get("/paper/test123/ai-gap-hypothesis-quality")
        assert resp.status_code == 200
        data = resp.json()
        assert data["paper_id"] == "test123"
        assert "available" in data

    def test_with_file(self, client, tmp_path):
        import scientra.ai.gap_hypothesis_quality as ghq

        test_data = {
            "paper_id": "existing-q", "status": "evaluated",
            "gap_count": 2, "hypothesis_count": 3,
            "overall_quality_score": 0.75, "recommendation": "accept",
            "gap_scores": [],
            "hypothesis_scores": [],
            "metrics": {"invalid_linked_gap_count": 0, "high_overclaim_risk_count": 0, "safety_ethics_warnings": 0},
            "top_warnings": [],
            "generated_at": "2026-01-01T00:00:00Z",
        }
        out = tmp_path / "quality"
        out.mkdir(parents=True)
        (out / "existing-q.json").write_text(json.dumps(test_data))

        with patch.object(ghq, "OUTPUT_DIR", out):
            resp = client.get("/paper/existing-q/ai-gap-hypothesis-quality")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert data["recommendation"] == "accept"
            assert data["overall_quality_score"] == 0.75
            assert data["metrics"]["invalid_linked_gap_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
