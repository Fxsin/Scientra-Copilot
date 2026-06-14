"""Table Structure Parser — parse actual table files to extract structure metadata.

Supports: .xlsx, .xls, .csv, .tsv, .txt
Unsupported: .pdf, .html, .docx (marked as unsupported, no crash)
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any


MAX_SAMPLE_ROWS_DEFAULT = 20
MAX_ROWS_TOTAL = 100000  # Safety limit


def parse_table_structure(
    file_path: str,
    max_sample_rows: int = MAX_SAMPLE_ROWS_DEFAULT,
) -> dict[str, Any]:
    """Parse a table file and extract structure metadata.

    Args:
        file_path: Path to the table file.
        max_sample_rows: Maximum number of sample rows to include.

    Returns:
        Structure dict with sheet info, headers, sample rows, parse status.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if not path.exists():
        return _empty_structure("failed", "unknown", [f"File not found: {file_path}"])

    try:
        if ext in (".xlsx", ".xls"):
            return _parse_excel(path, max_sample_rows)
        elif ext == ".csv":
            return _parse_delimited(path, ",", "csv", max_sample_rows)
        elif ext == ".tsv" or ext == ".tab":
            return _parse_delimited(path, "\t", "tsv", max_sample_rows)
        elif ext == ".txt":
            return _parse_delimited(path, None, "txt", max_sample_rows)
        elif ext == ".pdf":
            return _empty_structure("unsupported", "pdf", ["PDF table parsing not yet supported."])
        elif ext in (".html", ".htm"):
            return _empty_structure("unsupported", "html", ["HTML table parsing not yet supported."])
        elif ext in (".docx", ".doc"):
            return _empty_structure("unsupported", "docx", ["DOCX table parsing not yet supported."])
        else:
            return _empty_structure("unsupported", ext, [f"Unsupported format: {ext}"])
    except Exception as e:
        return _empty_structure("failed", ext, [f"Parse error: {str(e)}"])


def _parse_excel(path: Path, max_sample_rows: int) -> dict[str, Any]:
    """Parse Excel file using openpyxl or xlrd."""
    ext = path.suffix.lower()
    sheets: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        if ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                sheet_info = _extract_sheet_from_openpyxl(ws, sheet_name, max_sample_rows)
                sheets.append(sheet_info)
            wb.close()
        else:
            # .xls
            import xlrd
            wb = xlrd.open_workbook(str(path))
            for sheet_name in wb.sheet_names():
                ws = wb.sheet_by_name(sheet_name)
                sheet_info = _extract_sheet_from_xlrd(ws, sheet_name, max_sample_rows)
                sheets.append(sheet_info)

    except Exception as e:
        warnings.append(f"Excel parse error: {str(e)}")
        if not sheets:
            return _empty_structure("failed", ext, warnings)

    return {
        "table_id": "",
        "asset_id": "",
        "parse_status": "parsed" if sheets else "empty",
        "file_type": ext.replace(".", ""),
        "sheets": sheets,
        "parse_warnings": warnings,
    }


def _extract_sheet_from_openpyxl(ws, sheet_name: str, max_sample_rows: int) -> dict[str, Any]:
    """Extract structure from openpyxl worksheet."""
    rows_data = list(ws.iter_rows(values_only=True))
    return _process_rows(rows_data, sheet_name, max_sample_rows)


def _extract_sheet_from_xlrd(ws, sheet_name: str, max_sample_rows: int) -> dict[str, Any]:
    """Extract structure from xlrd worksheet."""
    rows_data = []
    for r in range(ws.nrows):
        rows_data.append([ws.cell_value(r, c) for c in range(ws.ncols)])
    return _process_rows(rows_data, sheet_name, max_sample_rows)


def _parse_delimited(
    path: Path, delimiter: str | None, file_type: str, max_sample_rows: int,
) -> dict[str, Any]:
    """Parse CSV/TSV/TXT file."""
    warnings: list[str] = []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return _empty_structure("failed", file_type, [f"Read error: {str(e)}"])

    # Auto-detect delimiter for .txt
    if delimiter is None:
        delimiter = _detect_delimiter(content)

    try:
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows_data = []
        for row in reader:
            if len(rows_data) >= MAX_ROWS_TOTAL:
                warnings.append(f"Table truncated at {MAX_ROWS_TOTAL} rows.")
                break
            rows_data.append(row)
    except Exception as e:
        return _empty_structure("failed", file_type, [f"CSV parse error: {str(e)}"])

    sheet_info = _process_rows(rows_data, "Sheet1", max_sample_rows)
    sheet_info["sheet_name"] = path.stem

    return {
        "table_id": "",
        "asset_id": "",
        "parse_status": "parsed" if rows_data else "empty",
        "file_type": file_type,
        "sheets": [sheet_info],
        "parse_warnings": warnings,
    }


def _process_rows(
    rows_data: list, sheet_name: str, max_sample_rows: int,
) -> dict[str, Any]:
    """Process raw rows into structured sheet info."""
    if not rows_data:
        return {
            "sheet_name": sheet_name,
            "n_rows": 0,
            "n_columns": 0,
            "headers": [],
            "sample_rows": [],
            "detected_empty_rows": 0,
            "detected_merged_cells": False,
        }

    n_rows = len(rows_data)
    n_columns = max(len(row) for row in rows_data) if rows_data else 0

    # Detect headers (first non-empty row)
    headers: list[str] = []
    header_row_idx = 0
    for i, row in enumerate(rows_data):
        if any(v is not None and str(v).strip() != "" for v in row):
            headers = [str(v).strip() if v is not None else "" for v in row]
            header_row_idx = i
            break

    # Count empty rows
    empty_count = sum(
        1 for row in rows_data
        if all(v is None or str(v).strip() == "" for v in row)
    )

    # Sample rows (after header)
    sample_start = header_row_idx + 1
    sample_end = min(sample_start + max_sample_rows, n_rows)
    sample_rows = []
    for row in rows_data[sample_start:sample_end]:
        sample_rows.append([str(v) if v is not None else "" for v in row])

    return {
        "sheet_name": sheet_name,
        "n_rows": n_rows,
        "n_columns": n_columns,
        "headers": headers[:50],  # Limit header count
        "sample_rows": sample_rows,
        "detected_empty_rows": empty_count,
        "detected_merged_cells": False,  # Simplified; real detection needs openpyxl merged_cells
    }


def _detect_delimiter(content: str) -> str:
    """Auto-detect delimiter for text files."""
    # Try tab first, then comma, then semicolon
    first_lines = content[:2000]
    tabs = first_lines.count("\t")
    commas = first_lines.count(",")
    semicolons = first_lines.count(";")

    if tabs > commas and tabs > semicolons:
        return "\t"
    elif semicolons > commas:
        return ";"
    return ","


def _empty_structure(status: str, file_type: str, warnings: list[str]) -> dict[str, Any]:
    """Return an empty structure for unparseable files."""
    return {
        "table_id": "",
        "asset_id": "",
        "parse_status": status,
        "file_type": file_type,
        "sheets": [],
        "parse_warnings": warnings,
    }
