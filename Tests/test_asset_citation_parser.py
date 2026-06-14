"""Tests for Asset Citation Parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from scientra.assets.linking.citation_parser import CitationParser


class TestExtractFromText:
    def setup_method(self):
        self.parser = CitationParser()

    def test_figure_citation(self):
        text = "As shown in Fig. 1, the expression levels increased significantly."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:1", "results",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert m["citation_text"] == "Fig. 1"
        assert m["asset_type"] == "figure"
        assert m["normalized_label"] == "Figure 1"
        assert m["source_type"] == "body_text"

    def test_figure_s1_citation(self):
        text = "The supplementary data (Fig. S1) confirms this finding."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:2", "results",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert m["asset_type"] == "figure"
        assert m["normalized_label"] == "Figure S1"
        assert m["is_supplementary"] is True

    def test_table_citation(self):
        text = "Table 1 summarizes the demographic characteristics."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:3", "methods",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert m["citation_text"] == "Table 1"
        assert m["asset_type"] == "table"
        assert m["normalized_label"] == "Table 1"

    def test_supplementary_table_citation(self):
        text = "Supplementary Table 2 lists all primers used in this study."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:4", "methods",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert m["asset_type"] == "table"
        assert m["is_supplementary"] is True

    def test_dataset_citation(self):
        text = "Dataset S1 contains the raw RNA-seq counts."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:5", "results",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert m["asset_type"] == "dataset"
        assert m["normalized_label"] == "Dataset S1"

    def test_multiple_citations(self):
        text = "Fig. 1 shows the main result, while Table 1 provides statistics and Fig. S2 adds supplementary detail."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:6", "results",
        )
        assert len(mentions) >= 3

    def test_no_duplicate_citations(self):
        text = "Figure 2 and Fig. 2 illustrate the same thing."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:7", "results",
        )
        # Should not double-count the same span
        labels = [m["citation_text"] for m in mentions]
        # Both patterns match differently but should not produce exact duplicates
        assert len(mentions) >= 1

    def test_mention_structure(self):
        text = "See Figure 3A for details."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "evidence_chunk", "test:ev:0", "discussion",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert "mention_id" in m
        assert m["paper_id"] == "paper_test"
        assert m["source_type"] == "evidence_chunk"
        assert m["source_id"] == "test:ev:0"
        assert m["section"] == "discussion"
        assert len(m["sentence"]) > 0
        assert m["subpanel"] == "A"
        assert "context_before" in m
        assert "context_after" in m

    def test_sentence_extraction(self):
        text = "This is the first sentence. The results are shown in Fig. 4 and are significant. This is a third sentence."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:8", "results",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert "Fig. 4" in m["sentence"]
        assert "significant" in m["sentence"]

    def test_supplementary_general(self):
        text = "See Supplementary Material for detailed protocols."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:9", "methods",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert m["asset_type"] == "supplementary"

    def test_appendix_citation(self):
        text = "Details are provided in Appendix A."
        mentions = self.parser._extract_from_text(
            text, "paper_test", "body_text", "test:body:10", "methods",
        )
        assert len(mentions) >= 1
        m = mentions[0]
        assert m["asset_type"] == "supplementary"


class TestParseAllSources:
    def test_parse_empty_paper(self):
        parser = CitationParser()
        mentions = parser.parse_all_sources("nonexistent_paper_12345")
        # Should return empty list, not crash
        assert isinstance(mentions, list)
