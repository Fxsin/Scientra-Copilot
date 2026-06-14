"""
Hybrid PDF Parser — Output Merger.

Combines outputs from multiple parsers into a single final result.
Prioritizes: GROBID for metadata/references, OpenDataLoader for markdown/layout,
with Marker as fallback and PyMuPDF for figures.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.parsers.types import (
    HybridParseResult,
    OutputType,
    ParserOutput,
    ParserQualityReport,
    ParserStatus,
    PDFScanReport,
    PDFType,
)


def _resolve_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[2]


def _ensure_dir(target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    return target


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def merge_parser_outputs(
    paper_id: str,
    grobid_output: ParserOutput | None,
    opendataloader_output: ParserOutput | None,
    marker_output: ParserOutput | None,
    pymupdf_output: ParserOutput | None,
    quality_report: ParserQualityReport | None = None,
    scan_report: PDFScanReport | None = None,
    pdf_path: str = "",
    output_root: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> HybridParseResult:
    """Merge outputs from all parsers into a final HybridParseResult.

    Priority rules:
    - metadata → GROBID
    - references → GROBID
    - markdown → OpenDataLoader (fallback to Marker)
    - layout/bbox → OpenDataLoader
    - figures → OpenDataLoader structured (fallback to PyMuPDF)
    - tables → OpenDataLoader

    Saves:
    - 02_Parse/markdown/final/{paper_id}.md  — final markdown
    - 02_Parse/reports/hybrid/{paper_id}_parse_manifest.json — full manifest
    """
    root = Path(output_root) if output_root else _resolve_root()

    # Load config for defaults
    if config is None:
        config = {}
        wf_path = root / "Config" / "workflow_config.yaml"
        if wf_path.exists():
            config = _load_yaml_safe(wf_path).get("hybrid_parser", {})

    prefer_md = config.get("prefer_markdown_source", "opendataloader")
    fallback_md = config.get("fallback_markdown_source", "marker")

    result = HybridParseResult(
        paper_id=paper_id,
        pdf_path=pdf_path,
        pdf_type=scan_report.pdf_type if scan_report else PDFType.UNKNOWN,
        scan_report=scan_report,
    )

    all_outputs: list[ParserOutput] = []
    warnings: list[str] = []
    errors: list[str] = []

    # ── Determine metadata source ──
    if grobid_output and grobid_output.status == ParserStatus.SUCCESS:
        result.metadata_source = "grobid"
        all_outputs.append(grobid_output)
    elif grobid_output:
        result.metadata_source = "grobid_fallback"
        all_outputs.append(grobid_output)
        warnings.append("GROBID metadata extraction did not fully succeed.")
    else:
        result.metadata_source = "unknown"
        warnings.append("No GROBID metadata available. Metadata will be incomplete.")

    # ── Determine references source ──
    if grobid_output and grobid_output.status in (ParserStatus.SUCCESS, ParserStatus.FALLBACK):
        result.references_source = "grobid"
    else:
        result.references_source = "unknown"

    # ── Determine markdown source ──
    od_output = opendataloader_output
    mk_output = marker_output

    od_success = od_output and od_output.status == ParserStatus.SUCCESS
    mk_success = mk_output and mk_output.status == ParserStatus.SUCCESS

    if prefer_md == "opendataloader" and od_success:
        result.markdown_source = "opendataloader"
        if od_output:
            all_outputs.append(od_output)
    elif prefer_md == "marker" and mk_success:
        result.markdown_source = "marker"
        if mk_output:
            all_outputs.append(mk_output)
    elif od_success:
        result.markdown_source = "opendataloader"
        if od_output:
            all_outputs.append(od_output)
    elif mk_success:
        result.markdown_source = "marker"
        if mk_output:
            all_outputs.append(mk_output)
        warnings.append("OpenDataLoader markdown not available. Using Marker as fallback.")
    elif od_output and od_output.status == ParserStatus.FALLBACK:
        result.markdown_source = "opendataloader_fallback"
        if od_output:
            all_outputs.append(od_output)
    else:
        result.markdown_source = "none"
        errors.append("No markdown output available from any parser.")

    # Also add the non-primary markdown outputs for completeness
    if od_output and result.markdown_source not in ("opendataloader", "opendataloader_fallback"):
        all_outputs.append(od_output)
    if mk_output and result.markdown_source != "marker":
        all_outputs.append(mk_output)

    # ── Determine layout source ──
    if od_output and od_output.status == ParserStatus.SUCCESS:
        # Check if layout data was extracted
        has_layout = any("layout" in p for p in (od_output.output_paths or []))
        if has_layout:
            result.layout_source = "opendataloader"
        else:
            result.layout_source = "none"
            warnings.append("OpenDataLoader succeeded but no layout data found.")
    else:
        result.layout_source = "none"

    # ── Determine figures source ──
    pymupdf_fig = None
    od_fig = None
    for po in all_outputs:
        if po.parser_name == "pymupdf" and po.output_type == OutputType.FIGURES:
            pymupdf_fig = po
        elif po.parser_name == "opendataloader" and po.output_type == OutputType.FIGURES:
            od_fig = po

    if od_fig and od_fig.status == ParserStatus.SUCCESS:
        result.figures_source = "opendataloader"
    elif pymupdf_fig and pymupdf_fig.status == ParserStatus.SUCCESS:
        result.figures_source = "pymupdf"
        if pymupdf_fig not in all_outputs:
            all_outputs.append(pymupdf_fig)
    elif pymupdf_fig:
        result.figures_source = "pymupdf_fallback"
        if pymupdf_fig not in all_outputs:
            all_outputs.append(pymupdf_fig)
    else:
        result.figures_source = "none"

    # ── Determine tables source ──
    if od_output and od_output.status == ParserStatus.SUCCESS:
        result.tables_source = "opendataloader"
    else:
        result.tables_source = "none"

    # ── Add pymupdf scan output ──
    if pymupdf_output and pymupdf_output not in all_outputs:
        all_outputs.append(pymupdf_output)

    # ── Generate final markdown ──
    final_md_dir = _ensure_dir(root / "02_Parse" / "markdown" / "final")
    final_md_path = final_md_dir / f"{paper_id}.md"

    # Try to copy the best available markdown
    source_md_path = _find_best_markdown(paper_id, result.markdown_source, root)
    if source_md_path and source_md_path.exists():
        try:
            final_md_path.write_text(source_md_path.read_text(encoding="utf-8"), encoding="utf-8")
            result.final_markdown_path = str(final_md_path)
        except Exception as e:
            errors.append(f"Failed to write final markdown: {e}")
    else:
        errors.append("No source markdown found to create final output.")
        # Create an empty placeholder
        final_md_path.write_text(
            f"# {paper_id}\n\n> Hybrid parse could not produce markdown.\n"
            f"> Markdown source: {result.markdown_source}\n",
            encoding="utf-8",
        )
        result.final_markdown_path = str(final_md_path)

    # ── Generate manifest ──
    result.parser_outputs = all_outputs
    result.warnings = warnings
    result.errors = errors
    result.quality_report = quality_report

    manifest_dir = _ensure_dir(root / "02_Parse" / "reports" / "hybrid")
    manifest_path = manifest_dir / f"{paper_id}_parse_manifest.json"
    manifest_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    result.manifest_path = str(manifest_path)

    return result


def _find_best_markdown(paper_id: str, source: str, root: Path) -> Path | None:
    """Find the best available markdown file for a paper."""
    # Try in order of preference
    candidates: list[Path] = []

    if source.startswith("opendataloader"):
        candidates.append(root / "02_Parse" / "markdown" / "opendataloader" / f"{paper_id}.md")
    if source.startswith("marker"):
        candidates.append(root / "02_Parse" / "markdown" / "marker" / f"{paper_id}.md")

    # Fallback: try any available
    candidates.append(root / "02_Parse" / "markdown" / "opendataloader" / f"{paper_id}.md")
    candidates.append(root / "02_Parse" / "markdown" / "marker" / f"{paper_id}.md")

    for p in candidates:
        if p.exists():
            return p
    return None


def load_manifest(paper_id: str, root: str | Path | None = None) -> dict[str, Any] | None:
    """Load an existing hybrid parse manifest.

    Returns the parsed manifest dict, or None if not found.
    """
    root = Path(root) if root else _resolve_root()
    manifest_path = root / "02_Parse" / "reports" / "hybrid" / f"{paper_id}_parse_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
