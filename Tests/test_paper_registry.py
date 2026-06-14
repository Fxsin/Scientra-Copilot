"""Tests for paper registry."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scientra.papers.paper_registry import (
    _normalize,
    get_paper_entry,
    load_paper_registry,
)


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Hello World") == "helloworld"

    def test_removes_special_chars(self):
        assert _normalize("test-paper's title.") == "testpaperstitle"

    def test_removes_spaces(self):
        assert _normalize("a b c") == "abc"


class TestRegistryOps:
    def test_load_nonexistent(self, tmp_path):
        with patch("scientra.papers.paper_registry.REGISTRY_PATH", tmp_path / "nonexistent.json"):
            assert load_paper_registry() is None

    def test_get_paper_entry_returns_none_when_no_registry(self, tmp_path):
        with patch("scientra.papers.paper_registry.REGISTRY_PATH", tmp_path / "nonexistent.json"):
            assert get_paper_entry("paper_test") is None


class TestRegistryBuild:
    def test_build_with_metadata(self, tmp_path):
        """Test that build_paper_registry creates a valid registry."""
        import json, yaml

        # Create metadata
        yaml_dir = tmp_path / "yaml"
        yaml_dir.mkdir()
        meta = {
            "key": "Test_Paper_abc123",
            "paper_id": "paper_abc123456789",
            "title": "A Very Important Paper About Bt Toxins",
            "year": 2023,
            "doi": "10.1234/test.2023",
            "journal": "Test Journal",
            "authors": ["Author One"],
        }
        (yaml_dir / "Test_Paper_abc123.metadata.yaml").write_text(
            yaml.dump(meta), encoding="utf-8"
        )

        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()

        reg_path = tmp_path / "paper_registry.json"

        with patch("scientra.papers.paper_registry._get_project_root", return_value=tmp_path), \
             patch("scientra.papers.paper_registry.REGISTRY_PATH", reg_path):
            from scientra.papers.paper_registry import build_paper_registry

            reg = build_paper_registry(
                metadata_dir=str(yaml_dir),
                papers_source_dir=str(papers_dir),
            )
            assert reg["total_papers"] == 1
            assert "paper_abc123456789" in reg["papers"]
            entry = reg["papers"]["paper_abc123456789"]
            assert entry["title"] == "A Very Important Paper About Bt Toxins"
            assert entry["year"] == "2023"
            assert entry["doi"] == "10.1234/test.2023"
            assert "display_name" in entry
            assert "2023" in entry["display_name"]
