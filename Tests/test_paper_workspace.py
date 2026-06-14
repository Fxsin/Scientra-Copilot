"""Tests for paper workspace naming and migration."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scientra.papers.paper_workspace import (
    make_safe_display_name,
    resolve_workspace_dir,
)


class TestSafeDisplayName:
    def test_basic_format(self):
        name = make_safe_display_name("Transgenic cotton coexpressing Vip3A and Cry1Ac", "2023")
        assert name.startswith("2023_")
        assert "Transgenic" in name
        assert "cotton" in name.lower()

    def test_unsafe_characters_removed(self):
        name = make_safe_display_name("Test: paper <title> with \"quotes\"", "2020")
        assert ":" not in name
        assert "<" not in name
        assert ">" not in name
        assert '"' not in name

    def test_spaces_to_underscores(self):
        name = make_safe_display_name("Hello World Paper", "2021")
        assert " " not in name
        assert "Hello_World" in name or "Hello_World_Paper" in name

    def test_multi_underscore_collapse(self):
        name = make_safe_display_name("Test --- paper   title", "2022")
        assert "__" not in name

    def test_max_length_enforced(self):
        long_title = "A very long paper title " * 10
        name = make_safe_display_name(long_title, "2023", max_length=80)
        assert len(name) <= 80

    def test_empty_title_fallback(self):
        name = make_safe_display_name("", "2024")
        assert "Untitled" in name
        assert name.startswith("2024_")

    def test_none_title_fallback(self):
        name = make_safe_display_name(None, "2025")  # type: ignore
        assert "Untitled" in name

    def test_no_year(self):
        name = make_safe_display_name("Some Paper Title", None)
        assert name.startswith("NoYear_")

    def test_special_chars_stripped(self):
        name = make_safe_display_name("Test (paper) [with] special; chars.", "2020")
        assert "(" not in name
        assert ")" not in name
        assert "[" not in name
        assert ";" not in name


class TestResolveWorkspaceDir:
    def test_legacy_fallback(self, tmp_path):
        paper_id = "paper_test123"
        legacy_dir = tmp_path / paper_id
        legacy_dir.mkdir()

        with patch("scientra.papers.paper_workspace._PAPERS_DIR", tmp_path), \
             patch("scientra.papers.paper_workspace._get_project_root", return_value=tmp_path), \
             patch("scientra.papers.paper_registry.load_paper_registry", return_value=None):
            result = resolve_workspace_dir(paper_id)
            assert result == legacy_dir

    def test_registry_resolution(self, tmp_path):
        paper_id = "paper_test456"
        display_dir = tmp_path / "2020_My_Paper"
        display_dir.mkdir()

        reg = {
            "papers": {
                paper_id: {
                    "paper_id": paper_id,
                    "source_dir": "2020_My_Paper",
                    "title": "My Paper",
                    "year": "2020",
                }
            }
        }

        with patch("scientra.papers.paper_workspace._get_project_root", return_value=tmp_path), \
             patch("scientra.papers.paper_registry.load_paper_registry", return_value=reg):
            result = resolve_workspace_dir(paper_id)
            assert result == display_dir

    def test_new_paper_creates_legacy(self, tmp_path):
        """When neither registry nor legacy exists, creates legacy path."""
        paper_id = "paper_new789"

        with patch("scientra.papers.paper_workspace._PAPERS_DIR", tmp_path), \
             patch("scientra.papers.paper_workspace._get_project_root", return_value=tmp_path), \
             patch("scientra.papers.paper_registry.load_paper_registry", return_value=None):
            result = resolve_workspace_dir(paper_id)
            assert result.exists()
            assert result.name == paper_id
