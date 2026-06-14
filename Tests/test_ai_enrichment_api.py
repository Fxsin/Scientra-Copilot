"""Tests for AI Enrichment API endpoints.

Run:
    python -m pytest Tests/test_ai_enrichment_api.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAIEnrichmentAPI:
    """Test the AI enrichment API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")

        from scientra.server import create_app

        app = create_app()
        return TestClient(app)

    def test_ai_summary_v2_not_available(self, client):
        """GET /paper/{id}/ai-summary-v2 returns available=false when not generated."""
        response = client.get("/paper/nonexistent_paper_99999/ai-summary-v2")
        assert response.status_code == 200
        data = response.json()
        assert "paper_id" in data
        assert data["available"] is False

    def test_evidence_enrichment_not_available(self, client):
        """GET /paper/{id}/evidence-enrichment returns available=false when not generated."""
        response = client.get("/paper/nonexistent_paper_99999/evidence-enrichment")
        assert response.status_code == 200
        data = response.json()
        assert "paper_id" in data
        assert data["available"] is False

    def test_ai_summary_v2_returns_structure(self, client):
        """Response has correct structure even when unavailable."""
        response = client.get("/paper/test123/ai-summary-v2")
        assert response.status_code == 200
        data = response.json()
        assert data["paper_id"] == "test123"
        assert "available" in data
        assert "message" in data

    def test_evidence_enrichment_returns_structure(self, client):
        """Response has correct structure even when unavailable."""
        response = client.get("/paper/test123/evidence-enrichment")
        assert response.status_code == 200
        data = response.json()
        assert data["paper_id"] == "test123"
        assert "available" in data
        assert "message" in data

    def test_ai_summary_v2_with_existing_file(self, client, tmp_path):
        """Returns data when summary V2 file exists."""
        import scientra.ai.summary_v2 as sv2

        test_data = {
            "paper_id": "existing-test",
            "status": "generated",
            "core_finding": "Test finding",
            "confidence": 0.9,
            "method_summary": ["Method 1"],
            "key_evidence": [],
            "main_claims": [],
            "limitations": [],
            "future_directions": [],
            "important_entities": [],
            "warnings": [],
            "generated_at": "2026-01-01T00:00:00Z",
        }

        output_dir = tmp_path / "summary_v2"
        output_dir.mkdir(parents=True)
        (output_dir / "existing-test.json").write_text(
            json.dumps(test_data, ensure_ascii=False)
        )

        with patch.object(sv2, "OUTPUT_DIR", output_dir):
            response = client.get("/paper/existing-test/ai-summary-v2")
            assert response.status_code == 200
            data = response.json()
            assert data["available"] is True
            assert data["core_finding"] == "Test finding"
            assert data["confidence"] == 0.9

    def test_evidence_enrichment_with_existing_file(self, client, tmp_path):
        """Returns data when enrichment file exists."""
        import scientra.ai.evidence_enrichment as ee

        test_data = {
            "paper_id": "existing-ee",
            "status": "enriched",
            "chunks": [
                {"chunk_id": "C1", "ai_claim": "Test claim", "evidence_strength": "strong"}
            ],
            "enriched_chunks": 1,
            "generated_at": "2026-01-01T00:00:00Z",
        }

        output_dir = tmp_path / "enrichment"
        output_dir.mkdir(parents=True)
        (output_dir / "existing-ee.json").write_text(
            json.dumps(test_data, ensure_ascii=False)
        )

        with patch.object(ee, "OUTPUT_DIR", output_dir):
            response = client.get("/paper/existing-ee/evidence-enrichment")
            assert response.status_code == 200
            data = response.json()
            assert data["available"] is True
            assert len(data["chunks"]) == 1
            assert data["chunks"][0]["ai_claim"] == "Test claim"


class TestAIEnrichmentAPISpecialCases:
    """Test edge cases."""

    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")
        from scientra.server import create_app
        return TestClient(create_app())

    def test_ai_summary_v2_with_hyphens(self, client):
        """Paper IDs with hyphens and underscores work fine."""
        response = client.get("/paper/test-paper_with-hyphens_123/ai-summary-v2")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False

    def test_evidence_enrichment_with_hyphens(self, client):
        """Paper IDs with hyphens and underscores work fine."""
        response = client.get("/paper/test-paper_with-hyphens_123/evidence-enrichment")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
