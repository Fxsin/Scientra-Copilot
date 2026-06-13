"""
Agent Chunk Builder — converts all assets into Agent-ready JSONL chunks.

Phase 0.5B fix:
  - Populates linked_evidence_id from source asset's linked_evidence_id.
  - Populates linked_evidence_ids with all traceable evidence IDs from source assets.
  - Each chunk is a self-contained, citation-ready piece of knowledge suitable
    for LLM / Agent consumption. All chunks preserve source references.

Outputs: 06_PDF_DataAssets/09_agent_chunks/{paper_id}/agent_chunks.jsonl
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import AgentChunkAsset, Confidence
from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter
from scientra.pdf_data_assets.section_aligner import SectionAligner
from scientra.pdf_data_assets.method_asset_builder import MethodAssetBuilder
from scientra.pdf_data_assets.result_asset_builder import ResultAssetBuilder
from scientra.pdf_data_assets.entity_asset_builder import EntityAssetBuilder
from scientra.pdf_data_assets.claim_evidence_builder import ClaimEvidenceBuilder
from scientra.pdf_data_assets.figure_asset_builder import FigureAssetBuilder
from scientra.pdf_data_assets.table_asset_builder import TableAssetBuilder


class AgentChunkBuilder:
    """Builds agent-ready chunks from all asset types."""

    MAX_CHUNK_CHARS = 1200

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "09_agent_chunks"
        self.evidence_adapter = EvidenceAdapter(root)
        self.section_aligner = SectionAligner(root)
        self.method_builder = MethodAssetBuilder(root)
        self.result_builder = ResultAssetBuilder(root)
        self.entity_builder = EntityAssetBuilder(root)
        self.claim_builder = ClaimEvidenceBuilder(root)
        self.figure_builder = FigureAssetBuilder(root)
        self.table_builder = TableAssetBuilder(root)

    def _collect_evidence_ids(self, source_asset_ids: list[str]) -> list[str]:
        """Collect all linked_evidence_ids from source assets by inspecting builders."""
        evidence_ids: list[str] = []
        seen: set[str] = set()

        for asset_id in source_asset_ids:
            if not asset_id:
                continue
            # The asset_id encodes the evidence reference in its structure
            # e.g. {paper_id}:method:0004 -> evidence methods[4]
            # We extract the paper_id part and use it as fallback
            parts = asset_id.split(":")
            if len(parts) >= 1:
                paper_id = parts[0]
                if paper_id and paper_id not in seen:
                    evidence_ids.append(asset_id)
                    seen.add(paper_id)

        return evidence_ids

    def build(self, paper_id: str, force: bool = False) -> list[AgentChunkAsset]:
        """Build agent chunks for a paper. Returns list of AgentChunkAssets."""
        output_path = self.output_dir / paper_id / "agent_chunks.jsonl"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        chunks: list[AgentChunkAsset] = []
        timestamp = datetime.now(timezone.utc).isoformat()
        chunk_idx = 0

        # Pre-build all asset types for evidence ID extraction
        section_assets = self.section_aligner.build(paper_id, force=False)
        method_assets = self.method_builder.build(paper_id, force=False)
        result_assets = self.result_builder.build(paper_id, force=False)
        claim_data = self.claim_builder.build(paper_id, force=False)

        # Build lookup: asset_id -> linked_evidence_id
        ev_id_map: dict[str, str | None] = {}
        for sa in section_assets:
            ev_id_map[sa.asset_id] = sa.linked_evidence_id
        for ma in method_assets:
            ev_id_map[ma.asset_id] = ma.linked_evidence_id
        for ra in result_assets:
            ev_id_map[ra.asset_id] = ra.linked_evidence_id

        # Claims come as raw dicts
        raw_claims = claim_data.get("claims", [])
        for c in raw_claims:
            if isinstance(c, dict):
                ev_id_map[str(c.get("asset_id", ""))] = str(c.get("linked_evidence_id", "")) or None

        # ── Chunks from sections ──
        for sa in section_assets:
            text = sa.text.strip() if sa.text else sa.source_text.strip()
            if len(text) < 30:
                continue
            src_ids = [sa.asset_id]
            ev_ids = self._resolve_evidence_ids(src_ids, ev_id_map)
            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="section",
                text=text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=src_ids,
                source_section=sa.section_label,
                entities=[],
                linked_claims=[],
                linked_methods=[],
                linked_evidence_id=ev_ids[0] if ev_ids else sa.linked_evidence_id,
                linked_evidence_ids=ev_ids,
                citation_ready=True,
                confidence=sa.confidence,
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Chunks from methods ──
        for ma in method_assets:
            text = f"Method: {ma.method_name}\n{ma.source_text}".strip()
            if len(text) < 15:
                continue
            src_ids = [ma.asset_id]
            ev_ids = self._resolve_evidence_ids(src_ids, ev_id_map)
            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="method",
                text=text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=src_ids,
                source_section=ma.source_section,
                entities=[],
                linked_claims=[],
                linked_methods=[ma.asset_id],
                linked_evidence_id=ev_ids[0] if ev_ids else ma.linked_evidence_id,
                linked_evidence_ids=ev_ids,
                citation_ready=True,
                confidence=ma.confidence,
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Chunks from results ──
        for ra in result_assets:
            text = ra.result_text.strip()
            if len(text) < 15:
                continue
            src_ids = [ra.asset_id]
            ev_ids = self._resolve_evidence_ids(src_ids, ev_id_map)
            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="result",
                text=text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=src_ids,
                source_section=ra.source_section,
                entities=[],
                linked_claims=[],
                linked_methods=[],
                linked_evidence_id=ev_ids[0] if ev_ids else ra.linked_evidence_id,
                linked_evidence_ids=ev_ids,
                citation_ready=True,
                confidence=ra.confidence,
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Chunks from claims ──
        for c in raw_claims:
            if not isinstance(c, dict):
                continue
            claim_text = str(c.get("claim_text", "")).strip()
            if len(claim_text) < 15:
                continue
            asset_id = str(c.get("asset_id", ""))
            src_ids = [asset_id] if asset_id else []
            ev_ids = self._resolve_evidence_ids(src_ids, ev_id_map)
            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="claim",
                text=claim_text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=src_ids,
                source_section=str(c.get("source_section", "unknown")),
                entities=[],
                linked_claims=[asset_id] if asset_id else [],
                linked_methods=[],
                linked_evidence_id=ev_ids[0] if ev_ids else str(c.get("linked_evidence_id", "")) or None,
                linked_evidence_ids=ev_ids,
                citation_ready=True,
                confidence=Confidence(str(c.get("confidence", "medium"))),
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Chunks from figures (Phase 1 + 1B) ──
        figure_assets = self.figure_builder.build(paper_id, force=False)
        # Load interpretations if available
        interp_map: dict[str, dict] = {}
        interp_path = self.root / "06_PDF_DataAssets" / "02_figures" / paper_id / "figure_interpretations.json"
        if interp_path.exists():
            try:
                interps = json.loads(interp_path.read_text(encoding="utf-8"))
                for it in interps.get("interpretations", []):
                    interp_map[it.get("figure_label", "")] = it
            except Exception:
                pass

        for fa in figure_assets:
            interp = interp_map.get(fa.figure_label, {})
            parts = [f"Figure {fa.figure_label}: {fa.caption}"]
            # Add interpretation if available
            if interp.get("figure_main_message"):
                parts.append(f"Main message: {interp['figure_main_message']}")
            if interp.get("experimental_evidence_type", "unknown") != "unknown":
                parts.append(f"Evidence type: {interp['experimental_evidence_type']}")
            if interp.get("evidence_strength", "unclear") != "unclear":
                parts.append(f"Evidence strength: {interp['evidence_strength']}")
            claims = interp.get("supported_claims", [])
            if claims:
                parts.append("Supported claims:")
                for c in claims[:5]:
                    parts.append(f"  - {c}")
            lims = interp.get("limitations", [])
            if lims:
                parts.append("Limitations:")
                for lim in lims[:3]:
                    parts.append(f"  - {lim}")
            if fa.reference_sentences:
                parts.append("Referenced in:")
                for rs in fa.reference_sentences[:3]:
                    parts.append(f"  - {rs}")
            if fa.figure_type and fa.figure_type != "unknown":
                parts.append(f"Type: {fa.figure_type}")
            text = "\n".join(parts).strip()
            if len(text) < 15:
                continue

            src_ids = [fa.asset_id]
            ev_ids = list(fa.linked_evidence_ids) if fa.linked_evidence_ids else []
            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="figure",
                text=text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=src_ids,
                source_section=fa.source_section if fa.source_section else "unknown",
                entities=[],
                linked_claims=fa.linked_claim_assets,
                linked_methods=[],
                linked_evidence_id=ev_ids[0] if ev_ids else fa.linked_evidence_id,
                linked_evidence_ids=ev_ids,
                citation_ready=True,
                confidence=fa.confidence,
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Chunks from tables (Phase 2A + 2B) ──
        table_assets = self.table_builder.build(paper_id, force=False)
        for ta in table_assets:
            parts = [f"Table {ta.table_label}: {ta.caption}"]
            if ta.table_type and ta.table_type != "unknown":
                parts.append(f"Table type: {ta.table_type}")
            parts.append(f"Structure status: {ta.structure_status}")

            # Phase 2B: Include structure summary if available
            struct_cols = getattr(ta, 'structured_columns', [])
            struct_rows = getattr(ta, 'structured_rows', [])
            struct_conf = getattr(ta, 'structure_confidence', 'none')
            if struct_cols and struct_rows and ta.structure_status == "simple_structure_extracted":
                parts.append(f"Columns: {', '.join(struct_cols[:10])}")
                parts.append(f"Rows: {len(struct_rows)} rows")
                parts.append(f"Structure confidence: {struct_conf}")
                if struct_rows:
                    parts.append("Representative rows:")
                    for row in struct_rows[:5]:
                        row_parts = []
                        for k in list(row.keys())[:6]:
                            v = str(row.get(k, ""))[:80]
                            if v:
                                row_parts.append(f"{k}: {v}")
                        if row_parts:
                            parts.append(f"  - {'; '.join(row_parts[:3])}")

            if ta.reference_sentences:
                parts.append("Referenced in:")
                for rs in ta.reference_sentences[:5]:
                    parts.append(f"  - {rs}")
            if ta.linked_evidence_ids:
                parts.append("Linked evidence:")
                for ev_id in ta.linked_evidence_ids[:5]:
                    parts.append(f"  - {ev_id}")
            if ta.linked_result_assets:
                parts.append(f"Linked results: {len(ta.linked_result_assets)}")
            if ta.linked_claim_assets:
                parts.append(f"Linked claims: {len(ta.linked_claim_assets)}")
            text = "\n".join(parts).strip()
            if len(text) < 15:
                continue

            src_ids = [ta.asset_id]
            ev_ids = list(ta.linked_evidence_ids) if ta.linked_evidence_ids else []
            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="table",
                text=text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=src_ids,
                source_section=ta.source_section if ta.source_section else "unknown",
                entities=[],
                linked_claims=ta.linked_claim_assets,
                linked_methods=[],
                linked_evidence_id=ev_ids[0] if ev_ids else ta.linked_evidence_id,
                linked_evidence_ids=ev_ids,
                citation_ready=True,
                confidence=ta.confidence,
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Chunks from supplementary links (Phase 2C + 2C-B) ──
        suppl_links = self._load_supplementary_links(paper_id)
        for sl in suppl_links:
            content_status = sl.get("content_status", "link_only")
            is_file_missing = content_status in ("file_missing", "link_only")

            parts = [f"Supplementary {sl.get('supplement_label', 'unknown')}: {sl.get('referenced_as', '')}"]
            parts.append(f"Content status: {content_status}")

            if is_file_missing:
                parts.append("Matched file: None")
                parts.append("No local supplementary data file was found.")
            elif content_status == "candidate_only":
                parts.append("A possible local supplementary file was found, but the match is ambiguous.")
                parts.append("Rename the file to include the paper_id and supplement label for automatic matching.")
                cand_files = sl.get("candidate_files", [])
                if cand_files:
                    parts.append("Candidate files:")
                    for cf in cand_files[:5]:
                        # Show only filename, not full path
                        cf_name = cf.replace("\\", "/").split("/")[-1]
                        parts.append(f"  - {cf_name}")
                parts.append("Content status: candidate_only")
            else:
                if sl.get("imported_file_name"):
                    parts.append(f"Matched file: {sl['imported_file_name']}")
                    parts.append(f"Import source: manual_import")
                if sl.get("file_type") and sl.get("file_type") != "unknown":
                    parts.append(f"Matched file type: {sl['file_type']}")
                if sl.get("match_confidence") and sl.get("match_confidence") != "none":
                    parts.append(f"Match confidence: {sl['match_confidence']}")
                if sl.get("matched_file"):
                    parts.append(f"Matched file: {sl['matched_file']}")

                # Sheets (for xlsx imports)
                sheets = sl.get("sheet_names", [])
                if sheets:
                    parts.append(f"Sheets: {', '.join(sheets[:10])}")
                    sel = sl.get("selected_sheet")
                    if sel:
                        parts.append(f"Selected sheet: {sel}")

                # Preview only for TRUE matched+previewed supplementary files
                # Skip preview for candidate_only, file_missing, raw_text matches
                if content_status not in ("candidate_only", "file_missing"):
                    preview_cols = sl.get("preview_columns", [])
                    preview_rows = sl.get("preview_rows", [])
                    # Guard: skip preview if matched file looks like raw_text
                    matched = sl.get("matched_file", "")
                    if "raw_text" in matched.lower() or "03_summary" in matched.lower():
                        pass  # Skip raw_text preview
                    elif preview_cols:
                        parts.append(f"Preview columns: {', '.join(preview_cols[:10])}")
                    if preview_rows and "raw_text" not in matched.lower() and "03_summary" not in matched.lower():
                        parts.append("First rows preview:")
                        for row in preview_rows[:3]:
                            vals = list(row.values())[:5]
                            parts.append(f"  - {' | '.join(str(v)[:60] for v in vals if v)}")

            refs = sl.get("reference_sentences", [])
            if refs:
                parts.append("Reference sentences:")
                for rs in refs[:3]:
                    parts.append(f"  - {rs}")
            ev_ids = sl.get("linked_evidence_ids", [])
            if ev_ids:
                parts.append("Linked evidence:")
                for ev_id in ev_ids[:5]:
                    parts.append(f"  - {ev_id}")

            text = "\n".join(parts).strip()
            if len(text) < 15:
                continue

            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="supplementary_table",
                text=text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=[sl.get("asset_id", "")] if sl.get("asset_id") else [],
                source_section=sl.get("source_section", "unknown"),
                entities=[],
                linked_claims=sl.get("linked_claim_assets", []),
                linked_methods=[],
                linked_evidence_id=ev_ids[0] if ev_ids else None,
                linked_evidence_ids=ev_ids,
                citation_ready=True,
                confidence=Confidence("low" if is_file_missing else sl.get("confidence", "low")),
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Chunks from supplementary entities (Phase 2E) ──
        suppl_entities = self._load_supplementary_entities(paper_id)
        for se in suppl_entities:
            parts = [
                f"Supplementary entity: {se.get('entity_text', 'unknown')}",
                f"Entity type: {se.get('entity_type', 'unknown')}",
                f"Found in Supplement: {se.get('supplement_label', 'unknown')}",
            ]
            if se.get("imported_file_name"):
                parts.append(f"File: {se['imported_file_name']}")
            if se.get("sheet_name"):
                parts.append(f"Sheet: {se['sheet_name']}")
            if se.get("column_name"):
                parts.append(f"Column: {se['column_name']}")
            if se.get("row_index") is not None:
                parts.append(f"Row: {se['row_index']}")
            # Phase 2E-B: Show linked references
            linked_labels = se.get("linked_supplement_labels", [])
            link_count = se.get("source_link_count", 1)
            if link_count > 1:
                parts.append(f"Source link count: {link_count}")
                if linked_labels:
                    parts.append(f"Linked supplementary references: {', '.join(linked_labels[:10])}")
            value_cols = se.get("value_columns", {})
            if value_cols:
                parts.append("Associated values:")
                for k, v in list(value_cols.items())[:6]:
                    parts.append(f"  - {k}: {v}")
            row_preview = se.get("row_preview", {})
            if row_preview:
                parts.append("Row preview:")
                for k, v in list(row_preview.items())[:5]:
                    parts.append(f"  - {k}: {v}")
            text = "\n".join(parts).strip()
            if len(text) < 15:
                continue

            chunk = AgentChunkAsset(
                chunk_id=f"{paper_id}:chunk:{chunk_idx:04d}",
                paper_id=paper_id,
                chunk_type="supplementary_entity",
                text=text[:self.MAX_CHUNK_CHARS],
                source_asset_ids=[se.get("source_asset_id", "")],
                source_section=se.get("supplement_label", "unknown"),
                entities=[se.get("entity_text", "")],
                linked_claims=[],
                linked_methods=[],
                linked_evidence_id=None,
                linked_evidence_ids=[],
                citation_ready=True,
                confidence=Confidence(se.get("confidence", "medium")),
                created_at=timestamp,
            )
            chunks.append(chunk)
            chunk_idx += 1

        # ── Enrich chunks with entities ──
        entity_assets = self.entity_builder.build(paper_id, force=False)
        self._enrich_with_entities(chunks, entity_assets)

        self._write_output(output_path, chunks)
        return chunks

    def _resolve_evidence_ids(
        self, src_ids: list[str], ev_id_map: dict[str, str | None]
    ) -> list[str]:
        """Resolve evidence IDs from source asset IDs via the lookup map."""
        result: list[str] = []
        seen: set[str] = set()
        for sid in src_ids:
            if not sid:
                continue
            ev_id = ev_id_map.get(sid)
            if ev_id and ev_id not in seen:
                result.append(ev_id)
                seen.add(ev_id)
        return result

    def _enrich_with_entities(
        self, chunks: list[AgentChunkAsset], entities: list[Any]
    ) -> None:
        """Tag chunks with entity names found in their text."""
        entity_names = [e.entity_name.lower() for e in entities if hasattr(e, 'entity_name')]
        for chunk in chunks:
            text_lower = chunk.text.lower()
            for name in entity_names:
                if name in text_lower and name not in [e.lower() for e in chunk.entities]:
                    chunk.entities.append(name)

    def _load_existing(self, path: Path) -> list[AgentChunkAsset]:
        try:
            chunks: list[AgentChunkAsset] = []
            for line in path.read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    chunks.append(AgentChunkAsset(**json.loads(line)))
            return chunks
        except Exception:
            return []

    def _write_output(self, path: Path, chunks: list[AgentChunkAsset]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for c in chunks:
            lines.append(json.dumps(c.model_dump(mode="json", exclude_none=False), ensure_ascii=False))
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _load_supplementary_entities(self, paper_id: str) -> list[dict[str, Any]]:
        """Load supplementary entities for a paper, if available."""
        path = self.root / "06_PDF_DataAssets" / "09_supplementary_entities" / paper_id / "supplementary_entities.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _load_supplementary_links(self, paper_id: str) -> list[dict[str, Any]]:
        """Load supplementary links for a paper, if available."""
        path = self.root / "06_PDF_DataAssets" / "08_supplementary_links" / paper_id / "supplementary_links.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_chunk_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "agent_chunks.jsonl"
        if not path.exists():
            return 0
        try:
            return sum(1 for _ in path.read_text(encoding="utf-8").strip().splitlines() if _.strip())
        except Exception:
            return 0
