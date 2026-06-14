"""Tests for Asset Classifier."""

from __future__ import annotations

import pytest
from scientra.assets.asset_classifier import classify_asset


class TestSupplementaryPDF:
    def test_supplementary_keyword(self):
        atype, conf, warnings = classify_asset("supplementary.pdf", paper_has_main_pdf=True)
        assert atype == "supplementary_pdf"
        assert conf >= 0.8

    def test_supporting_information(self):
        atype, conf, _ = classify_asset("supporting_information.pdf", paper_has_main_pdf=True)
        assert atype == "supplementary_pdf"

    def test_appendix_pdf(self):
        atype, conf, _ = classify_asset("appendix_a.pdf", paper_has_main_pdf=True)
        assert atype == "supplementary_pdf"

    def test_si_file(self):
        atype, conf, _ = classify_asset("si_figures.pdf", paper_has_main_pdf=True)
        assert atype == "supplementary_pdf"


class TestMainPDF:
    def test_first_pdf_no_main(self):
        atype, conf, _ = classify_asset("research_paper.pdf", paper_has_main_pdf=False)
        assert atype == "main_pdf"

    def test_pdf_when_main_exists(self):
        atype, conf, warnings = classify_asset("some_other.pdf", paper_has_main_pdf=True)
        assert atype == "attachment"
        assert len(warnings) >= 1


class TestExcel:
    def test_xlsx(self):
        atype, conf, _ = classify_asset("Table_S1.xlsx")
        assert atype == "supplementary_table"

    def test_xls(self):
        atype, conf, _ = classify_asset("data.xls")
        assert atype == "supplementary_table"


class TestCSV:
    def test_csv(self):
        atype, conf, _ = classify_asset("source_data.csv")
        assert atype == "dataset"

    def test_tsv(self):
        atype, conf, _ = classify_asset("results.tsv")
        assert atype == "dataset"


class TestImages:
    def test_png_figure(self):
        atype, conf, _ = classify_asset("figure_1.png")
        assert atype == "figure_image"

    def test_tiff(self):
        atype, conf, _ = classify_asset("microscopy.tif")
        assert atype == "figure_image"

    def test_table_image(self):
        atype, conf, _ = classify_asset("table_2.png")
        assert atype == "table_image"


class TestArchives:
    def test_zip(self):
        atype, conf, _ = classify_asset("raw_data.zip")
        assert atype == "archive"

    def test_rar(self):
        atype, conf, _ = classify_asset("supplementary.rar")
        assert atype == "archive"


class TestUnknown:
    def test_unknown_extension(self):
        atype, conf, warnings = classify_asset("data.xyz")
        assert atype == "unknown"
        assert len(warnings) >= 1
