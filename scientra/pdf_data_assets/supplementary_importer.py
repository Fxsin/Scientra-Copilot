"""
Supplementary Importer — scans manual import directory for supplementary files.

Phase 2D: Scans 00_Supplementary/inbox/ for user-placed xlsx/csv/tsv/txt files.
Extracts lightweight previews and generates a file registry for matching.

No LLM. No OCR. No external download. No full file reads.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRUE_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.tsv', '.txt'}
MAX_PREVIEW_ROWS = 20
MAX_PREVIEW_CHARS = 5000


class SupplementaryImporter:
    """Scans manual import directory and builds a file registry with previews."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.inbox_dir = self.root / "00_Supplementary" / "inbox"
        self.registry_dir = self.root / "00_Supplementary" / "registry"

    def scan_inbox(self) -> list[dict[str, Any]]:
        """Scan inbox for supplementary files. Returns list of file records."""
        records: list[dict[str, Any]] = []
        if not self.inbox_dir.exists():
            return records

        for f in sorted(self.inbox_dir.iterdir()):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in TRUE_EXTENSIONS:
                continue

            record = self._build_file_record(f)
            if record:
                records.append(record)

        return records

    def build_registry(self) -> dict[str, Any]:
        """Build full import registry. Returns summary dict."""
        records = self.scan_inbox()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build registry
        registry: dict[str, Any] = {
            "version": "0.1.0",
            "generated_at": timestamp,
            "total_files": len(records),
            "files": records,
            "file_types": self._count_types(records),
            "previewed": sum(1 for r in records if r.get("preview_status") == "previewed"),
            "large_file_preview_only": sum(1 for r in records if r.get("preview_status") == "large_file_preview_only"),
            "file_unreadable": sum(1 for r in records if r.get("preview_status") == "file_unreadable"),
        }

        # Write registry
        reg_path = self.registry_dir / "supplementary_files.json"
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        tmp = reg_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(reg_path)

        # Write report
        self._write_report(registry)

        return registry

    def _build_file_record(self, file_path: Path) -> dict[str, Any] | None:
        """Build a single file record with preview."""
        try:
            stat = file_path.stat()
        except OSError:
            return None

        fname = file_path.name
        ext = file_path.suffix.lower()
        rel_path = str(file_path.relative_to(self.root))

        record: dict[str, Any] = {
            "file_id": f"suppl_file_{file_path.stem[:40]}",
            "file_name": fname,
            "relative_path": rel_path,
            "file_type": ext.lstrip("."),
            "size_bytes": stat.st_size,
            "possible_paper_id": self._guess_paper_id(fname),
            "possible_supplement_label": self._guess_supplement_label(fname),
            "sheet_names": [],
            "preview_status": "none",
            "row_count": 0,
            "column_count": 0,
            "columns_preview": [],
            "first_rows_preview": [],
            "selected_sheet": None,
            "notes": [],
        }

        # Extract preview
        if ext in ('.csv',):
            self._preview_csv(file_path, record)
        elif ext in ('.tsv',):
            self._preview_tsv(file_path, record)
        elif ext in ('.txt',):
            self._preview_txt(file_path, record)
        elif ext in ('.xlsx', '.xls'):
            self._preview_xlsx(file_path, record)

        # Large file note
        if stat.st_size > 50 * 1024 * 1024:  # 50 MB
            record["notes"].append("large_file_preview_only")
            if record["preview_status"] == "previewed":
                record["preview_status"] = "large_file_preview_only"

        return record

    # ── Preview methods ──

    def _preview_csv(self, path: Path, record: dict) -> None:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows_data = []
                for i, row in enumerate(reader):
                    if i == 0:
                        record["columns_preview"] = [c.strip() for c in row]
                        record["column_count"] = len(row)
                    if i < MAX_PREVIEW_ROWS:
                        row_dict = {}
                        for j, cell in enumerate(row):
                            cn = record["columns_preview"][j] if j < len(record["columns_preview"]) else f"col_{j}"
                            row_dict[cn] = str(cell)[:200]
                        rows_data.append(row_dict)
                    record["row_count"] = i + 1
                record["first_rows_preview"] = rows_data
                record["preview_status"] = "previewed"
                record["notes"].append(f"CSV: {record['column_count']} cols, {record['row_count']} rows")
        except Exception as e:
            record["preview_status"] = "file_unreadable"
            record["notes"].append(f"CSV error: {str(e)[:200]}")

    def _preview_tsv(self, path: Path, record: dict) -> None:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_PREVIEW_CHARS * 2)
            lines = content.strip().splitlines()
            if not lines:
                record["preview_status"] = "file_unreadable"
                return
            delimiter = '\t' if '\t' in lines[0] else ','
            rows_data = []
            for i, line in enumerate(lines[:MAX_PREVIEW_ROWS]):
                cells = line.split(delimiter)
                cells = [c.strip() for c in cells]
                if i == 0:
                    record["columns_preview"] = cells
                    record["column_count"] = len(cells)
                row_dict = {}
                for j, cell in enumerate(cells):
                    cn = record["columns_preview"][j] if j < len(record["columns_preview"]) else f"col_{j}"
                    row_dict[cn] = cell[:200]
                rows_data.append(row_dict)
            record["first_rows_preview"] = rows_data
            record["row_count"] = len(lines)
            record["preview_status"] = "previewed"
            record["notes"].append(f"TSV: {record['column_count']} cols, {record['row_count']} rows")
        except Exception as e:
            record["preview_status"] = "file_unreadable"
            record["notes"].append(f"TSV error: {str(e)[:200]}")

    def _preview_txt(self, path: Path, record: dict) -> None:
        # Try CSV first, then TSV
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                first = f.readline()
            if ',' in first and len(first.split(',')) >= 2:
                self._preview_csv(path, record)
            elif '\t' in first and len(first.split('\t')) >= 2:
                self._preview_tsv(path, record)
            else:
                record["preview_status"] = "none"
                record["notes"].append("TXT: No tabular structure detected")
        except Exception as e:
            record["preview_status"] = "file_unreadable"
            record["notes"].append(f"TXT error: {str(e)[:200]}")

    def _preview_xlsx(self, path: Path, record: dict) -> None:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            record["sheet_names"] = wb.sheetnames
            record["notes"].append(f"Sheets: {', '.join(wb.sheetnames[:10])}")

            if wb.sheetnames:
                sheet = wb.sheetnames[0]
                record["selected_sheet"] = sheet
                ws = wb[sheet]
                rows_data = []
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    cells = [str(c) if c is not None else "" for c in row]
                    if i == 0:
                        record["columns_preview"] = cells[:50]
                        record["column_count"] = len(cells)
                    if i < MAX_PREVIEW_ROWS:
                        row_dict = {}
                        for j, cell in enumerate(cells[:50]):
                            cn = record["columns_preview"][j] if j < len(record["columns_preview"]) else f"col_{j}"
                            row_dict[cn] = str(cell)[:200]
                        rows_data.append(row_dict)
                    record["row_count"] = i + 1
                    if i > 500:
                        record["notes"].append("XLSX truncated at 500 rows")
                        break
                record["first_rows_preview"] = rows_data
                record["preview_status"] = "previewed"
            wb.close()
        except ImportError:
            record["preview_status"] = "file_unreadable"
            record["notes"].append("openpyxl not available")
        except Exception as e:
            record["preview_status"] = "file_unreadable"
            record["notes"].append(f"XLSX error: {str(e)[:200]}")

    # ── Guessing methods ──

    def _guess_paper_id(self, filename: str) -> str | None:
        """Guess paper_id from filename pattern."""
        name_no_ext = Path(filename).stem
        # Pattern: {paper_id}__Table_S1
        m = re.match(r'(.+?)__(?:Table_?|Supplementary_?|Fig_?|Figure_?|Data_?|Dataset_?)', name_no_ext, re.IGNORECASE)
        if m:
            return m.group(1)
        # Pattern: {paper_id}.xlsx
        # Check if it looks like a long paper_id with hash
        m = re.match(r'([a-zA-Z][\w_]{20,})', name_no_ext)
        if m:
            return m.group(1)
        return None

    def _guess_supplement_label(self, filename: str) -> str | None:
        """Guess supplement label from filename."""
        name_no_ext = Path(filename).stem
        patterns = [
            (r'Table[_\s]?(S?\d+[A-Za-z]?)', 'Table'),
            (r'Supplementary[_\s]?Table[_\s]?(S?\d+[A-Za-z]?)', 'Supplementary Table'),
            (r'Supplementary[_\s]?Data[_\s]?(\d+)', 'Supplementary Data'),
            (r'Supplementary[_\s]?Dataset[_\s]?(\d+)', 'Supplementary Dataset'),
            (r'Fig[_\s]?S(\d+)', 'Figure S'),
            (r'Figure[_\s]?S(\d+)', 'Figure S'),
            (r'S(\d+)[_\s]Table', 'Table S'),
        ]
        for pat, prefix in patterns:
            m = re.search(pat, name_no_ext, re.IGNORECASE)
            if m:
                num = m.group(1)
                return f"{prefix} {num}"
        return None

    @staticmethod
    def _count_types(records: list[dict]) -> dict[str, int]:
        from collections import Counter
        return dict(Counter(r.get("file_type", "unknown") for r in records))

    def _write_report(self, registry: dict[str, Any]) -> None:
        report_path = self.registry_dir / "manual_import_report.md"
        lines = [
            "# Manual Supplementary Import Report — Phase 2D", "",
            f"Generated: {registry['generated_at']}", "",
            "## Summary", "",
            f"- **Total imported files**: {registry['total_files']}",
            f"- **Files with preview**: {registry['previewed']}",
            f"- **Large file preview only**: {registry['large_file_preview_only']}",
            f"- **File unreadable**: {registry['file_unreadable']}",
            f"- **File types**: {registry['file_types']}",
            "", "## File Details", "",
        ]
        for f in registry.get("files", []):
            lines.append(f"### {f['file_name']}")
            lines.append(f"- Type: {f['file_type']}, Size: {f['size_bytes']} bytes")
            lines.append(f"- Path: `{f['relative_path']}`")
            lines.append(f"- Guessed paper_id: {f.get('possible_paper_id', 'unknown')}")
            lines.append(f"- Guessed label: {f.get('possible_supplement_label', 'unknown')}")
            lines.append(f"- Preview status: {f['preview_status']}")
            lines.append(f"- Columns: {f['column_count']}, Rows: {f['row_count']}")
            if f.get("sheet_names"):
                lines.append(f"- Sheets: {', '.join(f['sheet_names'][:10])}")
            if f.get("notes"):
                for n in f["notes"]:
                    lines.append(f"  - Note: {n}")
            lines.append("")

        if registry['total_files'] == 0:
            lines.append("> No files found in 00_Supplementary/inbox/.")
            lines.append("> Place downloaded supplementary files there and re-run --import-supplementary.")

        lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Import report: {report_path}")


def load_registry(root: str | Path) -> dict[str, Any] | None:
    """Load the supplementary file registry if it exists."""
    reg_path = Path(root) / "00_Supplementary" / "registry" / "supplementary_files.json"
    if reg_path.exists():
        try:
            return json.loads(reg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None
