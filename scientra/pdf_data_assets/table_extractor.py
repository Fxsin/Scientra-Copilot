"""
Table Extractor — multi-strategy table caption extraction from raw text.

Phase 2A: Uses raw_text files (03_Summary/raw_text/) as primary source.
Extracts "Table N. Caption text..." patterns from within paragraphs.
No OCR. No LLM. No complex table structure parsing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class TableExtractor:
    """Multi-strategy table extractor using raw_text files as primary source."""

    MIN_CAPTION = 30
    MAX_CAPTION = 2500

    # Patterns for table label identification
    TABLE_LABEL_PATTERNS = [
        # "Table 1", "Table 2A", "Table S1"
        re.compile(
            r'(?:Supplementary\s+)?(?:Table|TABLE|Tab\.?)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)\s*\.',
            re.IGNORECASE
        ),
        # "Supplementary Table S1"
        re.compile(
            r'Supplementary\s+(?:Table|TABLE|Tab\.?)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)\s*\.',
            re.IGNORECASE
        ),
    ]

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.raw_text_dir = self.root / "03_Summary" / "raw_text"

    def extract(self, paper_id: str) -> list[dict[str, Any]]:
        """Extract table captions from raw text. Falls back to reference-only if no captions found."""
        text = self._load_raw_text(paper_id)
        if text:
            tables = self._extract_captions(text)
            if tables:
                return tables
        return self._extract_reference_only(paper_id)

    def _extract_captions(self, text: str) -> list[dict[str, Any]]:
        """Find 'Table N. Caption...' in text and extract caption content."""
        tables: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Find all "Table N." / "Table N:" positions using the primary pattern
        # Matches: "Table 1.", "Table S1:", "TABLE 1.", "Supplementary Table S1.", "Tab. 1:"
        table_starts = list(re.finditer(
            r'(?:Supplementary\s+)?(?:Table|TABLE|Tab\.?)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)\s*[.:]',
            text, re.IGNORECASE
        ))

        for i, m in enumerate(table_starts):
            number = m.group(1).strip()
            label = m.group(0).strip().rstrip(".")

            # Canonical dedup
            canonical = number.upper().replace(" ", "")
            if canonical in seen:
                continue
            seen.add(canonical)

            # Determine full table label (e.g. "Table 1" or "Supplementary Table S1")
            full_label = self._normalize_label(label, number)

            # Extract caption: from after "Table N." to next "Table/Figure M." or section break
            cap_start = m.end()
            if i + 1 < len(table_starts):
                cap_end = table_starts[i + 1].start()
            else:
                cap_end = min(len(text), cap_start + self.MAX_CAPTION)

            caption_raw = text[cap_start:cap_end].strip()

            # Trim at natural boundaries
            caption_raw = self._trim_caption(caption_raw)

            # Clean whitespace
            caption = re.sub(r'\s+', ' ', caption_raw).strip()

            # Skip if too short to be a real caption
            if len(caption) < 15:
                continue

            # Quality assessment
            cap_len = len(caption)
            if cap_len < self.MIN_CAPTION:
                quality = "low"
            elif cap_len < 100:
                quality = "medium"
            else:
                quality = "high"

            source = "plain_text_caption"

            tables.append({
                "table_label": full_label,
                "table_number": number,
                "caption": caption[:self.MAX_CAPTION],
                "source_text": caption[:self.MAX_CAPTION],
                "caption_quality": quality,
                "caption_source": source,
                "extraction_method": source,
                "confidence": "high" if quality == "high" else "medium" if quality == "medium" else "low",
            })

        return tables

    def _normalize_label(self, raw_label: str, number: str) -> str:
        """Normalize table label to consistent format."""
        label_lower = raw_label.lower().strip()

        if "supplementary" in label_lower:
            if number.upper().startswith("S"):
                return f"Supplementary Table {number}"
            else:
                return f"Supplementary Table S{number}"
        else:
            return f"Table {number}"

    def _trim_caption(self, text: str) -> str:
        """Trim caption at natural end boundaries."""
        stop_patterns = [
            # Next section header (Capitalized words followed by newline)
            r'\n\s*\n\s*(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5}\s*\n)',
            # References / Acknowledgements / common ending sections
            r'\n\s*(?:REFERENCES|ACKNOWLEDGMENTS|ACKNOWLEDGEMENTS|Funding|Conflicts|Author Contributions|Competing interests|Data Availability|Supplementary Information)\b',
            # Next Table or Figure label
            r'\n\s*(?:Table\s+\d+|TABLE\s+\d+|Tab\.?\s+\d+|Figure\s+\d+|Fig\.?\s+\d+|Supplementary\s+Table\s+\w+|Supplementary\s+Figure\s+\w+)\.',
            # Dense numeric data (table body likely)
            r'\n\s*\d+\.\d+\s*\(',
            # Abbreviations list
            r'\n\s*(?:Abbreviations|Acronyms|Nomenclature)\b',
            # Footnotes
            r'\n\s*\*[^*]',
        ]
        end_pos = len(text)
        for pat in stop_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m and m.start() < end_pos:
                end_pos = m.start()
        return text[:end_pos].strip()

    def _extract_reference_only(self, paper_id: str) -> list[dict[str, Any]]:
        """Fallback: table labels from evidence references only."""
        text = self._gather_evidence_text(paper_id)
        if not text:
            return []
        tables: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r'(?:Supplementary\s+)?(?:Tab\.?|Table|TABLE)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)',
            text, re.IGNORECASE
        ):
            number = m.group(1).strip()
            canonical = number.upper().replace(" ", "")
            if canonical in seen:
                continue
            seen.add(canonical)
            label = f"Table {number}"
            tables.append({
                "table_label": label,
                "table_number": number,
                "caption": "",
                "source_text": m.group(0),
                "caption_quality": "none",
                "caption_source": "reference_only",
                "extraction_method": "reference_only",
                "confidence": "low",
            })
        return tables

    def _load_raw_text(self, paper_id: str) -> str:
        """Load raw_text file for the paper."""
        if not self.raw_text_dir.exists():
            return ""
        pid_hash = paper_id[-12:] if len(paper_id) >= 12 else paper_id
        for f in self.raw_text_dir.glob("*.txt"):
            if pid_hash in f.name:
                try:
                    return f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
        return ""

    def _gather_evidence_text(self, paper_id: str) -> str:
        """Gather text from evidence.json fields for reference-only extraction."""
        ev_path = self.root / "03_Evidence" / paper_id / "evidence.json"
        if not ev_path.exists():
            return ""
        try:
            ev = json.loads(ev_path.read_text(encoding="utf-8"))
            parts = []
            for field in ["methods", "key_results", "core_findings", "discussion_points"]:
                items = ev.get(field, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            for k in ["result", "finding", "point", "quote", "name"]:
                                t = str(item.get(k, ""))
                                if len(t) > 20:
                                    parts.append(t)
            return "\n".join(parts)
        except Exception:
            return ""
