"""
Hybrid PDF Parser — PyMuPDF Adapter.

Provides fast PDF scanning (page count, text layer detection, image count),
raw text extraction fallback, and image extraction.

Third-Party Notice:
  PyMuPDF (fitz) — Copyright Artifex Software, Inc.
  Licensed under AGPL-3.0 (SPDX: AGPL-3.0) or a commercial license.
  See https://pymupdf.readthedocs.io/en/latest/about.html#license

  WARNING: PyMuPDF is AGPL-3.0 licensed. The AGPL requires that all
  derivative works be licensed under AGPL-3.0, including when used
  as a network service. Users distributing Scientra Copilot with
  PyMuPDF should seek legal advice or obtain a commercial license
  from Artifex (https://artifex.com/).

All functions return ParserOutput with status="skipped" if PyMuPDF is
not installed. No uncaught exceptions propagate.
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.parsers.types import (
    OutputType,
    ParserOutput,
    ParserStatus,
    PDFScanReport,
    PDFType,
)


def _resolve_root() -> Path:
    """Resolve project root from this file's location."""
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[2]


def _ensure_dir(target: Path) -> Path:
    """Create directory if it doesn't exist and return it."""
    target.mkdir(parents=True, exist_ok=True)
    return target


# ── Public API ──

def run_pymupdf_scan(
    pdf_path: str | Path,
    paper_id: str,
    output_root: str | Path | None = None,
) -> ParserOutput:
    """Scan a PDF with PyMuPDF to detect type, pages, text layer, etc.

    Saves:
    - 02_Parse/reports/pymupdf/{paper_id}.json  (scan report)
    - 02_Parse/text/pymupdf/{paper_id}.txt       (raw text)

    Returns ParserOutput with status="skipped" if PyMuPDF is not available.
    """
    pdf_path = Path(pdf_path)
    root = Path(output_root) if output_root else _resolve_root()

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ParserOutput(
            parser_name="pymupdf",
            status=ParserStatus.SKIPPED,
            output_type=OutputType.SCAN_REPORT,
            warnings=["PyMuPDF (fitz) is not installed. Skipping PDF scan."],
        )

    try:
        if not pdf_path.exists():
            return ParserOutput(
                parser_name="pymupdf",
                status=ParserStatus.FAILED,
                output_type=OutputType.SCAN_REPORT,
                errors=[f"PDF file not found: {pdf_path}"],
            )

        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        has_text_layer = False
        total_text_length = 0
        image_count = 0
        all_pages_text: list[str] = []

        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()
            if text and text.strip():
                has_text_layer = True
                total_text_length += len(text)
                all_pages_text.append(text)

            # Count images on the page
            try:
                images = page.get_images()
                image_count += len(images)
            except Exception:
                pass

        doc.close()

        # Heuristic: scanned PDFs have little or no text but many images
        suspected_scanned = (not has_text_layer or total_text_length < 500) and image_count > page_count

        file_size = pdf_path.stat().st_size if pdf_path.exists() else 0

        # Classify PDF type
        if suspected_scanned:
            pdf_type = PDFType.SCANNED_PDF
        elif image_count > page_count * 3:
            pdf_type = PDFType.IMAGE_HEAVY_PDF
        elif total_text_length > 50000 and page_count < 20:
            pdf_type = PDFType.TABLE_HEAVY_PDF  # best guess; tables often produce dense text
        else:
            pdf_type = PDFType.NORMAL_PAPER

        scan_report = PDFScanReport(
            page_count=page_count,
            has_text_layer=has_text_layer,
            text_length=total_text_length,
            image_count=image_count,
            suspected_scanned_pdf=suspected_scanned,
            pdf_type=pdf_type,
            file_size_bytes=file_size,
        )

        # Save raw text
        text_dir = _ensure_dir(root / "02_Parse" / "text" / "pymupdf")
        text_path = text_dir / f"{paper_id}.txt"
        combined_text = "\n\n".join(all_pages_text)
        text_path.write_text(combined_text, encoding="utf-8")

        # Save scan report
        report_dir = _ensure_dir(root / "02_Parse" / "reports" / "pymupdf")
        report_path = report_dir / f"{paper_id}.json"
        report_path.write_text(
            json.dumps(scan_report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        status = ParserStatus.FALLBACK if suspected_scanned else ParserStatus.SUCCESS
        warnings: list[str] = []
        if suspected_scanned:
            warnings.append("Scanned PDF detected — text layer missing or minimal. OCR may be required.")

        return ParserOutput(
            parser_name="pymupdf",
            status=status,
            output_type=OutputType.SCAN_REPORT,
            output_paths=[str(text_path), str(report_path)],
            quality_score=0.0 if suspected_scanned else 0.7,
            warnings=warnings,
        )

    except Exception as exc:
        return ParserOutput(
            parser_name="pymupdf",
            status=ParserStatus.FAILED,
            output_type=OutputType.SCAN_REPORT,
            errors=[f"PyMuPDF scan failed: {type(exc).__name__}: {exc}"],
        )


def extract_pymupdf_figures(
    pdf_path: str | Path,
    paper_id: str,
    output_root: str | Path | None = None,
) -> ParserOutput:
    """Extract images from a PDF using PyMuPDF.

    Saves images to:
    - 02_Parse/figures/raw_images/{paper_id}/

    Returns ParserOutput with status="skipped" if PyMuPDF is not available.
    """
    pdf_path = Path(pdf_path)
    root = Path(output_root) if output_root else _resolve_root()

    try:
        import fitz
    except ImportError:
        return ParserOutput(
            parser_name="pymupdf",
            status=ParserStatus.SKIPPED,
            output_type=OutputType.FIGURES,
            warnings=["PyMuPDF (fitz) is not installed. Skipping figure extraction."],
        )

    try:
        if not pdf_path.exists():
            return ParserOutput(
                parser_name="pymupdf",
                status=ParserStatus.FAILED,
                output_type=OutputType.FIGURES,
                errors=[f"PDF file not found: {pdf_path}"],
            )

        doc = fitz.open(str(pdf_path))
        output_dir = _ensure_dir(root / "02_Parse" / "figures" / "raw_images" / paper_id)
        extracted_paths: list[str] = []
        image_count = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            images = page.get_images()
            for img_idx, img in enumerate(images):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image.get("image")
                    if image_bytes:
                        ext = base_image.get("ext", "png")
                        img_path = output_dir / f"page{page_num + 1:03d}_img{img_idx + 1:03d}.{ext}"
                        img_path.write_bytes(image_bytes)
                        extracted_paths.append(str(img_path))
                        image_count += 1
                except Exception:
                    continue

        doc.close()

        return ParserOutput(
            parser_name="pymupdf",
            status=ParserStatus.SUCCESS if extracted_paths else ParserStatus.FALLBACK,
            output_type=OutputType.FIGURES,
            output_paths=[str(output_dir)] if extracted_paths else [],
            warnings=[] if extracted_paths else ["No images extracted from PDF."],
        )

    except Exception as exc:
        return ParserOutput(
            parser_name="pymupdf",
            status=ParserStatus.FAILED,
            output_type=OutputType.FIGURES,
            errors=[f"PyMuPDF figure extraction failed: {type(exc).__name__}: {exc}"],
        )
