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

    def get_chunk_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "agent_chunks.jsonl"
        if not path.exists():
            return 0
        try:
            return sum(1 for _ in path.read_text(encoding="utf-8").strip().splitlines() if _.strip())
        except Exception:
            return 0
