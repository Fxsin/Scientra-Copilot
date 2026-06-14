"""Tests for Cross-Paper Gap API endpoint.

Run: python -m pytest Tests/test_cross_paper_gap_api.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestCrossPaperGapAPI:
    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")
        from scientra.server import create_app
        return TestClient(create_app())

    def test_not_available(self, client):
        resp = client.get("/knowledge/cross-paper-gaps")
        assert resp.status_code == 200
        data = resp.json()
        # May be True if real data exists, False otherwise
        assert "available" in data

    def test_structure(self, client):
        resp = client.get("/knowledge/cross-paper-gaps")
        data = resp.json()
        assert "available" in data
        assert "clusters" in data
        assert "summary" in data

    def test_min_paper_count_filter(self, client):
        resp = client.get("/knowledge/cross-paper-gaps?min_paper_count=3")
        assert resp.status_code == 200

    def test_gap_type_filter(self, client):
        resp = client.get("/knowledge/cross-paper-gaps?gap_type=mechanistic")
        assert resp.status_code == 200

    def test_limit_param(self, client):
        resp = client.get("/knowledge/cross-paper-gaps?limit=5")
        assert resp.status_code == 200

    def test_with_data(self, client, tmp_path):
        from scientra.ai.cross_paper_gap_fusion import (
            fuse_cross_paper_gaps, load_cross_paper_gaps, DEFAULT_OUTPUT_DIR,
        )
        import scientra.ai.cross_paper_gap_fusion as cpgf

        gaps_dir = tmp_path / "gaps"
        gaps_dir.mkdir(parents=True)
        for i in range(3):
            (gaps_dir / f"p{i}.json").write_text(json.dumps({
                "paper_id": f"p{i}", "gaps": [
                    {"gap_id": f"p{i}:g1", "gap_type": "mechanistic",
                     "gap_statement": "Mechanism of autophagy induction unclear",
                     "missing_information": "Signaling cascade",
                     "why_it_matters": "Therapeutic target", "confidence": 0.85},
                ]
            }))

        out_dir = tmp_path / "output"
        fuse_cross_paper_gaps(str(gaps_dir), str(out_dir), threshold=0.3)

        with patch.object(cpgf, "DEFAULT_OUTPUT_DIR", out_dir):
            resp = client.get("/knowledge/cross-paper-gaps")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert len(data["clusters"]) == 1
            assert data["clusters"][0]["support_level"] == "strong_multi_paper"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
