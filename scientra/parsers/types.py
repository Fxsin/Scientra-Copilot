"""
Hybrid PDF Parser — Unified Data Structures.

Defines the canonical data models used across all parser adapters,
the router, merge logic, and quality scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ── Enums ──

class ParserStatus(str, Enum):
    """Outcome of a single parser run."""
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    FALLBACK = "fallback"


class PDFType(str, Enum):
    """Classification of a PDF document."""
    NORMAL_PAPER = "normal_paper"
    SUPPLEMENTARY_PDF = "supplementary_pdf"
    SCANNED_PDF = "scanned_pdf"
    TABLE_HEAVY_PDF = "table_heavy_pdf"
    IMAGE_HEAVY_PDF = "image_heavy_pdf"
    UNKNOWN = "unknown"


class OutputType(str, Enum):
    """Type of parser output artifact."""
    METADATA = "metadata"
    MARKDOWN = "markdown"
    LAYOUT = "layout"
    TEXT = "text"
    FIGURES = "figures"
    TABLES = "tables"
    REFERENCES = "references"
    SCAN_REPORT = "scan_report"


# ── Data Classes ──

@dataclass
class ParserOutput:
    """Result from a single parser execution."""
    parser_name: str
    status: ParserStatus
    output_type: OutputType
    output_paths: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "parser_name": self.parser_name,
            "status": self.status.value,
            "output_type": self.output_type.value,
            "output_paths": self.output_paths,
            "quality_score": self.quality_score,
            "warnings": self.warnings,
            "errors": self.errors,
            "created_at": self.created_at,
        }


@dataclass
class ParserQualityReport:
    """Quality assessment of a hybrid parse result."""
    metadata_score: float = 0.0
    markdown_score: float = 0.0
    layout_score: float = 0.0
    reference_score: float = 0.0
    figure_score: float = 0.0
    table_score: float = 0.0
    overall_score: float = 0.0
    problems: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_score": self.metadata_score,
            "markdown_score": self.markdown_score,
            "layout_score": self.layout_score,
            "reference_score": self.reference_score,
            "figure_score": self.figure_score,
            "table_score": self.table_score,
            "overall_score": self.overall_score,
            "problems": self.problems,
            "recommendations": self.recommendations,
        }


@dataclass
class PDFScanReport:
    """Quick scan report from PyMuPDF."""
    page_count: int = 0
    has_text_layer: bool = False
    text_length: int = 0
    image_count: int = 0
    suspected_scanned_pdf: bool = False
    pdf_type: PDFType = PDFType.UNKNOWN
    file_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_count": self.page_count,
            "has_text_layer": self.has_text_layer,
            "text_length": self.text_length,
            "image_count": self.image_count,
            "suspected_scanned_pdf": self.suspected_scanned_pdf,
            "pdf_type": self.pdf_type.value,
            "file_size_bytes": self.file_size_bytes,
        }


@dataclass
class HybridParseResult:
    """Complete result from running the hybrid parser pipeline."""
    paper_id: str
    pdf_path: str
    pdf_type: PDFType = PDFType.UNKNOWN
    metadata_source: str = ""
    markdown_source: str = ""
    layout_source: str = ""
    figures_source: str = ""
    tables_source: str = ""
    references_source: str = ""
    final_markdown_path: str = ""
    manifest_path: str = ""
    scan_report: PDFScanReport | None = None
    parser_outputs: list[ParserOutput] = field(default_factory=list)
    quality_report: ParserQualityReport | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "pdf_path": self.pdf_path,
            "pdf_type": self.pdf_type.value,
            "metadata_source": self.metadata_source,
            "markdown_source": self.markdown_source,
            "layout_source": self.layout_source,
            "figures_source": self.figures_source,
            "tables_source": self.tables_source,
            "references_source": self.references_source,
            "final_markdown_path": self.final_markdown_path,
            "manifest_path": self.manifest_path,
            "scan_report": self.scan_report.to_dict() if self.scan_report else None,
            "parser_outputs": [po.to_dict() for po in self.parser_outputs],
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "warnings": self.warnings,
            "errors": self.errors,
            "created_at": self.created_at,
        }


@dataclass
class ParserAvailability:
    """Availability status of each parser in the current environment."""
    grobid_available: bool = False
    opendataloader_available: bool = False
    marker_available: bool = False
    pymupdf_available: bool = False
    hybrid_parser_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "grobid_available": self.grobid_available,
            "opendataloader_available": self.opendataloader_available,
            "marker_available": self.marker_available,
            "pymupdf_available": self.pymupdf_available,
            "hybrid_parser_enabled": self.hybrid_parser_enabled,
        }
