"""
Supplementary Preview — lightweight preview extraction for supplementary files.

Phase 2C: Reads first 20 rows from csv/tsv/xlsx files for preview purposes.
No OCR. No LLM. No full file reads. No complex interpretation.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

MAX_PREVIEW_ROWS = 20
MAX_PREVIEW_CHARS = 5000


class SupplementaryPreview:
    """Extracts lightweight preview data from supplementary files."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def preview(self, file_path: str) -> dict[str, Any]:
        """Extract preview from a supplementary file.

        Phase 2C-B: Rejects raw_text files, original PDFs, and generated assets.
        Only true supplementary files (xlsx/csv/tsv/keyword-labeled) are previewed.

        Returns dict with columns, rows (preview), row_count, column_count, status, notes.
        """
        full_path = self.root / file_path
        result: dict[str, Any] = {
            "preview_columns": [],
            "preview_rows": [],
            "row_count": 0,
            "column_count": 0,
            "content_status": "link_only",
            "notes": [],
        }

        # Phase 2C-B: Reject non-true-supplementary paths
        rp_lower = file_path.lower()
        reject_patterns = [
            r'03_summary[\\/]raw_text', r'01_pdf[\\/]',
            r'06_pdf_dataassets', r'02_metadata', r'03_evidence',
            r'04_vectordb', r'05_index',
        ]
        for pat in reject_patterns:
            if re.search(pat, rp_lower):
                return {**result, "content_status": "complex_file_skipped",
                        "notes": [f"Not a true supplementary file: {file_path}"]}

        if not full_path.exists():
            return {**result, "content_status": "file_missing",
                    "notes": [f"File not found: {file_path}"]}

        ext = full_path.suffix.lower()

        try:
            if ext in ('.csv',):
                return self._preview_csv(full_path, result)
            elif ext in ('.tsv', '.txt'):
                return self._preview_tsv(full_path, result)
            elif ext in ('.xlsx', '.xls'):
                return self._preview_xlsx(full_path, result)
            elif ext in ('.pdf', '.docx', '.zip'):
                return {**result, "content_status": "complex_file_skipped",
                        "notes": [f"Preview not supported for {ext} in Phase 2C"]}
            else:
                return {**result, "content_status": "complex_file_skipped",
                        "notes": [f"Unknown file type: {ext}"]}
        except Exception as e:
            return {**result, "content_status": "file_unreadable",
                    "notes": [f"Error reading file: {str(e)[:200]}"]}

    def _preview_csv(self, path: Path, result: dict) -> dict:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows_data = []
                for i, row in enumerate(reader):
                    if i == 0:
                        result["preview_columns"] = [c.strip() for c in row]
                        result["column_count"] = len(row)
                    if i < MAX_PREVIEW_ROWS:
                        row_dict = {}
                        for j, cell in enumerate(row):
                            col_name = result["preview_columns"][j] if j < len(result["preview_columns"]) else f"col_{j}"
                            row_dict[col_name] = str(cell)[:200]
                        rows_data.append(row_dict)
                    result["row_count"] = i + 1

                result["preview_rows"] = rows_data
                result["content_status"] = "simple_preview_extracted"
                result["notes"].append(f"CSV: {result['column_count']} cols, {result['row_count']} rows, preview={len(rows_data)} rows")
        except Exception as e:
            result["notes"].append(f"CSV parse error: {e}")
            result["content_status"] = "file_unreadable"
        return result

    def _preview_tsv(self, path: Path, result: dict) -> dict:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_PREVIEW_CHARS * 2)
            lines = content.strip().splitlines()
            if not lines:
                return {**result, "content_status": "file_unreadable", "notes": ["Empty file"]}

            # Detect delimiter
            first_line = lines[0]
            if '\t' in first_line:
                delimiter = '\t'
            elif ',' in first_line:
                delimiter = ','
            else:
                # Try whitespace
                delimiter = None

            rows_data = []
            for i, line in enumerate(lines[:MAX_PREVIEW_ROWS]):
                if delimiter:
                    cells = line.split(delimiter)
                else:
                    cells = re.split(r'\s{2,}', line.strip())
                cells = [c.strip() for c in cells if c.strip()]

                if i == 0:
                    result["preview_columns"] = cells
                    result["column_count"] = len(cells)
                row_dict = {}
                for j, cell in enumerate(cells):
                    col_name = result["preview_columns"][j] if j < len(result["preview_columns"]) else f"col_{j}"
                    row_dict[col_name] = cell[:200]
                rows_data.append(row_dict)

            result["preview_rows"] = rows_data
            result["row_count"] = len(lines)
            result["content_status"] = "simple_preview_extracted"
            result["notes"].append(f"TXT/TSV: {result['column_count']} cols, {result['row_count']} rows, preview={len(rows_data)} rows")
        except Exception as e:
            result["notes"].append(f"TSV/TXT parse error: {e}")
            result["content_status"] = "file_unreadable"
        return result

    def _preview_xlsx(self, path: Path, result: dict) -> dict:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            result["notes"].append(f"Sheets: {', '.join(sheet_names[:5])}")

            # Preview first sheet
            if sheet_names:
                ws = wb[sheet_names[0]]
                rows_data = []
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    cells = [str(c) if c is not None else "" for c in row]
                    if i == 0:
                        result["preview_columns"] = cells[:50]
                        result["column_count"] = len(cells)
                    if i < MAX_PREVIEW_ROWS:
                        row_dict = {}
                        for j, cell in enumerate(cells[:50]):
                            col_name = result["preview_columns"][j] if j < len(result["preview_columns"]) else f"col_{j}"
                            row_dict[col_name] = str(cell)[:200]
                        rows_data.append(row_dict)
                    result["row_count"] = i + 1
                    if i > MAX_PREVIEW_ROWS * 3:
                        break  # Safety limit

                result["preview_rows"] = rows_data
                result["content_status"] = "simple_preview_extracted"
                result["notes"].append(f"XLSX sheet '{sheet_names[0]}': {result['column_count']} cols, ~{result['row_count']} rows")
            wb.close()
        except ImportError:
            result["notes"].append("openpyxl not available — skipping xlsx preview")
            result["content_status"] = "file_found"
        except Exception as e:
            result["notes"].append(f"XLSX parse error: {str(e)[:200]}")
            result["content_status"] = "file_unreadable"
        return result
