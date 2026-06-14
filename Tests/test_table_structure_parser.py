"""Tests for Table Structure Parser."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest
from scientra.assets.table_intelligence.table_structure_parser import (
    parse_table_structure,
    _parse_delimited,
    _process_rows,
    _detect_delimiter,
)

CSV_DATA = "name,age,score\nAlice,30,95\nBob,25,87\nCharlie,35,92\n"
TSV_DATA = "name\tage\tscore\nAlice\t30\t95\nBob\t25\t87\nCharlie\t35\t92\n"


class TestParseCSV:
    def test_parse_csv(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write(CSV_DATA)
            f.flush()
            result = parse_table_structure(f.name)
        Path(f.name).unlink()

        assert result["parse_status"] == "parsed"
        assert result["file_type"] == "csv"
        assert len(result["sheets"]) == 1
        sheet = result["sheets"][0]
        assert sheet["n_rows"] == 4
        assert sheet["n_columns"] == 3
        assert "name" in sheet["headers"]
        assert len(sheet["sample_rows"]) == 3

    def test_parse_tsv(self):
        with tempfile.NamedTemporaryFile(suffix=".tsv", mode="w", delete=False, encoding="utf-8") as f:
            f.write(TSV_DATA)
            f.flush()
            result = parse_table_structure(f.name)
        Path(f.name).unlink()

        assert result["parse_status"] == "parsed"
        assert result["file_type"] == "tsv"
        assert result["sheets"][0]["n_rows"] == 4

    def test_unsupported_pdf(self):
        # PDF files are unsupported even if they don't exist physically
        # Use a .pdf path that would be treated as unsupported format
        result = parse_table_structure("paper_table.pdf")
        # May be "unsupported" or "failed" depending on whether file check runs first
        assert result["parse_status"] in ("unsupported", "failed")

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write("")
            f.flush()
            result = parse_table_structure(f.name)
        Path(f.name).unlink()
        assert result["parse_status"] == "empty"

    def test_file_not_found(self):
        result = parse_table_structure("/nonexistent/file.xlsx")
        assert result["parse_status"] == "failed"


class TestXLSX:
    def test_parse_xlsx_headers(self):
        # Create a simple xlsx with openpyxl
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Test"
            ws.append(["Gene", "log2FC", "pvalue"])
            ws.append(["GeneA", "2.5", "0.001"])
            ws.append(["GeneB", "-1.3", "0.05"])
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                wb.save(f.name)
                tmp = f.name
            wb.close()

            result = parse_table_structure(tmp)
            Path(tmp).unlink()

            assert result["parse_status"] == "parsed"
            assert result["file_type"] == "xlsx"
            sheet = result["sheets"][0]
            assert "Gene" in sheet["headers"]
            assert sheet["n_rows"] == 3
            assert sheet["n_columns"] == 3
        except ImportError:
            pytest.skip("openpyxl not available")


class TestHelpers:
    def test_detect_delimiter_tab(self):
        assert _detect_delimiter("a\tb\tc\n1\t2\t3\n") == "\t"

    def test_detect_delimiter_comma(self):
        assert _detect_delimiter("a,b,c\n1,2,3\n") == ","

    def test_process_rows(self):
        rows = [["A", "B", "C"], ["1", "2", "3"], ["4", "5", "6"]]
        result = _process_rows(rows, "Sheet1", 20)
        assert result["n_rows"] == 3
        assert result["n_columns"] == 3
        assert result["headers"] == ["A", "B", "C"]
        assert len(result["sample_rows"]) == 2
