"""
Hybrid PDF Parser — Unified Entry Point.

Routes PDFs to the appropriate parsers based on document type and
availability. Orchestrates: scan → classify → parse → merge → report.

Usage:
    result = run_hybrid_parse(pdf_path, paper_id)
    print(result.to_dict())
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scientra.parsers.availability import check_parser_availability
from scientra.parsers.grobid_adapter import run_grobid_metadata
from scientra.parsers.hybrid_merge import merge_parser_outputs
from scientra.parsers.marker_adapter import run_marker
from scientra.parsers.opendataloader_adapter import run_opendataloader
from scientra.parsers.pymupdf_adapter import extract_pymupdf_figures, run_pymupdf_scan
from scientra.parsers.quality import score_parse_result
from scientra.parsers.types import (
    HybridParseResult,
    ParserQualityReport,
    ParserStatus,
    PDFType,
)


def _resolve_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[2]


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def run_hybrid_parse(
    pdf_path: str | Path,
    paper_id: str,
    config: dict[str, Any] | None = None,
    output_root: str | Path | None = None,
) -> HybridParseResult:
    """Run the complete hybrid parser pipeline on a PDF.

    Pipeline:
    1. Check parser availability
    2. Quick-scan PDF with PyMuPDF → PDF type classification
    3. Route to appropriate parsers based on type and availability
    4. Merge outputs into final result
    5. Score quality and save manifest

    Args:
        pdf_path: Path to the PDF file.
        paper_id: Unique paper identifier.
        config: Optional config overrides (defaults from workflow_config.yaml).
        output_root: Project root directory (auto-detected if None).

    Returns:
        HybridParseResult with all parser outputs, quality report, and manifest path.
    """
    root = Path(output_root) if output_root else _resolve_root()
    pdf_path = Path(pdf_path)

    # ── Load config ──
    if config is None:
        wf_path = root / "Config" / "workflow_config.yaml"
        if wf_path.exists():
            config = _load_yaml_safe(wf_path).get("hybrid_parser", {})
        else:
            config = {}

    use_grobid = config.get("use_grobid", True)
    use_opendataloader = config.get("use_opendataloader", True)
    use_marker = config.get("use_marker", False)  # Default: disabled
    use_pymupdf = config.get("use_pymupdf", True)

    # ── Check availability ──
    avail = check_parser_availability(root)

    # ── Step 1: PyMuPDF scan ──
    scan_output = None
    scan_report = None
    pdf_type = PDFType.UNKNOWN

    if use_pymupdf and avail.pymupdf_available:
        scan_output = run_pymupdf_scan(pdf_path, paper_id, root)
        # Try to load scan report from file
        report_path = root / "02_Parse" / "reports" / "pymupdf" / f"{paper_id}.json"
        if report_path.exists():
            try:
                import json
                raw = json.loads(report_path.read_text(encoding="utf-8"))
                from scientra.parsers.types import PDFScanReport
                scan_report = PDFScanReport(
                    page_count=raw.get("page_count", 0),
                    has_text_layer=raw.get("has_text_layer", False),
                    text_length=raw.get("text_length", 0),
                    image_count=raw.get("image_count", 0),
                    suspected_scanned_pdf=raw.get("suspected_scanned_pdf", False),
                    pdf_type=PDFType(raw.get("pdf_type", "unknown")),
                    file_size_bytes=raw.get("file_size_bytes", 0),
                )
                pdf_type = scan_report.pdf_type
            except Exception:
                pass
    else:
        scan_output = None  # Will be handled gracefully

    # ── Step 2: Route based on PDF type ──
    grobid_out = None
    od_out = None
    marker_out = None
    pymupdf_fig_out = None

    if pdf_type == PDFType.SCANNED_PDF:
        # Scanned PDF — minimal processing, flag as low quality
        if use_pymupdf and avail.pymupdf_available:
            pymupdf_fig_out = extract_pymupdf_figures(pdf_path, paper_id, root)
        # Skip text-based parsers for scanned PDFs

    elif pdf_type == PDFType.SUPPLEMENTARY_PDF:
        # Supplementary — OpenDataLoader + PyMuPDF (no GROBID needed)
        if use_opendataloader and avail.opendataloader_available:
            od_out = run_opendataloader(pdf_path, paper_id, root)
        if use_pymupdf and avail.pymupdf_available:
            pymupdf_fig_out = extract_pymupdf_figures(pdf_path, paper_id, root)

    else:
        # normal_paper, table_heavy_pdf, image_heavy_pdf, unknown
        # — Run all available parsers

        if use_grobid and avail.grobid_available:
            grobid_out = run_grobid_metadata(pdf_path, paper_id, root)
        else:
            grobid_out = None  # skipped gracefully by adapter, but we can skip the call

        if use_opendataloader and avail.opendataloader_available:
            od_out = run_opendataloader(pdf_path, paper_id, root)

        if use_marker and avail.marker_available:
            marker_out = run_marker(pdf_path, paper_id, root)

        if use_pymupdf and avail.pymupdf_available:
            pymupdf_fig_out = extract_pymupdf_figures(pdf_path, paper_id, root)

    # ── Step 3: Score quality ──
    # Collect metadata from GROBID output if available
    metadata = None
    if grobid_out and grobid_out.status == ParserStatus.SUCCESS:
        meta_path = root / "02_Parse" / "reports" / "grobid" / f"{paper_id}_metadata.json"
        if meta_path.exists():
            try:
                import json
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Collect markdown text for scoring
    markdown_text = None
    for md_dir_name in ("opendataloader", "marker"):
        md_path = root / "02_Parse" / "markdown" / md_dir_name / f"{paper_id}.md"
        if md_path.exists():
            try:
                markdown_text = md_path.read_text(encoding="utf-8")
                break
            except Exception:
                pass

    # Collect layout data
    layout_data = None
    layout_path = root / "02_Parse" / "layout" / "opendataloader" / f"{paper_id}.json"
    if layout_path.exists():
        try:
            import json
            layout_data = json.loads(layout_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    all_outputs_raw = [o for o in [grobid_out, od_out, marker_out, scan_output, pymupdf_fig_out] if o is not None]
    all_outputs_dicts = [o.to_dict() for o in all_outputs_raw]

    quality_report = score_parse_result(
        paper_id=paper_id,
        parser_outputs=all_outputs_dicts,
        root=root,
        metadata=metadata,
        markdown_text=markdown_text,
        layout_data=layout_data,
    )

    # ── Step 4: Merge ──
    result = merge_parser_outputs(
        paper_id=paper_id,
        grobid_output=grobid_out,
        opendataloader_output=od_out,
        marker_output=marker_out,
        pymupdf_output=scan_output,
        quality_report=quality_report,
        scan_report=scan_report,
        pdf_path=str(pdf_path),
        output_root=root,
        config=config,
    )

    return result
