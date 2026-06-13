"""
Context Builder — dual-source retrieval from pdf_asset_chunks + evidence_chunks.

Phase 0.7: Queries both LanceDB tables with the same embedding, merges results,
deduplicates by paper_id, and builds a structured ContextPack for the LLM.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@dataclass
class ContextChunk:
    """A single retrieved chunk with provenance."""
    chunk_id: str
    paper_id: str
    chunk_type: str  # section / method / result / claim
    text: str
    source: str  # "pdf_asset_chunks" or "evidence_chunks"
    linked_evidence_id: str = ""
    linked_evidence_ids: list[str] = field(default_factory=list)
    source_asset_ids: list[str] = field(default_factory=list)
    score: float = 0.0
    confidence: str = "medium"
    quality_score: float = 0.0
    paper_title: str = ""
    paper_year: int | None = None
    paper_journal: str = ""


@dataclass
class ContextPack:
    """Structured context ready for LLM prompt assembly."""
    question: str
    chunks: list[ContextChunk] = field(default_factory=list)
    papers: dict[str, dict[str, Any]] = field(default_factory=dict)
    total_chunks_searched: int = 0
    total_papers_found: int = 0
    token_estimate: int = 0
    elapsed_ms: float = 0.0


class ContextBuilder:
    """Dual-source retrieval: pdf_asset_chunks + evidence_chunks."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).resolve() if root else _get_project_root()
        # Priority: v3 index (promoted) > archive > legacy
        archives = sorted((self.root / "10_System/legacy_archive").glob(
            "storage_v1_legacy_*/04_VectorDB/lancedb"))
        candidates = [
            self.root / "06_Index/vector/lancedb",  # v3 promoted (priority 1)
        ] + archives[::-1] + [
            self.root / "04_VectorDB/lancedb",       # legacy (last resort)
        ]
        self.lancedb_dir = candidates[0]
        for cand in candidates:
            if not cand.exists():
                continue
            # Check if this has actual LanceDB tables (not just auto-created)
            import lancedb as _ldb
            try:
                db_tmp = _ldb.connect(str(cand))
                tbls = db_tmp.table_names()
                if len(tbls) >= 1:  # Must have at least 1 table
                    self.lancedb_dir = cand
                    break
            except Exception:
                continue
        self._embedder = None

    @property
    def embedder(self):
        if self._embedder is None:
            from scientra.embedding import BgeM3Embedder
            self._embedder = BgeM3Embedder(model_name="BAAI/bge-m3")
        return self._embedder

    def search_assets(
        self,
        query: str,
        top_k: int = 10,
        chunk_types: list[str] | None = None,
        paper_id: str | None = None,
        min_quality_score: float = 0.0,
    ) -> list[ContextChunk]:
        """Search pdf_asset_chunks only. Used by /query/assets API."""
        t0 = time.time()
        query_vector = self.embedder.encode([query], batch_size=1)[0]
        chunks = self._search_table(
            table_name="pdf_asset_chunks",
            query_vector=query_vector,
            top_k=top_k,
            chunk_types=chunk_types,
            source_label="pdf_asset_chunks",
        )
        # Post-filter: paper_id + quality_score
        filtered: list[ContextChunk] = []
        for c in chunks:
            if paper_id and c.paper_id != paper_id:
                continue
            if c.quality_score < min_quality_score:
                continue
            filtered.append(c)
        return filtered

    def build_context(
        self,
        question: str,
        top_k: int = 10,
        chunk_types: list[str] | None = None,
        include_evidence: bool = True,
    ) -> ContextPack:
        """Build a context pack from dual-source retrieval."""
        t0 = time.time()
        pack = ContextPack(question=question)

        # Encode question once
        query_vector = self.embedder.encode([question], batch_size=1)[0]

        # ── Source 1: pdf_asset_chunks ──
        asset_chunks = self._search_table(
            table_name="pdf_asset_chunks",
            query_vector=query_vector,
            top_k=top_k,
            chunk_types=chunk_types,
            source_label="pdf_asset_chunks",
        )
        pack.chunks.extend(asset_chunks)

        # ── Source 2: evidence_chunks ──
        if include_evidence:
            ev_chunks = self._search_table(
                table_name="evidence_chunks",
                query_vector=query_vector,
                top_k=top_k,
                source_label="evidence_chunks",
            )
            pack.chunks.extend(ev_chunks)

        # ── Merge & deduplicate ──
        pack.chunks = self._merge_deduplicate(pack.chunks)

        # ── Enrich with paper metadata ──
        pack.papers = self._gather_paper_metadata(pack.chunks)

        # ── Estimate tokens ──
        all_text = question + " " + " ".join(c.text for c in pack.chunks)
        pack.token_estimate = len(all_text) // 3  # rough: ~3 chars/token for scientific text
        pack.total_chunks_searched = len(asset_chunks) + (len(ev_chunks) if include_evidence else 0)
        pack.total_papers_found = len(pack.papers)
        pack.elapsed_ms = (time.time() - t0) * 1000

        return pack

    def _search_table(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 10,
        chunk_types: list[str] | None = None,
        source_label: str = "",
    ) -> list[ContextChunk]:
        """Search a LanceDB table and return ContextChunks."""
        try:
            import lancedb
            db = lancedb.connect(str(self.lancedb_dir))

            # Check table existence (API compat)
            try:
                table_names = db.table_names() if hasattr(db, 'table_names') else [t for t in db.list_tables().tables]
            except Exception:
                return []

            if table_name not in table_names:
                return []

            table = db.open_table(table_name)
            results = table.search(query_vector).limit(top_k).to_list()

            chunks: list[ContextChunk] = []
            for row in results:
                # Parse metadata_json if present
                meta = {}
                meta_json = row.get("metadata_json", "{}")
                if isinstance(meta_json, str):
                    try:
                        meta = json.loads(meta_json)
                    except json.JSONDecodeError:
                        pass
                elif isinstance(meta_json, dict):
                    meta = meta_json

                ctype = str(row.get("chunk_type", row.get("level", "unknown")))
                if chunk_types and ctype not in chunk_types:
                    continue

                chunk = ContextChunk(
                    chunk_id=str(row.get("chunk_id", row.get("record_id", ""))),
                    paper_id=str(row.get("paper_id", "")),
                    chunk_type=ctype,
                    text=str(row.get("text", "")),
                    source=source_label,
                    linked_evidence_id=str(row.get("linked_evidence_id", "")),
                    linked_evidence_ids=meta.get("linked_evidence_ids", []),
                    source_asset_ids=meta.get("source_asset_ids", []),
                    score=float(row.get("_distance", 0)),
                    confidence=str(row.get("confidence", "medium")),
                    quality_score=float(meta.get("quality_score", 0)),
                )
                chunks.append(chunk)

            return chunks

        except Exception:
            return []

    def _merge_deduplicate(self, chunks: list[ContextChunk]) -> list[ContextChunk]:
        """Merge results: deduplicate by chunk_id, rank by score, interleave sources."""
        seen_ids: set[str] = set()
        merged: list[ContextChunk] = []

        # Sort by score (lower _distance = better)
        sorted_chunks = sorted(chunks, key=lambda c: c.score)

        for chunk in sorted_chunks:
            if chunk.chunk_id and chunk.chunk_id in seen_ids:
                continue
            seen_ids.add(chunk.chunk_id)
            merged.append(chunk)

        # Interleave: alternate between sources for diversity
        asset = [c for c in merged if c.source == "pdf_asset_chunks"]
        evidence = [c for c in merged if c.source == "evidence_chunks"]
        interleaved: list[ContextChunk] = []
        max_len = max(len(asset), len(evidence))
        for i in range(max_len):
            if i < len(asset):
                interleaved.append(asset[i])
            if i < len(evidence):
                interleaved.append(evidence[i])

        return interleaved

    def _gather_paper_metadata(self, chunks: list[ContextChunk]) -> dict[str, dict[str, Any]]:
        """Collect paper metadata from 02_Metadata for cited papers."""
        papers: dict[str, dict[str, Any]] = {}
        metadata_dir = self.root / "02_Metadata" / "yaml"

        for chunk in chunks:
            pid = chunk.paper_id
            if pid in papers:
                continue

            # Try to load metadata YAML
            meta: dict[str, Any] = {"paper_id": pid, "title": pid, "year": None, "journal": ""}
            if metadata_dir.exists():
                for yf in metadata_dir.glob("*.yaml"):
                    if pid[:30] in yf.name or pid[-12:] in yf.name:
                        try:
                            import yaml
                            with open(yf, encoding="utf-8") as f:
                                data = yaml.safe_load(f) or {}
                            meta["title"] = str(data.get("title", pid))
                            meta["year"] = data.get("year")
                            meta["journal"] = str(data.get("journal", ""))
                            meta["doi"] = str(data.get("doi", ""))
                            meta["authors"] = data.get("authors", [])
                            break
                        except Exception:
                            pass

            papers[pid] = meta
            chunk.paper_title = str(meta.get("title", ""))
            chunk.paper_year = meta.get("year")
            chunk.paper_journal = str(meta.get("journal", ""))

        return papers
