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
from scientra.parsers.grobid_adapter import (
    locate_existing_grobid_outputs,
    read_grobid_metadata_if_available,
)
from scientra.parsers.hybrid_input_selector import select_text_for_evidence
from scientra.parsers.hybrid_merge import load_manifest, merge_parser_outputs
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
    # GROBID utilities (read-only, no API calls)
    "locate_existing_grobid_outputs",
    "read_grobid_metadata_if_available",
    # Evidence input selector (P1)
    "select_text_for_evidence",
    # Merge & manifest
    "merge_parser_outputs",
    "load_manifest",
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
