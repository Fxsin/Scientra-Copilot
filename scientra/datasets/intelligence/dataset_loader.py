"""Dataset Loader — read dataset files with sampling for large files."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

MAX_ROWS = 100000
DEFAULT_SAMPLE = 50


def load_dataset(file_path: str, max_sample_rows: int = DEFAULT_SAMPLE) -> dict[str, Any]:
    """Load a dataset file, returning structure with sampled rows.

    Returns dict with load_status, sheets, n_rows, n_columns, headers, sample_rows, warnings.
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    base = {
        "dataset_id": "", "asset_id": "", "load_status": "failed",
        "file_type": ext.replace(".", ""), "sheets": [],
        "n_rows": 0, "n_columns": 0, "headers": [], "sample_rows": [],
        "warnings": [],
    }

    if not path.exists():
        base["warnings"].append(f"File not found: {file_path}")
        return base

    try:
        if ext in (".xlsx", ".xls"):
            return _load_excel(path, max_sample_rows, base)
        elif ext == ".csv":
            return _load_delimited(path, ",", max_sample_rows, base)
        elif ext in (".tsv", ".tab"):
            return _load_delimited(path, "\t", max_sample_rows, base)
        elif ext == ".txt":
            return _load_delimited(path, None, max_sample_rows, base)
        else:
            base["load_status"] = "unsupported"
            base["warnings"].append(f"Unsupported: {ext}")
            return base
    except Exception as e:
        base["load_status"] = "failed"
        base["warnings"].append(str(e))
        return base


def _load_excel(path: Path, max_sample: int, base: dict) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = []
    total_rows = 0
    total_cols = 0
    warnings = []

    for sn in wb.sheetnames[:20]:  # Max 20 sheets
        ws = wb[sn]
        rows = list(ws.iter_rows(values_only=True))
        n = len(rows)
        if n > MAX_ROWS:
            warnings.append(f"Sheet '{sn}' has {n} rows — using sampling.")
            rows = rows[:MAX_ROWS]

        headers = [str(v).strip() if v is not None else "" for v in rows[0]] if rows else []
        sample = []
        for row in rows[1:max_sample + 1]:
            sample.append([str(v) if v is not None else "" for v in row])

        nc = len(headers) if headers else (max(len(r) for r in rows) if rows else 0)
        sheets.append({
            "sheet_name": sn, "n_rows": n, "n_columns": nc,
            "headers": headers[:100], "sample_rows": sample,
        })
        total_rows += n
        if nc > total_cols:
            total_cols = nc

    wb.close()
    base["load_status"] = "loaded"
    base["sheets"] = sheets
    base["n_rows"] = total_rows
    base["n_columns"] = total_cols
    base["headers"] = sheets[0]["headers"] if sheets else []
    base["sample_rows"] = sheets[0]["sample_rows"] if sheets else []
    base["warnings"].extend(warnings)
    return base


def _load_delimited(path: Path, delimiter: str | None, max_sample: int, base: dict) -> dict:
    if delimiter is None:
        content = path.read_text(encoding="utf-8", errors="replace")[:5000]
        tabs = content.count("\t")
        commas = content.count(",")
        delimiter = "\t" if tabs > commas else ","

    rows_data = []
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for i, row in enumerate(reader):
            if i >= MAX_ROWS:
                base["warnings"].append(f"File truncated at {MAX_ROWS} rows.")
                break
            rows_data.append(row)

    if not rows_data:
        base["load_status"] = "empty"
        return base

    headers = [str(v).strip() for v in rows_data[0]]
    sample = [[str(v) for v in row] for row in rows_data[1:max_sample + 1]]
    nc = len(headers)

    base["load_status"] = "loaded"
    base["n_rows"] = len(rows_data)
    base["n_columns"] = nc
    base["headers"] = headers[:100]
    base["sample_rows"] = sample
    base["sheets"] = [{"sheet_name": path.stem, "n_rows": len(rows_data), "n_columns": nc, "headers": headers[:100], "sample_rows": sample}]
    return base
