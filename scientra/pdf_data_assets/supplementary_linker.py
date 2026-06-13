"""
Supplementary Linker — identifies supplementary table/data references in raw text.

Phase 2C: Regex-based identification of supplementary table, data, dataset, and
additional file references from 03_Summary/raw_text/ and 03_Evidence/.

No OCR. No LLM. No complex parsing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Patterns for supplementary references
SUPP_PATTERNS: list[tuple[str, re.Pattern]] = [
    # "Supplementary Table S1", "Supplementary Table 1"
    ("supplementary_table", re.compile(
        r'(?:Supplementary|Supplemental|Suppl\.?)\s+(?:Table|TABLE)\s+(S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)',
        re.IGNORECASE
    )),
    # "Table S1" (supplementary-style label)
    ("table_s_label", re.compile(
        r'(?:^|(?<=[\s(]))(?:Table|TABLE)\s+(S\d+[A-Za-z]?(?:[–\-]S?\d+[A-Za-z]?)?)',
        re.IGNORECASE
    )),
    # "Tables S1-S3", "Tables S1 and S2"
    ("tables_s_range", re.compile(
        r'(?:Tables|TABLES)\s+((?:S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?(?:,\s*|\s+and\s+))*S?\d+[A-Za-z]?(?:[–\-]\d+[A-Za-z]?)?)',
        re.IGNORECASE
    )),
    # "Supplementary Data 1", "Supplementary Dataset 1"
    ("supplementary_data", re.compile(
        r'(?:Supplementary|Supplemental|Suppl\.?)\s+(?:Data|Dataset|Data\s+Set)\s+(\d+[A-Za-z]?)',
        re.IGNORECASE
    )),
    # "Additional file 1", "Additional File 1"
    ("additional_file", re.compile(
        r'(?:Additional|Additional\s+File|Additional\s+file)\s+(\d+[A-Za-z]?)',
        re.IGNORECASE
    )),
    # "Supporting Information Table S1"
    ("supporting_info_table", re.compile(
        r'Supporting\s+Information\s+(?:Table|Fig\.?|Figure)\s+(S?\d+[A-Za-z]?)',
        re.IGNORECASE
    )),
    # "Table S1 in the supplemental material"
    ("supplemental_material", re.compile(
        r'(?:Table|Fig\.?|Figure)\s+(S?\d+[A-Za-z]?)\s+in\s+the\s+(?:supplemental|supplementary|supporting)\s+material',
        re.IGNORECASE
    )),
    # "Supplementary Excel", "Supplementary file"
    ("supplementary_file", re.compile(
        r'(?:Supplementary|Supplemental|Suppl\.?)\s+(?:Excel|File|Spreadsheet|Document)\s*(\d+[A-Za-z]?)?',
        re.IGNORECASE
    )),
    # URL-style supplementary references
    ("supplementary_url", re.compile(
        r'https?://[^\s]*suppl[^\s]*\.(?:xlsx|xls|csv|tsv|pdf|zip)',
        re.IGNORECASE
    )),
]


class SupplementaryLinker:
    """Finds supplementary table/data references and attempts file matching."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.raw_text_dir = self.root / "03_Summary" / "raw_text"
        self.suppl_dir = self.root / "06_PDF_DataAssets" / "08_supplementary_links"
        self._file_inventory: list[dict[str, Any]] | None = None

    def find_all_references(self, paper_id: str) -> list[dict[str, Any]]:
        """Find all supplementary references for a paper. Returns list of candidate dicts."""
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()

        text = self._load_raw_text(paper_id)
        if not text:
            text = self._gather_evidence_text(paper_id)

        if not text:
            return refs

        for ref_type, pattern in SUPP_PATTERNS:
            for m in pattern.finditer(text):
                number = m.group(1).strip() if m.lastindex and m.group(1) else ""
                full_match = m.group(0).strip()

                # Dedup
                dedup_key = f"{ref_type}:{number}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Extract surrounding sentence
                start_ctx = max(0, m.start() - 120)
                end_ctx = min(len(text), m.end() + 120)
                sentence = text[start_ctx:end_ctx].strip()

                # Normalize label
                label = self._normalize_label(ref_type, number, full_match)

                refs.append({
                    "paper_id": paper_id,
                    "supplement_label": label,
                    "supplement_number": number,
                    "referenced_as": full_match[:200],
                    "reference_sentences": [sentence[:400]],
                    "source_text": sentence[:500],
                    "source_section": "unknown",
                    "ref_type": ref_type,
                    "linked_evidence_ids": [],
                })

        # Also scan evidence.json for supplementary references
        ev_refs = self._scan_evidence_fields(paper_id)
        for er in ev_refs:
            dedup_key = f"{er.get('ref_type','')}:{er.get('supplement_number','')}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                refs.append(er)

        return refs

    def match_files(
        self, paper_id: str, refs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Attempt to match references to supplementary files.

        Phase 2D: Priority matching from manual imports (00_Supplementary/inbox/).
        Falls back to true supplementary file inventory if no manual match.
        """
        # Phase 2D: Load manual import registry first
        from scientra.pdf_data_assets.supplementary_importer import load_registry
        import_registry = load_registry(self.root)
        import_files = import_registry.get("files", []) if import_registry else []

        # Also check true supplementary inventory
        inventory = self._get_file_inventory()

        # Combine: manual imports first, then true supplementary
        all_candidates = list(import_files)  # manual imports
        # Add true inventory files not already in imports
        import_paths = {f.get("relative_path", "") for f in import_files}
        for inv_f in inventory:
            if inv_f["path"] not in import_paths:
                all_candidates.append({
                    "file_name": inv_f["name"],
                    "relative_path": inv_f["path"],
                    "file_type": inv_f["ext"].lstrip("."),
                    "possible_paper_id": None,
                    "possible_supplement_label": None,
                })

        for ref in refs:
            ref["candidate_files"] = []
            ref["matched_file"] = None
            ref["file_type"] = "unknown"
            ref["match_confidence"] = "none"
            ref["match_method"] = "no_match"
            ref["content_status"] = "link_only"
            ref["preview_columns"] = []
            ref["preview_rows"] = []
            ref["row_count"] = 0
            ref["column_count"] = 0
            ref["notes"] = []
            # Phase 2D import fields
            ref["imported_file_id"] = None
            ref["imported_file_name"] = None
            ref["imported_relative_path"] = None
            ref["sheet_names"] = []
            ref["preview_status"] = "none"
            ref["selected_sheet"] = None
            ref["import_source"] = "none"

            label = ref.get("supplement_label", "").lower()
            number = ref.get("supplement_number", "")

            if not all_candidates:
                ref["notes"].append("No local supplementary files found")
                ref["content_status"] = "file_missing"
                continue

            # Try matching strategies with priority
            best_score = 0
            best_file = None
            best_method = "no_match"

            for cand in all_candidates:
                fname = cand.get("file_name", "").lower()
                fpath = cand.get("relative_path", "").lower()
                guessed_pid = (cand.get("possible_paper_id") or "").lower()
                guessed_label = (cand.get("possible_supplement_label") or "").lower()
                score = 0
                match_method_type = "no_match"

                # Strategy 1: Exact paper_id + supplement label
                pid_match = paper_id.lower() in fname or guessed_pid == paper_id.lower()
                pid_short = paper_id[-12:] if len(paper_id) >= 12 else paper_id
                pid_short_match = pid_short.lower() in fname or guessed_pid.endswith(pid_short.lower())

                label_match = (
                    (number and f"table_s{number}" in fname) or
                    (number and f"table s{number}" in fname) or
                    label in guessed_label
                )

                if pid_match and label_match:
                    score = 5
                    match_method_type = "manual_paper_id_label"
                elif pid_short_match and label_match:
                    score = 4
                    match_method_type = "manual_paper_id_label"
                elif pid_match:
                    score = 3
                    match_method_type = "manual_paper_id_only"
                elif label_match:
                    score = 2
                    match_method_type = "manual_label_only"
                elif pid_short_match:
                    score = 1
                    match_method_type = "manual_paper_id_only"

                if score > best_score:
                    best_score = score
                    best_file = cand
                    best_method = match_method_type

            if best_file and best_score >= 1:
                # ── Phase 2D-B: Confidence gating ──
                is_label_only = best_method == "manual_label_only"
                is_pid_only = best_method == "manual_paper_id_only"

                if is_label_only:
                    # Label-only: too ambiguous → candidate_only, NOT matched_file
                    ref["matched_file"] = None
                    ref["candidate_files"].append(best_file.get("relative_path", ""))
                    ref["file_type"] = best_file.get("file_type", "unknown")
                    ref["match_confidence"] = "low"
                    ref["match_method"] = "manual_label_only_candidate"
                    ref["content_status"] = "candidate_only"
                    ref["import_source"] = "manual_import"
                    ref["imported_file_id"] = best_file.get("file_id")
                    ref["imported_file_name"] = best_file.get("file_name")
                    ref["imported_relative_path"] = best_file.get("relative_path")
                    ref["sheet_names"] = best_file.get("sheet_names", [])
                    ref["preview_status"] = best_file.get("preview_status", "none")
                    ref["selected_sheet"] = best_file.get("selected_sheet")
                    # NO preview_rows/columns — candidate only
                    ref["preview_columns"] = []
                    ref["preview_rows"] = []
                    ref["row_count"] = 0
                    ref["column_count"] = 0
                    ref["notes"].append(
                        f"Label-only match is ambiguous: {best_file.get('file_name','')}. "
                        "Rename file with paper_id or title keyword for automatic matching."
                    )
                elif is_pid_only and best_score < 3:
                    # PID-only with low score → candidate_only
                    ref["matched_file"] = None
                    ref["candidate_files"].append(best_file.get("relative_path", ""))
                    ref["file_type"] = best_file.get("file_type", "unknown")
                    ref["match_confidence"] = "low"
                    ref["match_method"] = best_method + "_candidate"
                    ref["content_status"] = "candidate_only"
                    ref["import_source"] = "manual_import"
                    ref["imported_file_id"] = best_file.get("file_id")
                    ref["imported_file_name"] = best_file.get("file_name")
                    ref["imported_relative_path"] = best_file.get("relative_path")
                    ref["sheet_names"] = best_file.get("sheet_names", [])
                    ref["preview_status"] = best_file.get("preview_status", "none")
                    ref["selected_sheet"] = best_file.get("selected_sheet")
                    ref["preview_columns"] = []
                    ref["preview_rows"] = []
                    ref["row_count"] = 0
                    ref["column_count"] = 0
                    ref["notes"].append(
                        f"Paper-ID-only match is ambiguous: {best_file.get('file_name','')}. "
                        "Add supplement label to filename for higher confidence."
                    )
                else:
                    # High/medium confidence: paper_id+label or title+label
                    ref["matched_file"] = best_file.get("relative_path", "")
                    ref["file_type"] = best_file.get("file_type", "unknown")
                    ref["candidate_files"].append(best_file.get("relative_path", ""))
                    ref["content_status"] = "file_found"
                    ref["match_confidence"] = "high" if best_score >= 4 else "medium" if best_score >= 3 else "low"
                    ref["match_method"] = best_method
                    ref["notes"].append(f"Matched: {best_file.get('file_name','')} (score={best_score}, method={best_method})")
                    ref["imported_file_id"] = best_file.get("file_id")
                    ref["imported_file_name"] = best_file.get("file_name")
                    ref["imported_relative_path"] = best_file.get("relative_path")
                    ref["sheet_names"] = best_file.get("sheet_names", [])
                    ref["preview_status"] = best_file.get("preview_status", "none")
                    ref["selected_sheet"] = best_file.get("selected_sheet")
                    ref["import_source"] = "manual_import"
                    ref["preview_columns"] = best_file.get("columns_preview", [])
                    ref["preview_rows"] = best_file.get("first_rows_preview", [])
                    ref["row_count"] = best_file.get("row_count", 0)
                    ref["column_count"] = best_file.get("column_count", 0)
                    if best_file.get("preview_status") == "previewed":
                        ref["content_status"] = "simple_preview_extracted"
            else:
                ref["content_status"] = "file_missing"
                ref["notes"].append("No matching local file found")

        return refs

    def _normalize_label(self, ref_type: str, number: str, full_match: str) -> str:
        """Normalize supplementary reference to consistent label format."""
        fm = full_match.lower()

        if "supplementary table" in fm or "supplemental table" in fm:
            return f"Supplementary Table {number}" if number else "Supplementary Table"
        elif "table s" in fm or (number and number.upper().startswith("S")):
            return f"Table {number}"
        elif "supplementary data" in fm or "supplementary dataset" in fm:
            return f"Supplementary Data {number}" if number else "Supplementary Data"
        elif "additional file" in fm:
            return f"Additional File {number}" if number else "Additional File"
        elif "supporting information" in fm and "table" in fm:
            return f"Supporting Information Table {number}" if number else "Supporting Information Table"
        elif "supplementary excel" in fm or "supplementary file" in fm:
            return f"Supplementary File {number}" if number else "Supplementary File"
        else:
            return full_match[:100]

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

    def _scan_evidence_fields(self, paper_id: str) -> list[dict[str, Any]]:
        """Scan evidence.json fields for supplementary references."""
        ev_path = self.root / "03_Evidence" / paper_id / "evidence.json"
        refs = []
        if not ev_path.exists():
            return refs
        try:
            ev = json.loads(ev_path.read_text(encoding="utf-8"))
        except Exception:
            return refs

        fields = [
            ("methods", "quote"),
            ("key_results", "result"),
            ("core_findings", "finding"),
            ("discussion_points", "point"),
        ]
        for field_name, text_key in fields:
            items = ev.get(field_name, [])
            if not isinstance(items, list):
                continue
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                text = str(item.get(text_key, item.get("name", "")))
                section = str(item.get("section", "unknown"))

                for ref_type, pattern in SUPP_PATTERNS:
                    for m in pattern.finditer(text):
                        number = m.group(1).strip() if m.lastindex and m.group(1) else ""
                        full_match = m.group(0).strip()
                        start_ctx = max(0, m.start() - 120)
                        end_ctx = min(len(text), m.end() + 120)
                        sentence = text[start_ctx:end_ctx].strip()
                        label = self._normalize_label(ref_type, number, full_match)

                        refs.append({
                            "paper_id": paper_id,
                            "supplement_label": label,
                            "supplement_number": number,
                            "referenced_as": full_match[:200],
                            "reference_sentences": [sentence[:400]],
                            "source_text": sentence[:500],
                            "source_section": section,
                            "ref_type": ref_type,
                            "linked_evidence_ids": [f"{paper_id}:{field_name}:{i}"],
                        })
        return refs

    def _get_file_inventory(self) -> list[dict[str, Any]]:
        """Get cached inventory of TRUE supplementary files only.

        Phase 2C-B: Strictly excludes raw_text .txt, original PDFs,
        and generated assets. Only xlsx/csv/tsv and keyword-labeled
        supplementary files are considered.
        """
        if self._file_inventory is not None:
            return self._file_inventory

        inventory: list[dict[str, Any]] = []
        supp_exts = {'.xlsx', '.xls', '.csv', '.tsv', '.txt', '.docx', '.pdf', '.zip'}
        exclude_dirs = {'node_modules', '.git', '__pycache__', 'web', 'logs', '.claude'}

        # Paths to explicitly EXCLUDE from supplementary matching
        exclude_path_patterns = [
            r'03_Summary[\\/]raw_text',
            r'01_PDF[\\/]', r'02_Metadata[\\/]', r'03_Evidence[\\/]',
            r'04_VectorDB[\\/]', r'05_Index[\\/]', r'06_PDF_DataAssets[\\/]',
            r'07_Workflows[\\/]', r'Config[\\/]',
            r'evidence\.json', r'figures\.json', r'tables\.json',
            r'agent_chunks\.jsonl', r'asset_registry\.json',
            r'supplementary_links\.json',
        ]
        # Keywords that indicate a .txt or .pdf file IS supplementary
        supp_keywords = [
            'supplementary', 'supplement', 'suppl', 'supporting',
            'additional', 'dataset', 'data', 'table_s', 'si_table',
        ]
        true_table_exts = {'.xlsx', '.xls', '.csv', '.tsv'}

        for ext in supp_exts:
            for f in self.root.rglob(f"*{ext}"):
                skip = False
                for part in f.parts:
                    if part in exclude_dirs:
                        skip = True
                        break
                if skip:
                    continue
                if f.name.startswith("Scientra_"):
                    continue

                rp = str(f.relative_to(self.root))
                rp_lower = rp.lower()
                name_lower = f.name.lower()

                # Reject excluded paths
                excluded = False
                for pat in exclude_path_patterns:
                    if re.search(pat, rp_lower):
                        excluded = True
                        break
                if excluded:
                    continue

                # True tabular files (xlsx/csv/tsv): always include
                if ext in true_table_exts:
                    inventory.append({"path": rp, "name": f.name, "ext": ext, "size": f.stat().st_size})
                    continue

                # txt/pdf/zip/docx: only include if name has supplementary keywords
                has_keyword = any(kw in name_lower for kw in supp_keywords)
                if has_keyword:
                    inventory.append({"path": rp, "name": f.name, "ext": ext, "size": f.stat().st_size})

        self._file_inventory = inventory
        return inventory
