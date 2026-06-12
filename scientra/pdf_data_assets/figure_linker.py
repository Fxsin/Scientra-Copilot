"""
Figure Linker — finds figure references in results, discussion, claims, and sections.

Phase 1: Regex-based reference detection. Links figures to result assets, claim assets,
and evidence items.

Output: reference links with source context.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Patterns for in-text figure references
FIGURE_REF_PATTERNS = [
    # "Fig. 1", "Fig. 2A"
    re.compile(r"(?:Fig\.?|Figure|FIG\.?)\s+(\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?(?:,\s*\d+[A-Za-z]?)*)", re.IGNORECASE),
    # "Figs. 1 and 2", "Figures 1, 2"
    re.compile(r"(?:Figs\.?|Figures)\s+((?:\d+[A-Za-z]?(?:,\s*|\s+and\s+))*\d+[A-Za-z]?)", re.IGNORECASE),
    # "Supplementary Fig. S1"
    re.compile(r"(?:Supplementary\s+Fig\.?|Suppl\.?\s*Fig\.?|Figure\s+S)\s+(S?\d+[A-Za-z]?)", re.IGNORECASE),
]


class FigureLinker:
    """Finds in-text figure references and links them to result/claim assets."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def find_references(self, paper_id: str) -> list[dict[str, Any]]:
        """Find all figure reference sentences and link to assets. Returns list of links."""
        links: list[dict[str, Any]] = []

        # Load evidence for structured fields
        evidence = self._load_evidence(paper_id)

        # Scan each evidence field for figure references
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

                for pattern in FIGURE_REF_PATTERNS:
                    for match in pattern.finditer(text):
                        number = match.group(1).strip()
                        if not number:
                            continue

                        # Get surrounding sentence
                        start = max(0, match.start() - 120)
                        end = min(len(text), match.end() + 120)
                        sentence = text[start:end].strip()

                        links.append({
                            "figure_label": f"Figure {number}",
                            "figure_number": number,
                            "reference_sentence": sentence[:400],
                            "source_section": section,
                            "source_field": field_name,
                            "source_index": i,
                            "linked_evidence_id": f"{paper_id}:{field_name}:{i}",
                        })

        return links

    def link_to_assets(
        self, paper_id: str, figures: list[dict[str, Any]], references: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge figure candidates with reference links by matching figure_number."""
        # Build reference lookup by figure_number
        ref_map: dict[str, list[dict[str, Any]]] = {}
        for ref in references:
            num = ref.get("figure_number", "")
            if num not in ref_map:
                ref_map[num] = []
            ref_map[num].append(ref)

        for fig in figures:
            num = fig.get("figure_number", "")
            refs = ref_map.get(num, [])

            if refs:
                fig["reference_sentences"] = [r.get("reference_sentence", "") for r in refs]
                fig["mentioned_in_sections"] = list({r.get("source_section", "unknown") for r in refs})
                fig["linked_evidence_ids"] = [r.get("linked_evidence_id", "") for r in refs if r.get("linked_evidence_id")]
                fig["confidence"] = "high" if fig.get("caption") else "medium"
            # If caption exists but no references, still keep it
            if not fig.get("reference_sentences"):
                fig.setdefault("reference_sentences", [])
                fig.setdefault("mentioned_in_sections", [])
                fig.setdefault("linked_evidence_ids", [])

            fig.setdefault("linked_result_assets", [])
            fig.setdefault("linked_claim_assets", [])

        return figures

    def _load_evidence(self, paper_id: str) -> dict[str, Any]:
        ev_path = self.root / "03_Evidence" / paper_id / "evidence.json"
        if ev_path.exists():
            try:
                return json.loads(ev_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}
