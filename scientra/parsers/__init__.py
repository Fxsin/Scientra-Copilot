"""
Scientra Hybrid PDF Parser — Multi-engine PDF parsing with graceful degradation.

Parsers:
    - GROBID: metadata, references, citation metadata
    - OpenDataLoader PDF: markdown, layout, tables
    - Marker: high-quality markdown (optional fallback)
    - PyMuPDF: fast scan, raw text, figure extraction

Main entry point: run_hybrid_parse()
"""

from scientra.parsers.availability import check_parser_availability
from scientra.parsers.parser_router import run_hybrid_parse
from scientra.parsers.types import (
    HybridParseResult,
    OutputType,
    ParserAvailability,
    ParserOutput,
    ParserQualityReport,
    ParserStatus,
    PDFScanReport,
    PDFType,
)

__all__ = [
    # Main entry point
    "run_hybrid_parse",
    # Availability
    "check_parser_availability",
    "ParserAvailability",
    # Data types
    "HybridParseResult",
    "ParserOutput",
    "ParserQualityReport",
    "PDFScanReport",
    # Enums
    "ParserStatus",
    "OutputType",
    "PDFType",
]
