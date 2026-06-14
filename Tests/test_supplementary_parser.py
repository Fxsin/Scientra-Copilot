"""Tests for Supplementary Parser."""

import tempfile
from pathlib import Path

import pytest
from scientra.assets.supplementary_intelligence.supplementary_parser import parse_supplementary


class TestTxtMd:
    def test_txt(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("Supplementary Methods\n\nWe performed the experiment as described.")
            f.flush()
            r = parse_supplementary(f.name)
        Path(f.name).unlink()
        assert r["parse_status"] == "parsed"
        assert "Supplementary Methods" in r["raw_text"]
        assert r["file_type"] == "txt"

    def test_md(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write("# Methods\n\nDetailed protocol.")
            f.flush()
            r = parse_supplementary(f.name)
        Path(f.name).unlink()
        assert r["parse_status"] == "parsed"

    def test_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("")
            f.flush()
            r = parse_supplementary(f.name)
        Path(f.name).unlink()
        assert r["parse_status"] == "empty"


class TestUnsupported:
    def test_rtf(self):
        r = parse_supplementary("/nonexistent/test.rtf")
        assert r["parse_status"] in ("unsupported", "failed")

    def test_unknown_ext(self):
        r = parse_supplementary("/nonexistent/test.xyz")
        assert r["parse_status"] in ("unsupported", "failed")


class TestStructure:
    def test_keys(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("Test content.")
            f.flush()
            r = parse_supplementary(f.name)
        Path(f.name).unlink()
        for k in ["supplementary_id", "paper_id", "asset_id", "parse_status", "file_type", "raw_text", "text_length", "parse_warnings"]:
            assert k in r
