"""Tests for Asset Storage."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scientra.assets.asset_storage import (
    ensure_paper_asset_dirs,
    get_paper_assets_dir,
    register_asset_for_paper,
)


class TestEnsureDirs:
    def test_creates_directories(self, tmp_path):
        with patch("scientra.assets.asset_storage.get_paper_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = ensure_paper_asset_dirs("paper_test")
            assert result == tmp_path
            assert (tmp_path / "assets" / "supplementary").exists()
            assert (tmp_path / "assets" / "tables").exists()
            assert (tmp_path / "assets" / "datasets").exists()
            assert (tmp_path / "assets" / "images").exists()
            assert (tmp_path / "assets" / "archives").exists()
            assert (tmp_path / "links").exists()


class TestGetAssetsDir:
    def test_returns_path(self, tmp_path):
        with patch("scientra.assets.asset_storage.get_paper_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            d = get_paper_assets_dir("paper_test")
            assert d.exists()


class TestRegisterAsset:
    def test_register_csv_as_dataset(self, tmp_path):
        csv_file = tmp_path / "source_data.csv"
        csv_file.write_text("col1,col2\n1,2\n3,4")

        paper_dir = tmp_path / "paper_test"
        paper_dir.mkdir()

        with patch("scientra.assets.asset_storage.get_paper_dir") as mock_paper_dir, \
             patch("scientra.assets.asset_storage.get_registry_path") as mock_reg_path, \
             patch("scientra.assets.asset_storage.load_registry") as mock_load, \
             patch("scientra.assets.asset_storage.save_registry") as mock_save:
            mock_paper_dir.return_value = paper_dir
            mock_reg_path.return_value = paper_dir / "paper_assets.json"
            mock_load.return_value = None  # No existing registry

            asset = register_asset_for_paper(
                paper_id="paper_test",
                file_path=str(csv_file),
                source="manual_upload",
            )

            assert asset.asset_type == "dataset"
            assert asset.status == "registered"
            assert asset.extension == ".csv"
            assert len(asset.sha256) == 64
            # Should have saved registry
            mock_save.assert_called()

    def test_duplicate_detection(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b\n1,2")

        paper_dir = tmp_path / "paper_test"
        paper_dir.mkdir()

        from scientra.assets.types import PaperAssetRegistry

        existing_registry = PaperAssetRegistry(paper_id="paper_test")
        sha = "abc123"
        # Pre-populate with matching sha256
        existing_registry.assets.append({
            "asset_id": "existing_asset",
            "paper_id": "paper_test",
            "sha256": sha,
            "asset_type": "dataset",
            "filename": "existing.csv",
            "relative_path": "assets/datasets/existing.csv",
            "mime_type": "text/csv",
            "status": "registered",
        })

        with patch("scientra.assets.asset_storage.get_paper_dir") as mock_paper_dir, \
             patch("scientra.assets.asset_storage.get_registry_path") as mock_reg_path, \
             patch("scientra.assets.asset_storage.load_registry") as mock_load, \
             patch("scientra.assets.asset_storage.compute_sha256") as mock_sha:
            mock_paper_dir.return_value = paper_dir
            mock_reg_path.return_value = paper_dir / "paper_assets.json"
            mock_load.return_value = existing_registry
            mock_sha.return_value = sha  # Same hash

            asset = register_asset_for_paper(
                paper_id="paper_test",
                file_path=str(csv_file),
                source="manual_upload",
            )

            assert asset.status == "skipped"
            assert "Duplicate" in asset.notes

    def test_register_with_type_override(self, tmp_path):
        pdf_file = tmp_path / "some_file.pdf"
        pdf_file.write_text("pdf content")

        paper_dir = tmp_path / "paper_test"
        paper_dir.mkdir()

        with patch("scientra.assets.asset_storage.get_paper_dir") as mock_paper_dir, \
             patch("scientra.assets.asset_storage.get_registry_path") as mock_reg_path, \
             patch("scientra.assets.asset_storage.load_registry") as mock_load, \
             patch("scientra.assets.asset_storage.save_registry") as mock_save:
            mock_paper_dir.return_value = paper_dir
            mock_reg_path.return_value = paper_dir / "paper_assets.json"
            mock_load.return_value = None

            asset = register_asset_for_paper(
                paper_id="paper_test",
                file_path=str(pdf_file),
                asset_type="supplementary_pdf",
                source="manual_upload",
            )

            assert asset.asset_type == "supplementary_pdf"

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            register_asset_for_paper(
                paper_id="paper_test",
                file_path="/nonexistent/file.pdf",
            )
