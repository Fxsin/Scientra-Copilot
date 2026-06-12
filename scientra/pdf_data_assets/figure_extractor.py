"""
Figure Extractor — multi-strategy caption extraction from raw text.

Phase 1A: Uses raw_text files (03_Summary/raw_text/) as primary source.
Extracts "Figure N. Caption text..." patterns from within paragraphs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class FigureExtractor:
    """Multi-strategy figure extractor using raw_text files as primary source."""

    MIN_CAPTION = 30
    MAX_CAPTION = 2500

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.raw_text_dir = self.root / "03_Summary" / "raw_text"

    def extract(self, paper_id: str) -> list[dict[str, Any]]:
        text = self._load_raw_text(paper_id)
        if text:
            captions = self._extract_captions(text)
            if captions:
                return captions
        return self._extract_reference_only(paper_id)

    def _extract_captions(self, text: str) -> list[dict[str, Any]]:
        """Find 'Figure N. Caption...' in text and extract caption content."""
        figures: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Find all "Figure N." positions
        fig_starts = list(re.finditer(
            r'(?:Supplementary\s+)?(?:Figure|Fig\.?|FIGURE)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)\s*\.',
            text, re.IGNORECASE
        ))

        for i, m in enumerate(fig_starts):
            number = m.group(1).strip()
            label = m.group(0).strip().rstrip(".")

            canonical = number.upper().replace(" ", "")
            if canonical in seen:
                continue
            seen.add(canonical)

            # Extract caption: from after "Figure N." to the next "Figure/Table M." or section break
            cap_start = m.end()
            if i + 1 < len(fig_starts):
                cap_end = fig_starts[i + 1].start()
            else:
                cap_end = min(len(text), cap_start + self.MAX_CAPTION)

            caption_raw = text[cap_start:cap_end].strip()

            # Trim at natural boundaries
            caption_raw = self._trim_caption(caption_raw)

            # Clean
            caption = re.sub(r'\s+', ' ', caption_raw).strip()

            # Skip if too short to be a real caption
            if len(caption) < 15:
                continue

            # Quality
            cap_len = len(caption)
            if cap_len < self.MIN_CAPTION:
                quality = "low"
            elif cap_len < 100:
                quality = "medium"
            else:
                quality = "high"

            source = "plain_text_caption"

            figures.append({
                "figure_label": label,
                "figure_number": number,
                "caption": caption[:self.MAX_CAPTION],
                "source_text": caption[:self.MAX_CAPTION],
                "caption_quality": quality,
                "caption_source": source,
                "extraction_method": source,
                "panels": self._detect_panels(number),
                "confidence": "high" if quality == "high" else "medium" if quality == "medium" else "low",
            })

        return figures

    def _trim_caption(self, text: str) -> str:
        """Trim caption at natural end boundaries."""
        # Stop before: next Figure/Table reference, section headers, table data
        stop_patterns = [
            r'\n\s*\n\s*(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5}\s*\n)',  # Section header
            r'\n\s*(?:REFERENCES|ACKNOWLEDGMENTS|Funding|Conflicts|Author Contributions)\b',
            r'\n\s*(?:Table\s+\d+|Figure\s+\d+|Fig\.?\s+\d+)\.',
            r'\n\s*\d+\.\d+\s*\(',  # Table values like "1.69 (1.36-2.04)"
        ]
        end_pos = len(text)
        for pat in stop_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m and m.start() < end_pos:
                end_pos = m.start()
        return text[:end_pos].strip()

    def _extract_reference_only(self, paper_id: str) -> list[dict[str, Any]]:
        """Fallback: labels from evidence references only."""
        text = self._gather_evidence_text(paper_id)
        if not text:
            return []
        figures: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(r'(?:Fig\.?|Figure|FIGURE)\s+(\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)', text, re.IGNORECASE):
            number = m.group(1).strip()
            if number in seen:
                continue
            seen.add(number)
            label = f"Figure {number}"
            figures.append({
                "figure_label": label, "figure_number": number,
                "caption": "", "source_text": m.group(0),
                "caption_quality": "none", "caption_source": "reference_only",
                "extraction_method": "reference_only",
                "panels": self._detect_panels(number), "confidence": "low",
            })
        return figures

    def _load_raw_text(self, paper_id: str) -> str:
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

    def _detect_panels(self, number: str) -> list[str]:
        range_match = re.match(r'(\d+)([A-Za-z])[–\-]([A-Za-z])', number)
        if range_match:
            s, e = ord(range_match.group(2).upper()), ord(range_match.group(3).upper())
            return [chr(c) for c in range(s, e + 1)]
        letter_match = re.match(r'(\d+)([A-Za-z])', number)
        if letter_match:
            return [letter_match.group(2).upper()]
        return []
