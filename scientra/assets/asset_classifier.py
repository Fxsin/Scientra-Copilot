"""Asset type classification based on filename, extension, and MIME type."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

# Classification result: (asset_type, confidence, warnings)
ClassificationResult = tuple[str, float, list[str]]

# Keywords for supplementary PDF detection
_SUPP_PDF_KEYWORDS = [
    "supplementary", "supporting", "supplement", "appendix",
    "si_", "si-", "_si", "-si", "si_fig", "si_table",
    "suppl", "supp_info", "suppinfo", "supporting_information",
]


def classify_asset(
    filepath: str,
    original_filename: str | None = None,
    mime_type: str | None = None,
    paper_has_main_pdf: bool = False,
) -> ClassificationResult:
    """Classify an asset file into an asset_type.

    Args:
        filepath: Path to the file on disk.
        original_filename: Original filename (if different from filepath).
        mime_type: MIME type hint.
        paper_has_main_pdf: Whether the paper already has a main PDF registered.

    Returns:
        Tuple of (asset_type, confidence, warnings).
    """
    path = Path(filepath)
    filename = (original_filename or path.name).lower()
    extension = path.suffix.lower()

    # Guess MIME type if not provided
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or ""

    warnings: list[str] = []

    # ── PDF ──
    if extension == ".pdf":
        return _classify_pdf(filename, mime_type, paper_has_main_pdf, warnings)

    # ── Excel ──
    if extension in (".xlsx", ".xls"):
        return ("supplementary_table", 0.9, warnings)

    # ── CSV/TSV ──
    if extension in (".csv", ".tsv"):
        return ("dataset", 0.85, warnings)

    # ── Images ──
    if extension in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".svg"):
        if "table" in filename or "tab_" in filename or "_tab" in filename:
            return ("table_image", 0.8, warnings)
        return ("figure_image", 0.8, warnings)

    # ── Archives ──
    if extension in (".zip", ".rar", ".7z", ".tar", ".gz"):
        return ("archive", 0.9, warnings)

    # ── Documents ──
    if extension in (".doc", ".docx"):
        warnings.append(f"DOC/DOCX file classified as attachment: {filename}")
        return ("attachment", 0.7, warnings)

    # ── Text ──
    if extension in (".txt", ".md", ".rst"):
        return ("attachment", 0.6, warnings)

    # ── Unknown ──
    warnings.append(f"Unknown file type for extension '{extension}': {filename}")
    return ("unknown", 0.3, warnings)


def _classify_pdf(
    filename: str,
    mime_type: str,
    paper_has_main_pdf: bool,
    warnings: list[str],
) -> ClassificationResult:
    """Classify a PDF file."""
    # Check for supplementary indicators in filename
    supp_matches = sum(1 for kw in _SUPP_PDF_KEYWORDS if kw in filename)

    if supp_matches >= 1:
        return ("supplementary_pdf", 0.85, warnings)

    # If paper has no main PDF and filename doesn't look supplementary
    if not paper_has_main_pdf:
        return ("main_pdf", 0.7, warnings)

    # Paper has main PDF and filename doesn't match supplementary keywords
    warnings.append(
        f"PDF file '{filename}' doesn't match supplementary keywords. "
        "Classified as attachment. Use --asset-type to override."
    )
    return ("attachment", 0.5, warnings)
