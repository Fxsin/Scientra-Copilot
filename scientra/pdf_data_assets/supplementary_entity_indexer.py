"""
Supplementary Entity Indexer — extracts entities from high-confidence supplementary files.

Phase 2E: Rule-based column classification + entity value extraction.
Only processes simple_preview_extracted links with high/medium confidence.
No LLM. No OCR. No external download. No full file reads.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Column classification rules (domain-agnostic) ──

GENE_COLUMN_PATTERNS = [
    r'^gene$', r'^gene[_ ]?id$', r'^gene[_ ]?name$', r'^gene[_ ]?symbol$',
    r'^locus$', r'^locus[_ ]?tag$', r'^transcript$', r'^transcript[_ ]?id$',
    r'^symbol$', r'^orf$', r'^gene[_ ]?list$', r'^gene[_ ]?accession$',
]

PROTEIN_COLUMN_PATTERNS = [
    r'^protein$', r'^protein[_ ]?id$', r'^accession$', r'^uniprot$',
    r'^peptide$', r'^protein[_ ]?name$', r'^protein[_ ]?accession$',
]

COMPOUND_COLUMN_PATTERNS = [
    r'^compound$', r'^metabolite$', r'^chemical$', r'^molecule$',
    r'^drug$', r'^inhibitor$', r'^activator$', r'^substrate$',
]

TREATMENT_COLUMN_PATTERNS = [
    r'^treatment$', r'^condition$', r'^group$', r'^sample$', r'^sample[_ ]?id$',
    r'^tissue$', r'^stage$', r'^time[_ ]?point$', r'^dose$', r'^concentration$',
]

SAMPLE_COLUMN_PATTERNS = [
    r'^strain$', r'^isolate$', r'^species$', r'^organism$', r'^cell[_ ]?line$',
    r'^cell[_ ]?type$', r'^specimen$', r'^source$', r'^collection$', r'^origin$',
]

PHENOTYPE_COLUMN_PATTERNS = [
    r'^phenotype$', r'^morpholog', r'^trait$', r'^characteristic$',
    r'^symptom$', r'^disease$', r'^severity$', r'^outcome$',
]

VALUE_COLUMN_PATTERNS = [
    r'^fc$', r'^fold[_ ]?change$', r'^log2fc$', r'^log[_ ]?2[_ ]?fc$',
    r'^expression$', r'^expr$', r'^count$', r'^tpm$', r'^fpkm$', r'^rpkm$',
    r'^intensity$', r'^abundance$', r'^concentration$',
    r'^lc[_ ]?50$', r'^ld[_ ]?50$', r'^ic[_ ]?50$', r'^ec[_ ]?50$',
    r'^mortality$', r'^survival$', r'^inhibition$', r'^activity$',
    r'^p[\-_ ]?value$', r'^pvalue$', r'^padj$', r'^q[\-_ ]?value$', r'^qvalue$',
    r'^fdr$', r'^adj[_ ]?p', r'^significance$',
    r'^slope$', r'^se$', r'^std[_ ]?err', r'^ci$', r'^odds[_ ]?ratio$',
    r'^ratio$', r'^percent', r'^percentage$', r'^rate$', r'^score$',
]

COLUMN_CLASSIFIERS: list[tuple[str, list[str]]] = [
    ("gene", GENE_COLUMN_PATTERNS),
    ("protein", PROTEIN_COLUMN_PATTERNS),
    ("compound", COMPOUND_COLUMN_PATTERNS),
    ("treatment", TREATMENT_COLUMN_PATTERNS),
    ("sample", SAMPLE_COLUMN_PATTERNS),
    ("phenotype", PHENOTYPE_COLUMN_PATTERNS),
    ("statistical_value", VALUE_COLUMN_PATTERNS),
]

# Values to skip as entities
SKIP_VALUES = {'na', 'n/a', 'none', 'null', 'unknown', 'n.d.', 'nd', '-', '--', '', ' '}


def classify_column(col_name: str) -> str:
    """Classify a column name into an entity type. Returns 'unknown' if no match."""
    clean = col_name.strip().lower()
    clean = re.sub(r'[_\-\s]+', '_', clean)  # Normalize dashes, underscores, spaces
    clean = clean.strip('_').lstrip('﻿')  # Remove BOM
    for etype, patterns in COLUMN_CLASSIFIERS:
        for pat in patterns:
            if re.match(pat, clean, re.IGNORECASE):
                return etype
    return "unknown"


def is_entity_column(col_name: str) -> bool:
    """Check if a column is an entity-bearing column (gene, protein, etc.)."""
    return classify_column(col_name) not in ("unknown", "statistical_value")


def is_value_column(col_name: str) -> bool:
    """Check if a column is a statistical/value column."""
    return classify_column(col_name) == "statistical_value"


def normalize_entity(text: str) -> str:
    """Normalize entity text for search."""
    return re.sub(r'\s+', '_', text.strip().lower()).strip('_')


def is_valid_entity(text: str) -> bool:
    """Check if a text value is a valid entity (not empty, not pure number, etc.)."""
    t = text.strip()
    if not t or len(t) < 2 or len(t) > 100:
        return False
    if t.lower() in SKIP_VALUES:
        return False
    if re.match(r'^[\d.\-+eE]+$', t):  # Pure number
        return False
    return True


# ── Main indexer ──

class SupplementaryEntityIndexer:
    """Indexes entities from high-confidence supplementary data files."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        # Phase v3: prefer new paths, fallback to legacy
        self.suppl_links_dir = self._resolve_dir(
            "03_Assets/supplementary_assets/links",
            "06_PDF_DataAssets/08_supplementary_links")
        self.output_dir = self._resolve_dir(
            "04_Corpus/data/gene_evidence",
            "06_PDF_DataAssets/09_supplementary_entities")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_dir(self, new_rel: str, legacy_rel: str) -> Path:
        new = self.root / new_rel
        if new.exists():
            return new
        legacy = self.root / legacy_rel
        if legacy.exists():
            return legacy
        return new  # default to new for future writes

    def index_all(self) -> dict[str, Any]:
        """Index entities from all papers with high-confidence supplementary links."""
        all_entities: list[dict[str, Any]] = []
        stats: dict[str, Any] = {
            "papers_with_high_conf": 0,
            "papers_skipped": 0,
            "candidate_only_skipped": 0,
            "file_missing_skipped": 0,
            "total_entity_records": 0,
            "raw_candidate_count": 0,
            "duplicates_collapsed": 0,
            "max_source_link_count": 0,
            "entities_with_multi_links": 0,
            "entity_types": Counter(),
            "column_types": Counter(),
        }

        if not self.suppl_links_dir.exists():
            return stats

        for paper_dir in sorted(self.suppl_links_dir.iterdir()):
            if not paper_dir.is_dir():
                continue
            links_path = paper_dir / "supplementary_links.json"
            if not links_path.exists():
                continue

            paper_entities = self.index_paper(paper_dir.name, links_path)
            if paper_entities:
                all_entities.extend(paper_entities)
                stats["papers_with_high_conf"] += 1
                for e in paper_entities:
                    stats["total_entity_records"] += 1
                    stats["entity_types"][e["entity_type"]] += 1
                    stats["column_types"][e.get("column_name", "unknown")] += 1
                    slc = e.get("source_link_count", 1)
                    stats["max_source_link_count"] = max(stats["max_source_link_count"], slc)
                    if slc > 1:
                        stats["entities_with_multi_links"] += 1
                # Collect raw candidate count from first entity's metadata
                raw = paper_entities[0].pop("_raw_candidate_count", 0)
                stats["raw_candidate_count"] += raw
                stats["duplicates_collapsed"] += max(0, raw - len(paper_entities))
            else:
                stats["papers_skipped"] += 1

        stats["entity_types"] = dict(stats["entity_types"].most_common())
        stats["column_types"] = dict(stats["column_types"].most_common(20))

        # Write report
        self._write_report(stats, all_entities)

        return stats

    def index_paper(self, paper_id: str, links_path: Path | None = None) -> list[dict[str, Any]]:
        """Index entities for a single paper with deduplication.

        Phase 2E-B: Entities are deduplicated by (file_id, sheet, row, column, normalized_entity).
        Same entity from multiple supplementary links is merged with linked_supplement_labels.
        """
        if links_path is None:
            links_path = self.suppl_links_dir / paper_id / "supplementary_links.json"
        if not links_path.exists():
            return []

        try:
            links = json.loads(links_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        # Phase 2E-B: Use dict for dedup by key
        dedup_map: dict[str, dict[str, Any]] = {}
        raw_candidate_count = 0
        timestamp = datetime.now(timezone.utc).isoformat()

        for link in links:
            # Only high-confidence matched+previewed links
            content_status = link.get("content_status", "")
            match_confidence = link.get("match_confidence", "")

            if content_status != "simple_preview_extracted":
                continue
            if match_confidence not in ("high", "medium"):
                continue
            if not link.get("imported_file_id"):
                continue

            preview_rows = link.get("preview_rows", [])
            preview_cols = link.get("preview_columns", [])
            if not preview_rows or not preview_cols:
                continue

            # Classify each column
            col_types = {col: classify_column(col) for col in preview_cols}
            entity_cols = [c for c, t in col_types.items() if t not in ("unknown", "statistical_value")]
            value_cols = [c for c, t in col_types.items() if t == "statistical_value"]

            if not entity_cols:
                continue

            supplement_label = link.get("supplement_label", "unknown")
            source_asset_id = link.get("asset_id", "")
            ref_sentence = (link.get("reference_sentences") or [""])[0][:300]
            file_id = link.get("imported_file_id", "")
            file_name = link.get("imported_file_name")
            sheet = link.get("selected_sheet") or ""

            # Extract entities from entity-bearing columns
            for row_idx, row in enumerate(preview_rows):
                # Skip header row if it appears as data
                if row_idx == 0:
                    header_like = all(
                        str(v).strip().lower() in {c.strip().lower() for c in preview_cols}
                        for v in row.values() if v
                    )
                    if header_like:
                        continue

                for ecol in entity_cols:
                    entity_text = str(row.get(ecol, "")).strip()
                    if not is_valid_entity(entity_text):
                        continue

                    norm = normalize_entity(entity_text)
                    entity_type = col_types.get(ecol, "unknown")
                    raw_candidate_count += 1

                    # Build dedup key
                    dedup_key = f"{paper_id}::{file_id}::{sheet}::{row_idx}::{ecol}::{norm}"

                    if dedup_key in dedup_map:
                        # Merge into existing record
                        existing = dedup_map[dedup_key]
                        existing["source_link_count"] += 1
                        if supplement_label not in existing["linked_supplement_labels"]:
                            existing["linked_supplement_labels"].append(supplement_label)
                        if source_asset_id and source_asset_id not in existing["linked_source_asset_ids"]:
                            existing["linked_source_asset_ids"].append(source_asset_id)
                        if ref_sentence and len(existing["linked_reference_sentences"]) < 5:
                            if ref_sentence not in existing["linked_reference_sentences"]:
                                existing["linked_reference_sentences"].append(ref_sentence)
                    else:
                        # Build value columns context
                        value_context: dict[str, str] = {}
                        for vcol in value_cols:
                            val = str(row.get(vcol, ""))
                            if val and len(val) < 200:
                                value_context[vcol] = val

                        # Build row preview
                        row_preview: dict[str, str] = {}
                        for k, v in row.items():
                            sv = str(v).strip()
                            if sv and len(sv) < 100:
                                row_preview[k] = sv
                        row_preview = dict(list(row_preview.items())[:8])

                        refs_list = [ref_sentence] if ref_sentence else []

                        dedup_map[dedup_key] = {
                            "dedup_key": dedup_key,
                            "paper_id": paper_id,
                            "source_asset_id": source_asset_id,
                            "supplement_label": supplement_label,
                            "imported_file_id": file_id,
                            "imported_file_name": file_name,
                            "sheet_name": sheet if sheet else None,
                            "entity_text": entity_text,
                            "normalized_entity": norm,
                            "entity_type": entity_type,
                            "column_name": ecol,
                            "row_index": row_idx,
                            "row_preview": row_preview,
                            "matched_columns": entity_cols,
                            "value_columns": value_context,
                            "confidence": match_confidence,
                            "extraction_method": "column_header_rule",
                            "linked_supplement_labels": [supplement_label],
                            "linked_source_asset_ids": [source_asset_id] if source_asset_id else [],
                            "linked_reference_sentences": refs_list,
                            "source_link_count": 1,
                            "created_at": timestamp,
                        }

        # Build final deduplicated list with entity_ids
        entities: list[dict[str, Any]] = []
        for ent_idx, (key, rec) in enumerate(sorted(dedup_map.items())):
            rec["entity_id"] = f"{paper_id}:suppl_entity:{ent_idx:04d}"
            # Sort linked lists for deterministic output
            rec["linked_supplement_labels"] = sorted(set(rec["linked_supplement_labels"]))
            rec["linked_source_asset_ids"] = sorted(set(rec["linked_source_asset_ids"]))
            rec["linked_reference_sentences"] = rec["linked_reference_sentences"][:5]
            entities.append(rec)

        # Store raw count for stats
        if entities:
            entities[0]["_raw_candidate_count"] = raw_candidate_count

        # Write output
        if entities:
            output_path = self.output_dir / paper_id / "supplementary_entities.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = output_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(output_path)

        return entities

    def search_entities(
        self, query: str, entity_type: str | None = None,
        paper_id: str | None = None, top_k: int = 20
    ) -> list[dict[str, Any]]:
        """Search indexed entities by normalized query."""
        results: list[dict[str, Any]] = []
        query_norm = normalize_entity(query)

        if not self.output_dir.exists():
            return results

        for paper_dir in self.output_dir.iterdir():
            if not paper_dir.is_dir():
                continue
            if paper_id and paper_dir.name != paper_id:
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

                # Exact match first, then substring
                if norm == query_norm:
                    results.append({**e, "match_type": "exact"})
                elif query_norm in norm or query_norm in entity_text:
                    results.append({**e, "match_type": "substring"})

        # Sort: exact matches first, then by confidence
        results.sort(key=lambda x: (0 if x.get("match_type") == "exact" else 1, x.get("row_index", 0)))
        return results[:top_k]

    @staticmethod
    def _write_report(stats: dict, entities: list[dict]) -> None:
        root = Path(__file__).resolve().parent.parent.parent
        report_path = root / "06_PDF_DataAssets" / "00_registry" / "supplementary_entity_index_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Supplementary Entity Index Report — Phase 2E", "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}", "",
            "## Summary", "",
            f"- **Papers with high-confidence supplementary data**: {stats['papers_with_high_conf']}",
            f"- **Papers skipped (no high-conf links)**: {stats['papers_skipped']}",
            f"- **Total entity records**: {stats['total_entity_records']}",
            "", "## Entity Type Distribution", "",
        ]
        for et, cnt in stats.get("entity_types", {}).items():
            lines.append(f"- **{et}**: {cnt}")

        lines.extend(["", "## Column Classification (top 20)", ""])
        for col, cnt in stats.get("column_types", {}).items():
            lines.append(f"- `{col}`: {cnt}")

        lines.extend(["", "## Top 20 Entity Samples", ""])
        for e in entities[:20]:
            lines.append(f"- **{e.get('entity_text','?')}** ({e.get('entity_type','?')}) "
                        f"in {e.get('imported_file_name','?')[:40]}, "
                        f"col={e.get('column_name','?')}, row={e.get('row_index',0)}")

        if stats['total_entity_records'] == 0:
            lines.extend(["", "> No high-confidence supplementary files with preview data found.",
                         "> Ensure files in 00_Supplementary/inbox/ use {paper_id}__{label}.ext naming."])

        lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")
