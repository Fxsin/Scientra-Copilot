"""
Table Linker — finds table references in results, discussion, claims, and sections.

Phase 2A: Regex-based reference detection. Links tables to result assets, claim assets,
and evidence items.

Output: reference links with source context.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Patterns for in-text table references
TABLE_REF_PATTERNS = [
    # "Table 1", "Table 2A"
    re.compile(
        r'(?:Table|TABLE|Tab\.?)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?(?:,\s*S?\d+[A-Za-z]?)*)',
        re.IGNORECASE
    ),
    # "Tables 1 and 2", "Tables 1, 2, 3"
    re.compile(
        r'(?:Tables|TABLES)\s+((?:S?\d+[A-Za-z]?(?:,\s*|\s+and\s+))*S?\d+[A-Za-z]?)',
        re.IGNORECASE
    ),
    # "Supplementary Table S1", "Supplementary Table 1"
    re.compile(
        r'(?:Supplementary\s+Table|Suppl\.?\s*Table|Table\s+S)\s+(S?\d+[A-Za-z]?)',
        re.IGNORECASE
    ),
    # "Supplementary Tables S1-S3", "Supplementary Tables S1 and S2"
    re.compile(
        r'Supplementary\s+Tables?\s+((?:S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?(?:,\s*|\s+and\s+))*S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)',
        re.IGNORECASE
    ),
    # "(Table 1)" parenthetical references
    re.compile(
        r'\((?:see\s+)?(?:Table|TABLE|Tab\.?)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)\)',
        re.IGNORECASE
    ),
]


class TableLinker:
    """Finds in-text table references and links them to result/claim assets."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def find_references(self, paper_id: str) -> list[dict[str, Any]]:
        """Find all table reference sentences and link to assets. Returns list of links."""
        links: list[dict[str, Any]] = []

        # Load evidence for structured fields
        evidence = self._load_evidence(paper_id)

        # Scan each evidence field for table references
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

                for pattern in TABLE_REF_PATTERNS:
                    for match in pattern.finditer(text):
                        number = match.group(1).strip()
                        if not number:
                            continue

                        # Handle multiple numbers in one reference (e.g. "Tables 1 and 2")
                        numbers = self._split_numbers(number)

                        for num in numbers:
                            # Get surrounding sentence context
                            start = max(0, match.start() - 120)
                            end = min(len(text), match.end() + 120)
                            sentence = text[start:end].strip()

                            links.append({
                                "table_label": f"Table {num}",
                                "table_number": num,
                                "reference_sentence": sentence[:400],
                                "source_section": section,
                                "source_field": field_name,
                                "source_index": i,
                                "linked_evidence_id": f"{paper_id}:{field_name}:{i}",
                            })

        return links

    def link_to_assets(
        self, paper_id: str, tables: list[dict[str, Any]], references: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge table candidates with reference links by matching table_number."""
        # Build reference lookup by table_number
        ref_map: dict[str, list[dict[str, Any]]] = {}
        for ref in references:
            num = ref.get("table_number", "")
            if num not in ref_map:
                ref_map[num] = []
            ref_map[num].append(ref)

        for tbl in tables:
            num = tbl.get("table_number", "")
            refs = ref_map.get(num, [])

            if refs:
                tbl["reference_sentences"] = [r.get("reference_sentence", "") for r in refs]
                tbl["mentioned_in_sections"] = list({r.get("source_section", "unknown") for r in refs})
                tbl["linked_evidence_ids"] = [r.get("linked_evidence_id", "") for r in refs if r.get("linked_evidence_id")]
                if tbl.get("caption"):
                    tbl["confidence"] = "high"
                else:
                    tbl["confidence"] = "medium"
            else:
                # If caption exists but no references, still keep it
                tbl.setdefault("reference_sentences", [])
                tbl.setdefault("mentioned_in_sections", [])
                tbl.setdefault("linked_evidence_ids", [])
                if not tbl.get("caption"):
                    tbl["confidence"] = "low"

            tbl.setdefault("linked_result_assets", [])
            tbl.setdefault("linked_claim_assets", [])

        return tables

    def _split_numbers(self, num_str: str) -> list[str]:
        """Split compound number references into individual numbers."""
        numbers: list[str] = []
        # Handle "S1-S3" ranges
        range_match = re.match(r'(S?)(\d+)[–\-](S?)(\d+)', num_str)
        if range_match:
            prefix1, start, prefix2, end = range_match.groups()
            pfx = prefix1 or prefix2 or ""
            for n in range(int(start), int(end) + 1):
                numbers.append(f"{pfx}{n}")
            return numbers

        # Split by "and" and commas
        parts = re.split(r'\s+and\s+|,\s*', num_str)
        for p in parts:
            p = p.strip()
            if p:
                numbers.append(p)
        return numbers

    def _load_evidence(self, paper_id: str) -> dict[str, Any]:
        ev_path = self.root / "03_Evidence" / paper_id / "evidence.json"
        if ev_path.exists():
            try:
                return json.loads(ev_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}
