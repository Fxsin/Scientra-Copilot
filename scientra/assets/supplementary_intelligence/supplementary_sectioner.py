"""Supplementary Sectioner — detect sections in supplementary text.

Recognizes: Supplementary Methods, Supplementary Results, Supplementary Figures,
Supplementary Tables, Supplementary Notes, Supplementary References, Appendix,
Protocol, Dataset Description, etc.
"""

from __future__ import annotations

import re
from typing import Any

# Section detection patterns
SECTION_PATTERNS: list[tuple[str, list[str], str]] = [
    ("supplementary_methods", [
        r"(?:supplementary|additional)\s+methods?",
        r"(?:supplementary|additional)\s+materials?\s+and\s+methods?",
        r"supplementary\s+experimental\s+procedures?",
        r"extended\s+methods?",
        r"detailed\s+methods?",
    ], "Supplementary Methods"),
    ("supplementary_results", [
        r"(?:supplementary|additional)\s+results?",
        r"supplementary\s+data\s+analys",
        r"extended\s+results?",
        r"additional\s+findings?",
    ], "Supplementary Results"),
    ("supplementary_figures", [
        r"(?:supplementary|additional)\s+figures?",
        r"supplementary\s+figure\s+legends?",
        r"suppl?(?:ementary)?\s*\.?\s*fig(?:ures?|\.)\s",
    ], "Supplementary Figures"),
    ("supplementary_tables", [
        r"(?:supplementary|additional)\s+tables?",
        r"supplementary\s+table\s+legends?",
        r"suppl?(?:ementary)?\s*\.?\s*tab(?:les?|\.)\s",
    ], "Supplementary Tables"),
    ("supplementary_notes", [
        r"(?:supplementary|additional)\s+notes?",
        r"supplementary\s+discussion",
        r"additional\s+discussion",
        r"supporting\s+notes?",
    ], "Supplementary Notes"),
    ("supplementary_references", [
        r"(?:supplementary\s+)?references?",
        r"bibliography",
        r"works\s+cited",
        r"literature\s+cited",
    ], "Supplementary References"),
    ("appendix", [
        r"appendix\s+[A-Z]",
        r"appendices",
        r"supplementary\s+appendix",
    ], "Appendix"),
    ("protocol", [
        r"protocol[s]?",
        r"experimental\s+protocol",
        r"step[-\s]by[-\s]step\s+protocol",
        r"detailed\s+protocol",
    ], "Protocol"),
    ("dataset_description", [
        r"dataset\s+descriptions?",
        r"data\s+descriptions?",
        r"data\s+dictionary",
        r"data\s+columns?\s+descriptions?",
        r"variable\s+descriptions?",
        r"supplementary\s+data\s+descriptions?",
    ], "Dataset Description"),
]


def detect_sections(raw_text: str) -> list[dict[str, Any]]:
    """Detect sections in supplementary text.

    Args:
        raw_text: Full text of the supplementary file.

    Returns:
        List of section dicts with offsets and types.
    """
    if not raw_text or not raw_text.strip():
        return []

    sections: list[dict[str, Any]] = []
    lines = raw_text.split("\n")

    # Strategy 1: Find section headers by pattern matching
    header_candidates = _find_headers(lines)

    # Strategy 2: If no headers found, try whole-text pattern matching
    if not header_candidates:
        return _fallback_sectioning(raw_text)

    # Build sections from header positions
    for i, (line_idx, header_text) in enumerate(header_candidates):
        # Determine section boundaries
        start_line = line_idx
        end_line = header_candidates[i + 1][0] if i + 1 < len(header_candidates) else len(lines)

        section_text = "\n".join(lines[start_line:end_line]).strip()
        section_type, confidence = _classify_section(header_text, section_text)

        # Calculate char offsets
        start_offset = _line_idx_to_char_offset(lines, start_line)
        end_offset = _line_idx_to_char_offset(lines, end_line)

        sections.append({
            "section_id": f"sec_{i:03d}",
            "paper_id": "",
            "asset_id": "",
            "section_title": header_text.strip(),
            "section_type": section_type,
            "text": section_text[:10000],  # Limit section text
            "start_offset": start_offset,
            "end_offset": min(end_offset, len(raw_text)),
            "confidence": round(confidence, 2),
        })

    return sections


def _find_headers(lines: list[str]) -> list[tuple[int, str]]:
    """Find likely section header lines."""
    candidates: list[tuple[int, str]] = []

    header_patterns = [
        re.compile(r"^#{1,4}\s+(.+)$"),                       # Markdown headers
        re.compile(r"^([A-Z][A-Za-z\s\-]{3,60})$"),          # ALL CAPS or Title Case lines
        re.compile(r"^(?:Supplementary|Additional|Extended)\s+\w+", re.IGNORECASE),
        re.compile(r"^(?:Appendix|Protocol|Dataset|Supporting)\s+\w*", re.IGNORECASE),
        re.compile(r"^\d+\.?\s+(?:Supplementary|Additional)?\s*\w+", re.IGNORECASE),
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) < 5 or len(stripped) > 120:
            continue

        # Skip lines that look like regular sentences
        if stripped.endswith(".") and len(stripped.split()) > 8:
            continue

        for pat in header_patterns:
            match = pat.match(stripped)
            if match:
                title = match.group(1) if match.lastindex else stripped
                candidates.append((i, title))
                break

    # Deduplicate adjacent candidates
    filtered = []
    for i, (idx, title) in enumerate(candidates):
        if i == 0 or idx - candidates[i - 1][0] > 3:
            filtered.append((idx, title))

    return filtered


def _classify_section(header: str, text: str) -> tuple[str, float]:
    """Classify section type from header and content."""
    header_lower = header.lower()
    text_sample = text[:500].lower() if text else ""

    for stype, patterns, _ in SECTION_PATTERNS:
        for pat in patterns:
            if re.search(pat, header_lower, re.IGNORECASE):
                return (stype, 0.85)
            if re.search(pat, text_sample, re.IGNORECASE):
                return (stype, 0.60)

    # Additional heuristic checks
    if re.search(r"\breferences?\b", header_lower) and not re.search(r"methods?|results?|figures?|tables?", header_lower):
        return ("supplementary_references", 0.75)

    if re.search(r"methods?|materials?", header_lower):
        return ("supplementary_methods", 0.50)
    if re.search(r"results?|findings?", header_lower):
        return ("supplementary_results", 0.50)
    if re.search(r"figures?|fig\.", header_lower):
        return ("supplementary_figures", 0.50)
    if re.search(r"tables?|tab\.", header_lower):
        return ("supplementary_tables", 0.50)

    return ("unknown", 0.30)


def _line_idx_to_char_offset(lines: list[str], line_idx: int) -> int:
    """Convert line index to character offset."""
    offset = 0
    for i in range(min(line_idx, len(lines))):
        offset += len(lines[i]) + 1  # +1 for newline
    return offset


def _fallback_sectioning(raw_text: str) -> list[dict[str, Any]]:
    """Fallback: create a single section covering the entire text."""
    text = raw_text[:10000]
    stype, confidence = _classify_section("", text)

    return [{
        "section_id": "sec_000",
        "paper_id": "",
        "asset_id": "",
        "section_title": "Supplementary Content",
        "section_type": stype if stype != "unknown" else "supplementary_notes",
        "text": text,
        "start_offset": 0,
        "end_offset": min(len(raw_text), 10000),
        "confidence": 0.20,
    }]
