"""
Cross-Paper Entity Comparator — aggregates entity records across papers/files/sheets.

Phase 2G-A: Location and summary only. No statistical comparison, no LLM, no mechanism.
Direction detection is rule-based from expression/FC/log2FC values.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.supplementary_entity_indexer import normalize_entity


class SupplementaryEntityComparator:
    """Aggregates entity records across papers for comparison."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.entities_dir = self._d(self.root, "04_Corpus/data/gene_evidence",
                                    "06_PDF_DataAssets/09_supplementary_entities")
        self.output_dir = self._d(self.root, "04_Corpus/data/cross_study",
                                   "06_PDF_DataAssets/10_entity_comparisons")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _d(base: Path, new_rel: str, legacy_rel: str) -> Path:
        new = base / new_rel
        return new if new.exists() else base / legacy_rel if (base / legacy_rel).exists() else new

    def compare(
        self, query: str, entity_type: str | None = None, top_k: int = 50
    ) -> dict[str, Any]:
        """Compare entity across all indexed papers.

        Returns comparison dict with aggregated records and summaries.
        """
        query_norm = normalize_entity(query)
        all_matches: list[dict[str, Any]] = []

        # Collect all matching records across all papers
        if not self.entities_dir.exists():
            return self._empty_result(query, query_norm, entity_type)

        for paper_dir in sorted(self.entities_dir.iterdir()):
            if not paper_dir.is_dir():
                continue
            ent_path = paper_dir / "supplementary_entities.json"
            if not ent_path.exists():
                continue
            try:
                entities = json.loads(ent_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            for e in entities:
                if entity_type and e.get("entity_type") != entity_type:
                    continue
                norm = e.get("normalized_entity", "")
                entity_text = e.get("entity_text", "").lower()
                if norm == query_norm or query_norm in norm or query_norm in entity_text:
                    all_matches.append(e)

        if not all_matches:
            return self._empty_result(query, query_norm, entity_type)

        # Deduplicate by dedup_key
        seen_keys: set[str] = set()
        unique_records: list[dict[str, Any]] = []
        for m in all_matches:
            dk = m.get("dedup_key", "")
            if dk and dk in seen_keys:
                continue
            if dk:
                seen_keys.add(dk)
            unique_records.append(m)

        unique_records = unique_records[:top_k]

        # Compute summaries
        papers = {r.get("paper_id") for r in unique_records}
        files = {r.get("imported_file_id") for r in unique_records if r.get("imported_file_id")}
        sheets = {r.get("sheet_name") for r in unique_records if r.get("sheet_name")}

        direction_summary = self._compute_direction_summary(unique_records)
        value_column_summary = self._compute_value_summary(unique_records)

        result: dict[str, Any] = {
            "query_entity": query,
            "normalized_query": query_norm,
            "entity_type": entity_type or self._guess_entity_type(unique_records),
            "total_matches": len(unique_records),
            "unique_papers_count": len(papers),
            "unique_files_count": len(files),
            "unique_sheets_count": len(sheets),
            "records": unique_records,
            "direction_summary": direction_summary,
            "value_column_summary": value_column_summary,
            "comparability_warning": (
                "Values from different papers or supplementary files may not be directly "
                "comparable unless experimental conditions, units, normalization, and "
                "statistical methods are aligned. Source link count reflects references "
                "linked to the same data row, not independent evidence."
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save output
        output_path = self.output_dir / f"{query_norm}_comparison.json"
        tmp = output_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(output_path)

        return result

    def _compute_direction_summary(self, records: list[dict]) -> dict:
        """Compute direction summary from expression/FC/log2FC values."""
        up = 0
        down = 0
        mixed = 0
        unknown = 0
        notes: list[str] = []

        for r in records:
            direction = self._detect_direction(r)
            if direction == "upregulated":
                up += 1
            elif direction == "downregulated":
                down += 1
            elif direction == "mixed":
                mixed += 1
            else:
                unknown += 1

        if up > 0 and down > 0:
            notes.append("Both upregulated and downregulated records found across papers.")

        return {
            "upregulated_count": up,
            "downregulated_count": down,
            "mixed_count": mixed,
            "unknown_count": unknown,
            "notes": notes,
        }

    def _detect_direction(self, record: dict) -> str:
        """Detect direction (up/down/unknown) from a single entity record."""
        value_cols = record.get("value_columns", {})
        row_preview = record.get("row_preview", {})

        # Check expression text columns
        for col_name in ["Expression", "expression", "Regulation", "regulation",
                         "Direction", "direction", "Change", "change"]:
            val = str(value_cols.get(col_name, "") or row_preview.get(col_name, "")).lower().strip()
            if val:
                if any(w in val for w in ["up", "increase", "induced", "upregulat", "higher", "elevated"]):
                    return "upregulated"
                if any(w in val for w in ["down", "decrease", "reduced", "downregulat", "lower", "suppressed"]):
                    return "downregulated"

        # Check log2FC numeric
        for col_name in ["log2FC", "log2fc", "log2_fc", "log2 fold change", "Log2FC"]:
            val = value_cols.get(col_name, "")
            if val:
                try:
                    num = float(str(val).replace(",", "."))
                    return "upregulated" if num > 0 else "downregulated" if num < 0 else "unknown"
                except (ValueError, TypeError):
                    pass

        # Check FC numeric
        for col_name in ["FC", "fc", "Fold Change", "fold_change", "fold change"]:
            val = value_cols.get(col_name, "")
            if val:
                try:
                    num = float(str(val).replace(",", "."))
                    if num > 1:
                        return "upregulated"
                    elif 0 < num < 1:
                        return "downregulated"
                except (ValueError, TypeError):
                    pass

        return "unknown"

    def _compute_value_summary(self, records: list[dict]) -> dict:
        """Summarize which value columns appear across records."""
        all_columns: set[str] = set()
        numeric_columns: set[str] = set()
        non_numeric_columns: set[str] = set()

        for r in records:
            for k, v in r.get("value_columns", {}).items():
                all_columns.add(k)
                try:
                    float(str(v).replace(",", "."))
                    numeric_columns.add(k)
                except (ValueError, TypeError):
                    non_numeric_columns.add(k)

        return {
            "detected_columns": sorted(all_columns),
            "numeric_columns": sorted(numeric_columns),
            "non_numeric_columns": sorted(non_numeric_columns - numeric_columns),
        }

    @staticmethod
    def _guess_entity_type(records: list[dict]) -> str:
        types = {r.get("entity_type", "unknown") for r in records}
        return list(types)[0] if len(types) == 1 else "mixed"

    @staticmethod
    def _empty_result(query: str, query_norm: str, entity_type: str | None) -> dict:
        return {
            "query_entity": query,
            "normalized_query": query_norm,
            "entity_type": entity_type or "unknown",
            "total_matches": 0,
            "unique_papers_count": 0,
            "unique_files_count": 0,
            "unique_sheets_count": 0,
            "records": [],
            "direction_summary": {"upregulated_count": 0, "downregulated_count": 0,
                                   "mixed_count": 0, "unknown_count": 0, "notes": []},
            "value_column_summary": {"detected_columns": [], "numeric_columns": [],
                                      "non_numeric_columns": []},
            "comparability_warning": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
