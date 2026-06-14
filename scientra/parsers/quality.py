"""
Hybrid PDF Parser — Quality Scoring.

Evaluates parse output quality across multiple dimensions:
metadata, markdown, layout, references, figures, and tables.
Produces a ParserQualityReport with scores, problems, and recommendations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.parsers.types import ParserQualityReport


# Key section heading patterns that should appear in a well-structured paper
IMPORTANT_SECTIONS = [
    r"\bintroduction\b",
    r"\bmethods?\b",
    r"\bmaterials?\b",
    r"\bresults?\b",
    r"\bdiscussion\b",
    r"\bconclusion\b",
    r"\babstract\b",
    r"\breferences?\b",
    r"\bbackground\b",
    r"\brelated\s+work\b",
]

# Characters/patterns that indicate encoding issues or garbled text
GARBLED_PATTERNS = [
    "���",
    "�",
    "�",
    "Ã¢",
    "Ã©",
    "Ã±",
    "â",
    "\\\\x[0-9a-f]{2}",
]


def score_parse_result(
    paper_id: str,
    parser_outputs: list[dict[str, Any]],
    root: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
    markdown_text: str | None = None,
    layout_data: dict[str, Any] | None = None,
) -> ParserQualityReport:
    """Score the quality of a hybrid parse result.

    Args:
        paper_id: The paper identifier.
        parser_outputs: List of parser output dicts from all adapters.
        root: Project root (for loading intermediate files).
        metadata: Optional pre-loaded metadata dict.
        markdown_text: Optional pre-loaded markdown text.
        layout_data: Optional pre-loaded layout/bbox data.

    Returns a ParserQualityReport with scores, problems, and recommendations.
    """
    problems: list[str] = []
    recommendations: list[str] = []

    root = Path(root) if root else Path(".")

    # ── Metadata Score ──
    metadata_score = _score_metadata(metadata, problems, recommendations)

    # ── Markdown Score ──
    markdown_score = _score_markdown(markdown_text, problems, recommendations)

    # ── Layout Score ──
    layout_score = _score_layout(layout_data, problems, recommendations)

    # ── Reference Score ──
    reference_score = _score_references(metadata, problems, recommendations)

    # ── Figure Score ──
    figure_score = _score_figures(parser_outputs, root, paper_id, problems, recommendations)

    # ── Table Score ──
    table_score = _score_tables(parser_outputs, root, paper_id, problems, recommendations)

    # ── Overall Score (weighted average) ──
    weights = {
        "metadata": 0.25,
        "markdown": 0.30,
        "layout": 0.15,
        "reference": 0.10,
        "figure": 0.10,
        "table": 0.10,
    }
    overall = (
        metadata_score * weights["metadata"]
        + markdown_score * weights["markdown"]
        + layout_score * weights["layout"]
        + reference_score * weights["reference"]
        + figure_score * weights["figure"]
        + table_score * weights["table"]
    )

    return ParserQualityReport(
        metadata_score=round(metadata_score, 2),
        markdown_score=round(markdown_score, 2),
        layout_score=round(layout_score, 2),
        reference_score=round(reference_score, 2),
        figure_score=round(figure_score, 2),
        table_score=round(table_score, 2),
        overall_score=round(overall, 2),
        problems=problems,
        recommendations=recommendations,
    )


def _score_metadata(
    metadata: dict[str, Any] | None,
    problems: list[str],
    recommendations: list[str],
) -> float:
    """Score metadata quality."""
    if not metadata:
        problems.append("No metadata extracted.")
        recommendations.append("Run GROBID metadata extraction or provide manual metadata.")
        return 0.0

    score = 0.0
    if metadata.get("title"):
        score += 0.30
    else:
        problems.append("Missing title in metadata.")
        recommendations.append("Ensure GROBID can extract the paper title.")

    if metadata.get("abstract"):
        score += 0.20
    else:
        problems.append("Missing abstract in metadata.")

    if metadata.get("doi"):
        score += 0.15
    if metadata.get("authors") and len(metadata.get("authors", [])) > 0:
        score += 0.15
    else:
        problems.append("No authors extracted.")

    if metadata.get("year"):
        score += 0.10
    if metadata.get("journal"):
        score += 0.10

    return min(score, 1.0)


def _score_markdown(
    markdown_text: str | None,
    problems: list[str],
    recommendations: list[str],
) -> float:
    """Score markdown quality."""
    if not markdown_text:
        problems.append("No markdown output generated.")
        recommendations.append("Ensure OpenDataLoader PDF or Marker is available for markdown extraction.")
        return 0.0

    text = markdown_text
    score = 0.0

    # Length check
    if len(text) > 5000:
        score += 0.25
    elif len(text) > 1000:
        score += 0.15
    else:
        problems.append("Markdown text is very short (<1000 chars) — likely incomplete parsing.")
        recommendations.append("Check if the PDF has a text layer. Consider OCR for scanned PDFs.")

    # Section heading check
    import re
    text_lower = text.lower()
    found_sections = 0
    for pattern in IMPORTANT_SECTIONS:
        if re.search(pattern, text_lower):
            found_sections += 1
    if found_sections >= 5:
        score += 0.35
    elif found_sections >= 3:
        score += 0.25
    elif found_sections >= 1:
        score += 0.10
    else:
        problems.append("Few or no recognized section headings in markdown.")
        recommendations.append("The parser may not be preserving document structure. Try Marker as fallback.")

    # Garbled text check
    garbled_count = 0
    for pattern in GARBLED_PATTERNS:
        import re as re_mod
        matches = re_mod.findall(pattern, text)
        garbled_count += len(matches)
    if garbled_count == 0:
        score += 0.25
    elif garbled_count < 5:
        score += 0.15
    else:
        problems.append(f"Detected {garbled_count} garbled-text artifacts — encoding issues likely.")
        recommendations.append("Check PDF encoding. Try a different parser.")

    # Figure/table mention check
    if re.search(r"\bfigure?\b", text_lower) and re.search(r"\btable?\b", text_lower):
        score += 0.15

    return min(score, 1.0)


def _score_layout(
    layout_data: dict[str, Any] | None,
    problems: list[str],
    recommendations: list[str],
) -> float:
    """Score layout/bbox data quality."""
    if not layout_data:
        problems.append("No layout/bbox data available.")
        recommendations.append("Enable OpenDataLoader PDF for layout extraction.")
        return 0.0

    score = 0.0
    # Check for page-level data
    if isinstance(layout_data, dict):
        pages = layout_data.get("pages", layout_data.get("blocks", []))
        if isinstance(pages, list) and len(pages) > 0:
            score += 0.5
        else:
            # Maybe the layout data itself is the list of pages
            if isinstance(layout_data, list) and len(layout_data) > 0:
                score += 0.5

        # Check for bbox info
        has_bbox = False
        try:
            flat = json.dumps(layout_data)
            has_bbox = '"bbox"' in flat or '"bounding_box"' in flat or '"box"' in flat
        except Exception:
            pass
        if has_bbox:
            score += 0.3

        # Check for reading order
        has_order = False
        try:
            flat = json.dumps(layout_data)
            has_order = '"order"' in flat or '"reading_order"' in flat or '"index"' in flat
        except Exception:
            pass
        if has_order:
            score += 0.2
    else:
        problems.append("Layout data is not in expected dict/list format.")

    return min(score, 1.0)


def _score_references(
    metadata: dict[str, Any] | None,
    problems: list[str],
    recommendations: list[str],
) -> float:
    """Score reference extraction quality."""
    if not metadata:
        return 0.0

    refs = metadata.get("references", [])
    if not refs:
        problems.append("No references extracted.")
        recommendations.append("Enable GROBID citation extraction.")
        return 0.0

    score = 0.0
    ref_count = len(refs)
    if ref_count >= 20:
        score += 0.4
    elif ref_count >= 10:
        score += 0.25
    elif ref_count >= 5:
        score += 0.15
    else:
        problems.append(f"Very few references ({ref_count}) — likely incomplete extraction.")
        recommendations.append("Check GROBID citation extraction settings.")

    # Check reference quality (do they have titles?)
    titled_refs = sum(1 for r in refs if isinstance(r, dict) and r.get("title"))
    if ref_count > 0 and titled_refs / ref_count > 0.7:
        score += 0.4
    elif ref_count > 0 and titled_refs / ref_count > 0.3:
        score += 0.2
    else:
        problems.append("References lack titles — authors/year may be incomplete.")
        recommendations.append("GROBID may need consolidateCitations enabled for better reference parsing.")

    # Year coverage
    dated_refs = sum(1 for r in refs if isinstance(r, dict) and r.get("year"))
    if ref_count > 0 and dated_refs / ref_count > 0.5:
        score += 0.2

    return min(score, 1.0)


def _score_figures(
    parser_outputs: list[dict[str, Any]],
    root: Path,
    paper_id: str,
    problems: list[str],
    recommendations: list[str],
) -> float:
    """Score figure extraction quality."""
    figure_outputs = [po for po in parser_outputs if po.get("output_type") == "figures"]
    if not figure_outputs:
        problems.append("No figure extraction attempted.")
        recommendations.append("Enable PyMuPDF figure extraction or OpenDataLoader figure detection.")
        return 0.0

    score = 0.0
    for po in figure_outputs:
        if po.get("status") == "success":
            paths = po.get("output_paths", [])
            if paths:
                # Check if figure directory has images
                fig_dir = Path(paths[0]) if paths else None
                if fig_dir and fig_dir.is_dir():
                    image_files = list(fig_dir.glob("*")) if fig_dir.exists() else []
                    img_count = len([f for f in image_files if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".tiff", ".bmp")])
                    if img_count >= 5:
                        score += 0.6
                    elif img_count > 0:
                        score += 0.4
                    else:
                        problems.append("Figure directory exists but contains no images.")
                elif fig_dir and str(fig_dir).endswith(".json"):
                    score += 0.3  # Structured figure data

        elif po.get("status") == "skipped":
            problems.append(f"Figure parser '{po.get('parser_name')}' was skipped.")
        elif po.get("status") == "failed":
            problems.append(f"Figure parser '{po.get('parser_name')}' failed: {po.get('errors', [])}")

    # Check if figures appear in markdown (indirect detection)
    try:
        md_path = root / "02_Parse" / "markdown" / "final" / f"{paper_id}.md"
        if md_path.exists():
            md_text = md_path.read_text(encoding="utf-8")
            import re
            if re.search(r"!\[.*\]\(.*\)", md_text):
                score += 0.2
            if re.search(r"\bfig(?:ure)?\s*\d", md_text, re.IGNORECASE):
                score += 0.2
    except Exception:
        pass

    return min(score, 1.0)


def _score_tables(
    parser_outputs: list[dict[str, Any]],
    root: Path,
    paper_id: str,
    problems: list[str],
    recommendations: list[str],
) -> float:
    """Score table extraction quality."""
    table_outputs = [po for po in parser_outputs if po.get("output_type") == "tables"]
    if not table_outputs:
        problems.append("No table extraction attempted.")
        recommendations.append("Enable OpenDataLoader PDF table extraction.")
        return 0.0

    score = 0.0
    for po in table_outputs:
        if po.get("status") == "success":
            paths = po.get("output_paths", [])
            for p in paths:
                try:
                    data = json.loads(Path(p).read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        score += min(0.6, len(data) * 0.1)
                    elif isinstance(data, dict):
                        score += 0.3
                except Exception:
                    pass
        elif po.get("status") == "skipped":
            problems.append(f"Table parser '{po.get('parser_name')}' was skipped.")
        elif po.get("status") == "failed":
            problems.append(f"Table parser '{po.get('parser_name')}' failed.")

    # Check markdown for table syntax
    try:
        md_path = root / "02_Parse" / "markdown" / "final" / f"{paper_id}.md"
        if md_path.exists():
            md_text = md_path.read_text(encoding="utf-8")
            import re
            if re.search(r"\|.*\|.*\|", md_text):
                score += 0.2
            if re.search(r"\btable\s*\d", md_text, re.IGNORECASE):
                score += 0.2
    except Exception:
        pass

    return min(score, 1.0)
