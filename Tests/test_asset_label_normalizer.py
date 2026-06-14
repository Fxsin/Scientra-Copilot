"""Tests for Asset Label Normalizer."""

from __future__ import annotations

import pytest
from scientra.assets.linking.label_normalizer import (
    normalize_label,
    make_search_variants,
    _parse_number_part,
)


class TestNormalizeFigure:
    def test_fig_1(self):
        result = normalize_label("Fig. 1")
        assert result["normalized_label"] == "Figure 1"
        assert result["asset_type"] == "figure"
        assert result["subpanel"] == ""

    def test_figure_1(self):
        result = normalize_label("Figure 1")
        assert result["normalized_label"] == "Figure 1"
        assert result["asset_type"] == "figure"

    def test_fig_1a(self):
        result = normalize_label("Fig. 1A")
        assert result["normalized_label"] == "Figure 1"
        assert result["asset_type"] == "figure"
        assert result["subpanel"] == "A"

    def test_figure_s1(self):
        result = normalize_label("Figure S1")
        assert result["normalized_label"] == "Figure S1"
        assert result["asset_type"] == "figure"
        assert result["is_supplementary"] is True

    def test_fig_s2(self):
        result = normalize_label("Fig. S2")
        assert result["normalized_label"] == "Figure S2"
        assert result["asset_type"] == "figure"
        assert result["is_supplementary"] is True

    def test_supplementary_fig_s3(self):
        result = normalize_label("Supplementary Fig. S3")
        assert result["normalized_label"] == "Figure S3"
        assert result["asset_type"] == "figure"
        assert result["is_supplementary"] is True

    def test_supplementary_fig_1_no_s_prefix(self):
        """Supplementary Fig. 1 -> Figure S1"""
        result = normalize_label("Supplementary Fig. 1")
        assert result["normalized_label"] == "Figure S1"
        assert result["asset_type"] == "figure"
        assert result["is_supplementary"] is True

    def test_fig_case_insensitive(self):
        result = normalize_label("fig. 5")
        assert result["normalized_label"] == "Figure 5"
        assert result["asset_type"] == "figure"

    def test_figs_multiple(self):
        result = normalize_label("Figs. 1 and 2")
        assert result["asset_type"] == "figure"


class TestNormalizeTable:
    def test_table_1(self):
        result = normalize_label("Table 1")
        assert result["normalized_label"] == "Table 1"
        assert result["asset_type"] == "table"

    def test_table_s1(self):
        result = normalize_label("Table S1")
        assert result["normalized_label"] == "Table S1"
        assert result["asset_type"] == "table"
        assert result["is_supplementary"] is True

    def test_supplementary_table_2(self):
        result = normalize_label("Supplementary Table 2")
        assert result["normalized_label"] == "Table S2"
        assert result["asset_type"] == "table"
        assert result["is_supplementary"] is True


class TestNormalizeDataset:
    def test_dataset_s1(self):
        result = normalize_label("Dataset S1")
        assert result["normalized_label"] == "Dataset S1"
        assert result["asset_type"] == "dataset"
        assert result["is_supplementary"] is True

    def test_data_s1(self):
        result = normalize_label("Data S1")
        assert result["normalized_label"] == "Dataset S1"
        assert result["asset_type"] == "dataset"

    def test_supplementary_data_1(self):
        result = normalize_label("Supplementary Data 1")
        assert result["normalized_label"] == "Dataset S1"
        assert result["asset_type"] == "dataset"
        assert result["is_supplementary"] is True


class TestNormalizeSupplementary:
    def test_supplementary_material(self):
        result = normalize_label("Supplementary Material")
        assert result["asset_type"] == "supplementary"
        assert result["is_supplementary"] is True

    def test_supporting_information(self):
        result = normalize_label("Supporting Information")
        assert result["asset_type"] == "supplementary"
        assert result["is_supplementary"] is True

    def test_si_appendix(self):
        result = normalize_label("SI Appendix")
        assert result["asset_type"] == "supplementary"

    def test_additional_file(self):
        result = normalize_label("Additional file 1")
        assert result["asset_type"] == "supplementary"

    def test_appendix_figure_s1(self):
        result = normalize_label("Appendix Figure S1")
        assert result["normalized_label"] == "Figure S1"
        assert result["asset_type"] == "figure"


class TestParseNumberPart:
    def test_simple_number(self):
        label, subpanel = _parse_number_part("1", "Figure", False)
        assert label == "Figure 1"
        assert subpanel == ""

    def test_number_with_subpanel(self):
        label, subpanel = _parse_number_part("1A", "Figure", False)
        assert label == "Figure 1"
        assert subpanel == "A"

    def test_s_number(self):
        label, subpanel = _parse_number_part("S1", "Figure", True)
        assert label == "Figure S1"
        assert subpanel == ""

    def test_s_number_with_subpanel(self):
        label, subpanel = _parse_number_part("S3B", "Figure", True)
        assert label == "Figure S3"
        assert subpanel == "B"

    def test_plain_number_supp(self):
        """Plain number with is_supp=True adds S prefix."""
        label, subpanel = _parse_number_part("1", "Figure", True)
        assert label == "Figure S1"
        assert subpanel == ""


class TestMakeSearchVariants:
    def test_figure_s1_variants(self):
        variants = make_search_variants("Figure S1", "figure")
        assert "Figure S1" in variants
        assert "Figure_S1" in variants
        assert "Fig_S1" in variants
        assert "Fig.S1" in variants
        assert "S1" in variants
        assert "Figure 1" in variants  # without S prefix
        assert "1" in variants  # bare number

    def test_table_3_variants(self):
        variants = make_search_variants("Table 3", "table")
        assert "Table 3" in variants
        assert "Table_3" in variants
        assert "Tab_3" in variants
        assert "3" in variants

    def test_dataset_s2_variants(self):
        variants = make_search_variants("Dataset S2", "dataset")
        assert "Dataset S2" in variants
        assert "Data_S2" in variants
