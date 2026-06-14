"""Citation Parser — extract Figure/Table/Dataset/Supplementary citations from text sources.

Scans body text, evidence chunks, and summaries for asset references.
Uses regex patterns to identify citation mentions with surrounding context.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from scientra.assets.linking.label_normalizer import normalize_label

# ── Citation patterns ──

_CITATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Figure references
    (
        re.compile(
            r"(?:(?:Supplementary|Suppl\.?|Appendix|App\.?)\s+)?"
            r"(?:Fig\.?|Figure|FIG\.?|Figs\.?|Figures)\s+"
            r"(S?\d+(?:[A-Za-z])?(?:[–\-]\d+[A-Za-z]?)?"
            r"(?:,\s*(?:and\s+)?\d+[A-Za-z]?)*)",
            re.IGNORECASE,
        ),
        "figure",
    ),
    # Table references
    (
        re.compile(
            r"(?:(?:Supplementary|Suppl\.?|Appendix|App\.?)\s+)?"
            r"(?:Table|TAB\.?|Tables)\s+"
            r"(S?\d+(?:[A-Za-z])?(?:[–\-]\d+[A-Za-z]?)?"
            r"(?:,\s*(?:and\s+)?\d+[A-Za-z]?)*)",
            re.IGNORECASE,
        ),
        "table",
    ),
    # Dataset/Data references
    (
        re.compile(
            r"(?:(?:Supplementary|Suppl\.?|Appendix|App\.?)\s+)?"
            r"(?:Data|Dataset|DATASET)\s+"
            r"(S?\d+(?:[A-Za-z])?)",
            re.IGNORECASE,
        ),
        "dataset",
    ),
    # Supplementary general references
    (
        re.compile(
            r"(?:Supplementary\s+(?:Material|Information|Data|File|Note|Text|Methods|Results|Discussion))"
            r"|(?:SI\s+Appendix)"
            r"|(?:Supporting\s+Information)"
            r"|(?:Additional\s+[Ff]ile\s+\d+)",
            re.IGNORECASE,
        ),
        "supplementary",
    ),
    # Appendix references
    (
        re.compile(
            r"(?:Appendix|App\.?)\s+([A-Z]\d*)",
            re.IGNORECASE,
        ),
        "supplementary",
    ),
]

# Context window size (chars) for extracting surrounding text
CONTEXT_WINDOW = 200


class CitationParser:
    """Extract asset citations from text sources for a paper."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            # Auto-detect project root
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()

    def parse_all_sources(self, paper_id: str) -> list[dict[str, Any]]:
        """Parse all available text sources for a paper.

        Returns a list of citation mention dicts.
        """
        mentions: list[dict[str, Any]] = []

        # Source 1: Body text (02_Content)
        body_mentions = self._parse_body_text(paper_id)
        mentions.extend(body_mentions)

        # Source 2: Evidence chunks (03_Evidence)
        evidence_mentions = self._parse_evidence(paper_id)
        mentions.extend(evidence_mentions)

        # Source 3: Summary (03_Summary)
        summary_mentions = self._parse_summary(paper_id)
        mentions.extend(summary_mentions)

        return mentions

    def _parse_body_text(self, paper_id: str) -> list[dict[str, Any]]:
        """Parse body text files for the paper."""
        mentions: list[dict[str, Any]] = []
        content_dir = self.root / "02_Content" / paper_id

        if not content_dir.exists():
            return mentions

        for txt_file in sorted(content_dir.glob("*.txt")):
            try:
                text = txt_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            section = txt_file.stem
            file_mentions = self._extract_from_text(
                text, paper_id, "body_text", section, section,
            )
            mentions.extend(file_mentions)

        return mentions

    def _parse_evidence(self, paper_id: str) -> list[dict[str, Any]]:
        """Parse evidence chunks for the paper."""
        mentions: list[dict[str, Any]] = []
        ev_path = self.root / "03_Evidence" / paper_id / "evidence.json"

        if not ev_path.exists():
            return mentions

        try:
            evidence = json.loads(ev_path.read_text(encoding="utf-8"))
        except Exception:
            return mentions

        # Scan evidence fields
        fields_to_scan = [
            ("key_results", "result"),
            ("core_findings", "finding"),
            ("discussion_points", "point"),
            ("methods", "quote"),
        ]

        for field_name, text_key in fields_to_scan:
            items = evidence.get(field_name, [])
            if not isinstance(items, list):
                continue
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                text = str(item.get(text_key, item.get("name", "")))
                section = str(item.get("section", "unknown"))
                source_id = f"{paper_id}:evidence:{field_name}:{i}"

                ev_mentions = self._extract_from_text(
                    text, paper_id, "evidence_chunk", source_id, section,
                )
                # Add evidence-specific metadata
                for m in ev_mentions:
                    m["evidence_field"] = field_name
                    m["evidence_index"] = i
                mentions.extend(ev_mentions)

        return mentions

    def _parse_summary(self, paper_id: str) -> list[dict[str, Any]]:
        """Parse summary file for the paper."""
        mentions: list[dict[str, Any]] = []
        summary_dir = self.root / "03_Summary"
        candidates = [
            summary_dir / f"{paper_id}_summary.md",
            summary_dir / f"{paper_id}_ai_summary.md",
        ]

        for sp in candidates:
            if not sp.exists():
                continue
            try:
                text = sp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            section = "summary"
            source_id = f"{paper_id}:summary:{sp.stem}"
            sum_mentions = self._extract_from_text(
                text, paper_id, "summary", source_id, section,
            )
            mentions.extend(sum_mentions)

        return mentions

    def _extract_from_text(
        self,
        text: str,
        paper_id: str,
        source_type: str,
        source_id: str,
        section: str,
    ) -> list[dict[str, Any]]:
        """Extract citation mentions from a single text block."""
        mentions: list[dict[str, Any]] = []
        seen_spans: set[tuple[int, int]] = set()

        for pattern, expected_type in _CITATION_PATTERNS:
            for match in pattern.finditer(text):
                span = (match.start(), match.end())
                # Avoid duplicate matches from overlapping patterns
                if any(
                    span[0] >= s[0] and span[1] <= s[1]
                    for s in seen_spans
                ):
                    continue

                citation_text = match.group(0).strip()
                if not citation_text:
                    continue

                # Normalize
                norm = normalize_label(citation_text)

                # Extract context
                ctx_start = max(0, match.start() - CONTEXT_WINDOW)
                ctx_end = min(len(text), match.end() + CONTEXT_WINDOW)
                context_before = text[ctx_start:match.start()].strip()
                context_after = text[match.end():ctx_end].strip()

                # Extract the sentence containing this citation
                sentence = self._extract_sentence(text, match.start(), match.end())

                mention_id = f"cite_{uuid.uuid4().hex[:12]}"

                mentions.append({
                    "mention_id": mention_id,
                    "paper_id": paper_id,
                    "source_type": source_type,
                    "source_id": source_id,
                    "section": section,
                    "sentence": sentence[:500],
                    "citation_text": citation_text,
                    "asset_type": norm["asset_type"],
                    "normalized_label": norm["normalized_label"],
                    "subpanel": norm.get("subpanel", ""),
                    "is_supplementary": norm.get("is_supplementary", False),
                    "context_before": context_before[:500],
                    "context_after": context_after[:500],
                    "char_start": match.start(),
                    "char_end": match.end(),
                })

                seen_spans.add(span)

        return mentions

    @staticmethod
    def _extract_sentence(text: str, start: int, end: int) -> str:
        """Extract the sentence containing the given span."""
        # Expand to sentence boundaries
        sent_start = start
        while sent_start > 0 and text[sent_start - 1] not in ".!?\n":
            sent_start -= 1
        # Skip leading punctuation/whitespace
        while sent_start < start and text[sent_start] in ".!?\n ":
            sent_start += 1

        sent_end = end
        while sent_end < len(text) and text[sent_end] not in ".!?\n":
            sent_end += 1
        if sent_end < len(text):
            sent_end += 1  # Include ending punctuation

        return text[sent_start:sent_end].strip()
