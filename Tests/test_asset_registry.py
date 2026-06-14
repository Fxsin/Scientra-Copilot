"""Tests for Asset Registry."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scientra.assets.asset_registry import (
    compute_sha256,
    _safe_filename,
    _generate_asset_id,
    load_registry,
    save_registry,
    find_asset_by_sha256,
    init_registry_for_paper,
)
from scientra.assets.types import PaperAssetRegistry, PaperAsset


class TestSHA256:
    def test_compute_hash(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = compute_sha256(str(f))
        assert len(h) == 64
        assert h == compute_sha256(str(f))  # deterministic

    def test_different_files(self, tmp_path):
        f1 = tmp_path / "a.txt"; f1.write_text("hello")
        f2 = tmp_path / "b.txt"; f2.write_text("world")
        assert compute_sha256(str(f1)) != compute_sha256(str(f2))


class TestSafeFilename:
    def test_removes_unsafe_chars(self):
        assert ":" not in _safe_filename("file:name.pdf")
        assert "<" not in _safe_filename("a<b.txt")

    def test_truncates_long_names(self):
        long_name = "a" * 200 + ".pdf"
        result = _safe_filename(long_name)
        assert len(result) <= 125


class TestAssetID:
    def test_generates_predictable_id(self):
        aid = _generate_asset_id("paper_d0cf4389f4ef6e06", 0)
        assert aid.startswith("asset_")
        assert "0000" in aid


class TestRegistrySaveLoad:
    def test_save_and_load(self, tmp_path):
        registry = PaperAssetRegistry(
            paper_id="paper_test",
            main_pdf={"asset_id": "main_pdf", "asset_type": "main_pdf"},
            assets=[],
            last_updated="2024-01-01T00:00:00Z",
        )

        with patch("scientra.assets.asset_registry.get_registry_path") as mock_path:
            mock_path.return_value = tmp_path / "paper_assets.json"
            save_registry(registry)
            assert (tmp_path / "paper_assets.json").exists()

            loaded = load_registry("paper_test")
            assert loaded is not None
            assert loaded.paper_id == "paper_test"
            assert loaded.main_pdf["asset_type"] == "main_pdf"

    def test_load_nonexistent(self):
        with patch("scientra.assets.asset_registry.get_registry_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/paper_assets.json")
            assert load_registry("paper_test") is None


class TestFindBySHA256:
    def test_finds_in_assets(self):
        registry = PaperAssetRegistry(paper_id="paper_test")
        registry.assets.append({"asset_id": "a1", "sha256": "abc123"})
        result = find_asset_by_sha256(registry, "abc123")
        assert result is not None
        assert result["asset_id"] == "a1"

    def test_finds_in_main_pdf(self):
        registry = PaperAssetRegistry(
            paper_id="paper_test",
            main_pdf={"asset_id": "main_pdf", "sha256": "def456"},
        )
        result = find_asset_by_sha256(registry, "def456")
        assert result is not None

    def test_not_found(self):
        registry = PaperAssetRegistry(paper_id="paper_test")
        assert find_asset_by_sha256(registry, "nonexistent") is None


class TestInitRegistry:
    def test_creates_new_registry_without_pdf(self, tmp_path):
        with patch("scientra.assets.asset_registry.get_paper_dir") as mock_dir, \
             patch("scientra.assets.asset_registry.get_registry_path") as mock_path:
            mock_dir.return_value = tmp_path
            mock_path.return_value = tmp_path / "paper_assets.json"

            registry = init_registry_for_paper("paper_test", main_pdf_source=None)
            assert registry.paper_id == "paper_test"
            assert registry.main_pdf is None
            assert (tmp_path / "paper_assets.json").exists()

    def test_creates_with_main_pdf(self, tmp_path):
        pdf = tmp_path / "main.pdf"
        pdf.write_text("test pdf content")

        with patch("scientra.assets.asset_registry.get_paper_dir") as mock_dir, \
             patch("scientra.assets.asset_registry.get_registry_path") as mock_path:
            mock_dir.return_value = tmp_path
            mock_path.return_value = tmp_path / "paper_assets.json"

            registry = init_registry_for_paper("paper_test", main_pdf_source=str(pdf))
            assert registry.main_pdf is not None
            assert registry.main_pdf["asset_type"] == "main_pdf"
