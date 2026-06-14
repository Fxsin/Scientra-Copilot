"""Tests for Gap & Hypothesis API endpoints.

Run: python -m pytest Tests/test_gap_hypothesis_api.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestGapHypothesisAPI:
    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")
        from scientra.server import create_app
        return TestClient(create_app())

    def test_gaps_not_available(self, client):
        resp = client.get("/paper/nonexistent_999/ai-gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["paper_id"] == "nonexistent_999"
        assert data["available"] is False
        assert "message" in data

    def test_hypotheses_not_available(self, client):
        resp = client.get("/paper/nonexistent_999/ai-hypotheses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["paper_id"] == "nonexistent_999"
        assert data["available"] is False
        assert "message" in data

    def test_gaps_structure(self, client):
        resp = client.get("/paper/test123/ai-gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["paper_id"] == "test123"
        assert "available" in data

    def test_hypotheses_structure(self, client):
        resp = client.get("/paper/test123/ai-hypotheses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["paper_id"] == "test123"
        assert "available" in data

    def test_gaps_with_file(self, client, tmp_path):
        import scientra.ai.gap_extraction as ge

        test_data = {"paper_id": "existing-gap", "gaps": [
            {"gap_id": "existing-gap:gap:0001", "gap_statement": "Test gap", "gap_type": "mechanistic",
             "based_on_evidence": [], "missing_information": "", "why_it_matters": "",
             "confidence": 0.8, "warnings": []}
        ], "status": "generated"}

        out = tmp_path / "gaps"
        out.mkdir(parents=True)
        (out / "existing-gap.json").write_text(json.dumps(test_data))

        with patch.object(ge, "OUTPUT_DIR", out):
            resp = client.get("/paper/existing-gap/ai-gaps")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert len(data["gaps"]) == 1
            assert data["gaps"][0]["gap_type"] == "mechanistic"

    def test_hypotheses_with_file(self, client, tmp_path):
        import scientra.ai.hypothesis_generation as hg

        test_data = {"paper_id": "existing-hyp", "hypotheses": [
            {"hypothesis_id": "existing-hyp:hyp:0001", "hypothesis_statement": "If X then Y",
             "rationale": "Because", "linked_gap_id": "g1", "supporting_evidence": [],
             "testable_prediction": "Y goes up", "suggested_experiment": "RNA-seq",
             "risk_level": "medium", "confidence": 0.8, "warnings": []}
        ], "status": "generated"}

        out = tmp_path / "hyps"
        out.mkdir(parents=True)
        (out / "existing-hyp.json").write_text(json.dumps(test_data))

        with patch.object(hg, "OUTPUT_DIR", out):
            resp = client.get("/paper/existing-hyp/ai-hypotheses")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert len(data["hypotheses"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
