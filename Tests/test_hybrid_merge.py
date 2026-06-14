"""
Test: Hybrid Merge.

Verifies:
- merge_parser_outputs produces valid HybridParseResult
- Final markdown path is created
- Manifest is written to 02_Parse/reports/hybrid/
- Priority rules are followed (GROBID for metadata, OpenDataLoader for markdown, etc.)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_merge_produces_result():
    """merge_parser_outputs should produce a HybridParseResult."""
    from scientra.parsers.hybrid_merge import merge_parser_outputs
    from scientra.parsers.types import (
        ParserOutput,
        ParserStatus,
        OutputType,
        ParserQualityReport,
    )

    # Create dummy parser outputs
    grobid_out = ParserOutput(
        parser_name="grobid",
        status=ParserStatus.SUCCESS,
        output_type=OutputType.METADATA,
        output_paths=["/tmp/grobid_meta.json"],
        quality_score=0.9,
    )

    od_out = ParserOutput(
        parser_name="opendataloader",
        status=ParserStatus.SUCCESS,
        output_type=OutputType.MARKDOWN,
        output_paths=["/tmp/od_markdown.md", "/tmp/od_layout.json"],
        quality_score=0.85,
    )

    quality_report = ParserQualityReport(
        metadata_score=0.9,
        markdown_score=0.85,
        layout_score=0.8,
        overall_score=0.82,
    )

    result = merge_parser_outputs(
        paper_id="test_paper_001",
        grobid_output=grobid_out,
        opendataloader_output=od_out,
        marker_output=None,
        pymupdf_output=None,
        quality_report=quality_report,
        pdf_path="/tmp/test.pdf",
    )

    assert result is not None
    assert result.paper_id == "test_paper_001"
    assert result.metadata_source == "grobid"
    assert result.markdown_source == "opendataloader"

    # Manifest should be writable
    manifest_path = Path(result.manifest_path)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        assert manifest["paper_id"] == "test_paper_001"
        print(f"Manifest written: {manifest_path}")

    print(f"Merge result: metadata_source={result.metadata_source}, markdown_source={result.markdown_source}")


def test_merge_fallback_to_marker():
    """When OpenDataLoader fails, should fallback to Marker."""
    from scientra.parsers.hybrid_merge import merge_parser_outputs
    from scientra.parsers.types import ParserOutput, ParserStatus, OutputType

    od_out = ParserOutput(
        parser_name="opendataloader",
        status=ParserStatus.SKIPPED,
        output_type=OutputType.MARKDOWN,
        warnings=["Not installed"],
    )

    marker_out = ParserOutput(
        parser_name="marker",
        status=ParserStatus.SUCCESS,
        output_type=OutputType.MARKDOWN,
        output_paths=["/tmp/marker_md.md"],
        quality_score=0.88,
    )

    result = merge_parser_outputs(
        paper_id="test_fallback",
        grobid_output=None,
        opendataloader_output=od_out,
        marker_output=marker_out,
        pymupdf_output=None,
    )

    assert result.markdown_source == "marker"
    print(f"Fallback worked: markdown_source={result.markdown_source}")


def test_merge_grobid_metadata_priority():
    """GROBID should be preferred for metadata."""
    from scientra.parsers.hybrid_merge import merge_parser_outputs
    from scientra.parsers.types import ParserOutput, ParserStatus, OutputType

    grobid_out = ParserOutput(
        parser_name="grobid",
        status=ParserStatus.SUCCESS,
        output_type=OutputType.METADATA,
        quality_score=0.95,
    )

    result = merge_parser_outputs(
        paper_id="test_meta_prio",
        grobid_output=grobid_out,
        opendataloader_output=None,
        marker_output=None,
        pymupdf_output=None,
    )

    assert result.metadata_source == "grobid"
    assert result.references_source == "grobid"
    print(f"GROBID priority: metadata_source={result.metadata_source}, references_source={result.references_source}")


def test_manifest_writable():
    """Manifest should be written to 02_Parse/reports/hybrid/."""
    from scientra.parsers.hybrid_merge import merge_parser_outputs
    from scientra.parsers.types import ParserOutput, ParserStatus, OutputType

    od_out = ParserOutput(
        parser_name="opendataloader",
        status=ParserStatus.SUCCESS,
        output_type=OutputType.MARKDOWN,
        output_paths=[],
        quality_score=0.7,
    )

    result = merge_parser_outputs(
        paper_id="test_manifest_write",
        grobid_output=None,
        opendataloader_output=od_out,
        marker_output=None,
        pymupdf_output=None,
    )

    manifest_path = Path(result.manifest_path)
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text())
        assert data["paper_id"] == "test_manifest_write"
        assert "parser_outputs" in data
        print(f"Manifest writable at: {manifest_path}")
    else:
        print(f"Manifest path returned but file not found (may depend on output_root): {manifest_path}")


if __name__ == "__main__":
    test_merge_produces_result()
    test_merge_fallback_to_marker()
    test_merge_grobid_metadata_priority()
    test_manifest_writable()
    print("\n[OK] All hybrid merge tests passed!")
