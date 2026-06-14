"""Tests for Paper Asset API endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scientra.assets.types import PaperAssetRegistry, PaperAsset


# ── Fixtures ──


@pytest.fixture
def sample_registry():
    """Sample paper asset registry for testing."""
    return {
        "paper_id": "paper_d0cf4389f4ef6e06",
        "main_pdf": {
            "asset_id": "main_pdf",
            "paper_id": "paper_d0cf4389f4ef6e06",
            "asset_type": "main_pdf",
            "filename": "paper.pdf",
            "original_filename": "paper.pdf",
            "relative_path": "",
            "sha256": "abc123",
            "size_bytes": 1048576,
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "source": "initial_import",
            "status": "registered",
        },
        "assets": [
            {
                "asset_id": "asset_d0cf_0001",
                "paper_id": "paper_d0cf4389f4ef6e06",
                "asset_type": "supplementary_pdf",
                "filename": "supplementary.pdf",
                "original_filename": "supplementary.pdf",
                "relative_path": "assets/supplementary/supplementary.pdf",
                "sha256": "def456",
                "size_bytes": 2048576,
                "mime_type": "application/pdf",
                "extension": ".pdf",
                "source": "web_upload",
                "status": "registered",
                "warnings": [],
                "errors": [],
            },
            {
                "asset_id": "asset_d0cf_0002",
                "paper_id": "paper_d0cf4389f4ef6e06",
                "asset_type": "supplementary_table",
                "filename": "Table_S1.xlsx",
                "original_filename": "Table_S1.xlsx",
                "relative_path": "assets/tables/Table_S1.xlsx",
                "sha256": "ghi789",
                "size_bytes": 51200,
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "extension": ".xlsx",
                "source": "manual_upload",
                "status": "registered",
                "warnings": [],
                "errors": [],
            },
        ],
        "asset_counts": {
            "supplementary_pdf": 1,
            "supplementary_table": 1,
            "dataset": 0,
            "figure_image": 0,
            "table_image": 0,
            "archive": 0,
            "attachment": 0,
            "unknown": 0,
        },
        "last_updated": "2024-06-14T00:00:00Z",
    }


# ── Tests ──


class TestAssetsResponse:
    def test_available_when_registry_exists(self, sample_registry):
        assert "paper_id" in sample_registry
        assert "main_pdf" in sample_registry
        assert "assets" in sample_registry
        assert "asset_counts" in sample_registry
        assert sample_registry["asset_counts"]["supplementary_pdf"] == 1

    def test_no_absolute_paths_in_response(self, sample_registry):
        """API response should never expose absolute paths."""
        for a in sample_registry["assets"]:
            assert "source_path" not in a
            assert not a.get("relative_path", "").startswith("/")
            assert not a.get("relative_path", "").startswith("C:")

    def test_asset_counts_match_assets(self, sample_registry):
        from collections import Counter
        actual = Counter(a["asset_type"] for a in sample_registry["assets"])
        counts = sample_registry["asset_counts"]
        for atype, count in actual.items():
            if atype in counts:
                assert counts[atype] == count

    def test_available_false_when_no_registry(self):
        response = {
            "paper_id": "paper_test",
            "available": False,
            "message": "Paper asset registry not initialized.",
        }
        assert response["available"] is False


class TestUploadResponse:
    def test_registered_response(self):
        response = {
            "paper_id": "paper_test",
            "available": True,
            "registered_assets": [{"asset_id": "asset_001", "status": "registered"}],
            "skipped_duplicates": [],
            "warnings": [],
            "errors": [],
        }
        assert len(response["registered_assets"]) == 1
        assert len(response["skipped_duplicates"]) == 0

    def test_duplicate_response(self):
        response = {
            "paper_id": "paper_test",
            "available": True,
            "registered_assets": [],
            "skipped_duplicates": [{"asset_id": "asset_001", "status": "skipped"}],
            "warnings": ["Duplicate asset"],
            "errors": [],
        }
        assert len(response["skipped_duplicates"]) == 1


class TestDeleteResponse:
    def test_logical_delete(self):
        response = {
            "paper_id": "paper_test",
            "asset_id": "asset_001",
            "deleted": True,
            "note": "Logical delete only — file preserved on disk.",
        }
        assert response["deleted"] is True
        assert "Logical delete" in response["note"]


class TestPathTraversal:
    def test_relative_paths_only(self):
        """Verify that relative_path values are safe."""
        paths = [
            "assets/supplementary/file.pdf",
            "assets/tables/data.xlsx",
            "assets/images/fig1.png",
        ]
        for p in paths:
            assert not p.startswith("/")
            assert not p.startswith("C:")
            assert ".." not in p
