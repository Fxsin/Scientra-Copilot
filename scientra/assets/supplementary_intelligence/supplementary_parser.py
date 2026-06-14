"""Supplementary Parser — parse supplementary file text content.

Supports: .pdf (via pdfplumber/PyPDF2), .txt, .md, .docx
Gracefully marks unsupported formats without crashing.
Sources from 01_Sources/ bound to paper supplementary assets.
Intermediates written to 02_Parse/supplementary/text/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_supplementary(file_path: str, paper_id: str = "") -> dict[str, Any]:
    """Parse a supplementary file and extract raw text.

    Args:
        file_path: Path to the supplementary file.
        paper_id: Paper ID for traceability.

    Returns:
        Parse result dict.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    base_result = {
        "supplementary_id": "",
        "paper_id": paper_id,
        "asset_id": "",
        "asset_path": str(path),
        "source_relative_path": "",
        "file_type": ext.replace(".", ""),
        "parse_status": "failed",
        "raw_text": "",
        "text_length": 0,
        "page_count": None,
        "parse_warnings": [],
    }

    if not path.exists():
        base_result["parse_warnings"].append(f"File not found: {file_path}")
        return base_result

    try:
        if ext == ".txt":
            return _parse_txt(path, base_result)
        elif ext == ".md":
            return _parse_txt(path, base_result)  # MD is plain text
        elif ext == ".docx":
            return _parse_docx(path, base_result)
        elif ext == ".pdf":
            return _parse_pdf(path, base_result)
        elif ext == ".html" or ext == ".htm":
            return _parse_html(path, base_result)
        elif ext == ".rtf":
            base_result["parse_status"] = "unsupported"
            base_result["file_type"] = "rtf"
            base_result["parse_warnings"].append("RTF parsing not yet supported.")
            return base_result
        else:
            base_result["parse_status"] = "unsupported"
            base_result["file_type"] = ext.replace(".", "unknown")
            base_result["parse_warnings"].append(f"Unsupported format: {ext}")
            return base_result
    except Exception as e:
        base_result["parse_status"] = "failed"
        base_result["parse_warnings"].append(f"Parse error: {e}")
        return base_result


def _parse_txt(path: Path, result: dict) -> dict:
    """Parse plain text / markdown file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            text = path.read_text(encoding="latin-1", errors="replace")
        except Exception as e:
            result["parse_warnings"].append(f"Text read error: {e}")
            return result

    result["parse_status"] = "parsed" if text.strip() else "empty"
    result["raw_text"] = text
    result["text_length"] = len(text)
    return result


def _parse_docx(path: Path, result: dict) -> dict:
    """Parse DOCX file using python-docx."""
    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        result["parse_status"] = "parsed" if text.strip() else "empty"
        result["raw_text"] = text
        result["text_length"] = len(text)
    except Exception as e:
        result["parse_status"] = "failed"
        result["parse_warnings"].append(f"DOCX parse error: {e}")
    return result


def _parse_pdf(path: Path, result: dict) -> dict:
    """Parse PDF using pdfplumber (primary) or PyPDF2 (fallback)."""
    text = ""
    pages = 0
    warnings: list[str] = []

    # Try pdfplumber first
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages[:200]:  # Safety limit
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            result["parse_status"] = "parsed"
            result["raw_text"] = text
            result["text_length"] = len(text)
            result["page_count"] = pages
            result["parse_warnings"] = warnings
            return result
    except Exception as e:
        warnings.append(f"pdfplumber failed: {e}")

    # Fallback to PyPDF2
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = len(reader.pages)
            for page in reader.pages[:200]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        warnings.append(f"PyPDF2 failed: {e}")

    if text.strip():
        result["parse_status"] = "parsed"
        result["raw_text"] = text
        result["text_length"] = len(text)
        result["page_count"] = pages if pages else None
    else:
        result["parse_status"] = "failed"
        warnings.append("Could not extract text from PDF.")

    result["parse_warnings"] = warnings
    return result


def _parse_html(path: Path, result: dict) -> dict:
    """Parse HTML file — strip tags for basic text extraction."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        import re
        # Simple tag stripping
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        result["parse_status"] = "parsed" if text else "empty"
        result["raw_text"] = text
        result["text_length"] = len(text)
    except Exception as e:
        result["parse_status"] = "failed"
        result["parse_warnings"].append(f"HTML parse error: {e}")
    return result
