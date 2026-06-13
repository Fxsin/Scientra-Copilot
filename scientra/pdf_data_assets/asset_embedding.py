"""
Asset Embedding Engine — embeds agent_chunks.quality.jsonl into LanceDB.

Phase 0.6: Reuses the project's existing BgeM3Embedder (scientra/embedding.py)
to encode vector_ready=true agent chunks into a new LanceDB table `pdf_asset_chunks`.

Does NOT modify:
  - 03_Evidence
  - evidence_embedding.py
  - existing LanceDB tables (metadata_embeddings, summary_embeddings, chunk_embeddings)
  - web / API routes

Commands:
    python -m scientra.pdf_data_assets.asset_embedding --status
    python -m scientra.pdf_data_assets.asset_embedding --paper-id <id>
    python -m scientra.pdf_data_assets.asset_embedding --all
    python -m scientra.pdf_data_assets.asset_embedding --all --force
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger("asset_embedding")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

ASSET_EMBEDDING_VERSION = "0.1.0"
DEFAULT_TABLE_NAME = "pdf_asset_chunks"
DEFAULT_BATCH_SIZE = 32
DEFAULT_MIN_QUALITY_SCORE = 70


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_pdf_assets_config(root: Path) -> dict[str, Any]:
    import yaml

    path = root / "Config" / "pdf_data_assets.yaml"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def _load_embedding_config(root: Path) -> dict[str, Any]:
    import yaml

    path = root / "Config" / "embedding.yaml"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def _get_embedder():
    """Reuse the project's existing BgeM3Embedder."""
    try:
        from scientra.embedding import BgeM3Embedder

        embed_config = _load_embedding_config(_get_project_root())
        model_name = embed_config.get("embedding_model", "BAAI/bge-m3")
        return BgeM3Embedder(model_name=model_name)
    except ImportError as e:
        raise RuntimeError(
            "Cannot import BgeM3Embedder from scientra.embedding. "
            "Ensure the project embedding environment is configured. "
            f"Error: {e}"
        ) from e


class AssetEmbeddingEngine:
    """Embeds agent_chunks into a dedicated LanceDB table."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).resolve() if root else _get_project_root()
        config = _load_pdf_assets_config(self.root)
        emb_config = config.get("asset_embedding", {})

        self.enabled = emb_config.get("enabled", True)
        self.source_dir = self.root / emb_config.get("source_dir", "06_PDF_DataAssets/09_agent_chunks")
        self.source_file = emb_config.get("source_file", "agent_chunks.quality.jsonl")
        self.vector_ready_only = emb_config.get("vector_ready_only", True)
        candidates = [
            self.root / "06_Index/vector",
            self.root / "04_VectorDB",
        ]
        archives = sorted((self.root / "10_System/legacy_archive").glob("storage_v1_legacy_*/04_VectorDB"))
        candidates += archives[::-1]
        default_ldb = candidates[0]
        for cand in candidates:
            ldb_sub = cand / "lancedb"
            if ldb_sub.exists() and any(ldb_sub.iterdir()):
                default_ldb = cand
                break
        self.lancedb_dir = self.root / emb_config.get("lancedb_dir", str(default_ldb.relative_to(self.root)))
        self.table_name = emb_config.get("table_name", DEFAULT_TABLE_NAME)
        self.batch_size = emb_config.get("batch_size", DEFAULT_BATCH_SIZE)
        self.overwrite_existing = emb_config.get("overwrite_existing", False)
        self.include_low_quality = emb_config.get("include_low_quality", False)
        self.min_quality_score = emb_config.get("min_quality_score", DEFAULT_MIN_QUALITY_SCORE)

        self._embedder = None
        self._db = None
        self._vector_dim: int | None = None
        self._embed_config = _load_embedding_config(self.root)
        self._vector_dim = self._embed_config.get("embedding_dimension", 1024)

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = _get_embedder()
        return self._embedder

    @property
    def db(self):
        if self._db is None:
            import lancedb

            db_path = self.lancedb_dir / "lancedb"
            db_path.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(db_path))
        return self._db

    def _table_exists(self) -> bool:
        """Check if the target table exists (LanceDB API compat)."""
        try:
            # list_tables() returns a ListTablesResponse with .tables attribute
            if hasattr(self.db, 'list_tables'):
                resp = self.db.list_tables()
                # Handle both object with .tables and plain list returns
                names = resp.tables if hasattr(resp, 'tables') else resp
                if isinstance(names, list):
                    return self.table_name in names
                return False
            else:
                return self.table_name in self.db.table_names()
        except Exception:
            return False

    # ── Status ──

    def status(self) -> dict[str, Any]:
        """Return current embedding status with full statistics."""
        from collections import Counter

        result: dict[str, Any] = {
            "lancedb_path": str(self.lancedb_dir / "lancedb"),
            "table_name": self.table_name,
            "table_exists": False,
            "embedded_chunk_count": 0,
            "distinct_papers_in_table": 0,
            "chunk_type_distribution": {},
            "available_papers": 0,
            "available_chunks": 0,
            "vector_ready_chunks": 0,
            "total_skipped": 0,
            "skipped_reasons": {},
            "duplicate_chunk_ids": 0,
            "failed_papers": 0,
            "embedding_model": self._embed_config.get("embedding_model", "unknown"),
            "vector_dimension": self._vector_dim,
            "enabled": self.enabled,
        }

        # Check LanceDB table
        try:
            if self._table_exists():
                result["table_exists"] = True
                table = self.db.open_table(self.table_name)
                rows = table.to_pandas()
                result["embedded_chunk_count"] = len(rows)
                result["distinct_papers_in_table"] = rows["paper_id"].nunique()
                type_counts = rows["chunk_type"].value_counts().to_dict()
                result["chunk_type_distribution"] = {str(k): int(v) for k, v in type_counts.items()}

                # Detect duplicate chunk_ids
                dup_mask = rows["chunk_id"].duplicated()
                result["duplicate_chunk_ids"] = int(dup_mask.sum())
        except Exception:
            pass

        # Count available papers/chunks and skipped
        skipped_reasons: Counter = Counter()
        if self.source_dir.exists():
            paper_dirs = [d for d in self.source_dir.iterdir() if d.is_dir()]
            result["available_papers"] = len(paper_dirs)
            for pd in paper_dirs:
                qpath = pd / self.source_file
                if qpath.exists():
                    try:
                        chunks = self._read_chunks(qpath)
                        result["available_chunks"] += len(chunks)
                        result["vector_ready_chunks"] += sum(
                            1 for c in chunks if c.get("vector_ready", False)
                        )
                        # Count would-be skipped
                        for c in chunks:
                            reason = self._should_skip(c)
                            if reason:
                                skipped_reasons[reason] += 1
                    except Exception:
                        result["failed_papers"] += 1
                else:
                    result["failed_papers"] += 1

        result["total_skipped"] = sum(skipped_reasons.values())
        result["skipped_reasons"] = dict(skipped_reasons.most_common())

        return result

    def print_status(self) -> None:
        """Print a human-readable status report."""
        s = self.status()
        print("=== Asset Embedding Status ===")
        print(f"LanceDB path:         {s['lancedb_path']}")
        print(f"Table name:           {s['table_name']}")
        print(f"Table exists:         {s['table_exists']}")
        print(f"Embedded chunks:      {s['embedded_chunk_count']}")
        print(f"Distinct papers:      {s['distinct_papers_in_table']}")
        print(f"Chunk type dist:      {s['chunk_type_distribution']}")
        print(f"Available papers:     {s['available_papers']}")
        print(f"Available chunks:     {s['available_chunks']}")
        print(f"Vector-ready chunks:  {s['vector_ready_chunks']}")
        print(f"Total skipped:        {s['total_skipped']}")
        print(f"Skipped reasons:      {s['skipped_reasons']}")
        print(f"Duplicate chunk_ids:  {s['duplicate_chunk_ids']}")
        print(f"Failed papers:        {s['failed_papers']}")
        print(f"Embedding model:      {s['embedding_model']}")
        print(f"Vector dimension:     {s['vector_dimension']}")
        print(f"Enabled:              {s['enabled']}")

    # ── Core embedding ──

    def embed_paper(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        """Embed chunks for a single paper. Returns summary dict."""
        quality_path = self.source_dir / paper_id / self.source_file
        if not quality_path.exists():
            return {
                "paper_id": paper_id,
                "status": "no_quality_file",
                "embedded": 0,
                "skipped": 0,
                "error": f"No {self.source_file} found",
            }

        all_chunks = self._read_chunks(quality_path)
        if not all_chunks:
            return {"paper_id": paper_id, "status": "no_chunks", "embedded": 0, "skipped": 0}

        # Filter
        to_embed: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for c in all_chunks:
            skip_reason = self._should_skip(c)
            if skip_reason:
                skipped.append({"chunk_id": c.get("chunk_id", "?"), "reason": skip_reason})
            else:
                to_embed.append(c)

        if not to_embed:
            return {
                "paper_id": paper_id,
                "status": "all_skipped",
                "total": len(all_chunks),
                "embedded": 0,
                "skipped": len(skipped),
                "skipped_details": skipped[:10],
            }

        # Remove existing paper chunks if force
        if force and self._table_exists():
            try:
                table = self.db.open_table(self.table_name)
                # Delete by paper_id using scanner filter
                import lance

                table.delete(f"paper_id = '{paper_id}'")
            except Exception as e:
                logger.warning(f"Could not delete existing chunks for {paper_id}: {e}")

        # Encode texts
        texts = [c.get("text", "") for c in to_embed]
        logger.info(f"Encoding {len(texts)} chunks for {paper_id}...")
        t0 = time.time()
        vectors = self.embedder.encode(texts, batch_size=self.batch_size)
        elapsed = time.time() - t0
        logger.info(f"Encoded {len(vectors)} vectors in {elapsed:.1f}s")

        # Build records
        records = []
        timestamp = datetime.now(timezone.utc).isoformat()
        for chunk, vector in zip(to_embed, vectors):
            record = self._build_record(chunk, vector, timestamp)
            records.append(record)

        # Write to LanceDB
        self._write_records(records, force=force)

        # Save status
        self._save_status()

        return {
            "paper_id": paper_id,
            "status": "success",
            "total": len(all_chunks),
            "embedded": len(records),
            "skipped": len(skipped),
            "skipped_details": skipped[:10],
            "encode_time_s": round(elapsed, 1),
        }

    def embed_all(self, force: bool = False) -> dict[str, Any]:
        """Embed chunks for all papers with quality chunks."""
        if not self.source_dir.exists():
            return {"status": "no_source_dir", "embedded": 0, "papers": []}

        paper_dirs = sorted(
            d for d in self.source_dir.iterdir()
            if d.is_dir() and (d / self.source_file).exists()
        )

        if not paper_dirs:
            return {"status": "no_papers", "embedded": 0, "papers": []}

        total_embedded = 0
        total_skipped = 0
        results = []

        for i, pd in enumerate(paper_dirs):
            pid = pd.name
            logger.info(f"[{i+1}/{len(paper_dirs)}] Embedding {pid[:60]}...")
            r = self.embed_paper(pid, force=force)
            results.append(r)
            total_embedded += r.get("embedded", 0)
            total_skipped += r.get("skipped", 0)

        summary = {
            "status": "complete",
            "papers_processed": len(paper_dirs),
            "total_embedded": total_embedded,
            "total_skipped": total_skipped,
            "results": results,
        }
        self._save_status()
        return summary

    # ── Internal helpers ──

    def _read_chunks(self, path: Path) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").strip().splitlines():
            if line.strip():
                try:
                    chunks.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return chunks

    def _should_skip(self, chunk: dict[str, Any]) -> str | None:
        """Return skip reason or None if chunk should be embedded."""
        text = str(chunk.get("text", "")).strip()
        if not text:
            return "empty_text"

        if self.vector_ready_only and not chunk.get("vector_ready", False):
            return "not_vector_ready"

        if not self.include_low_quality:
            qs = chunk.get("quality_score", 0)
            if isinstance(qs, (int, float)) and qs < self.min_quality_score:
                return f"quality_score_below_{self.min_quality_score}"

        return None

    def _build_record(
        self, chunk: dict[str, Any], vector: list[float], timestamp: str
    ) -> dict[str, Any]:
        """Build a LanceDB-compatible record from a chunk + vector."""
        chunk_type = str(chunk.get("chunk_type", "unknown"))
        metadata: dict[str, Any] = {
            "source_asset_ids": chunk.get("source_asset_ids", []),
            "linked_evidence_ids": chunk.get("linked_evidence_ids", []),
            "source_section": chunk.get("source_section", "unknown"),
            "entities": chunk.get("entities", [])[:50],  # cap for storage
            "linked_claims": chunk.get("linked_claims", []),
            "linked_methods": chunk.get("linked_methods", []),
            "citation_ready": chunk.get("citation_ready", False),
            "quality_score": chunk.get("quality_score"),
            "quality_notes": chunk.get("quality_notes", []),
            "chunk_created_at": chunk.get("created_at", ""),
        }

        # Phase 2A + 2B: Preserve table-specific metadata
        if chunk_type in ("table", "supplementary_table", "supplementary_entity"):
            # Extract table metadata from source asset if available
            table_meta: dict[str, Any] = {
                "table_label": "",
                "table_type": "unknown",
                "caption_quality": "none",
                "caption_source": "unknown",
                "structure_status": "caption_only",
                "structure_confidence": "none",
                "structure_extraction_method": "unavailable",
                "structured_columns": [],
                "row_count": 0,
                "first_rows_preview": [],
                "reference_sentences": [],
                "linked_result_assets": [],
                "linked_claim_assets": [],
            }
            # Try to load from tables.json if available
            src_ids = chunk.get("source_asset_ids", [])
            if src_ids:
                paper_id = chunk.get("paper_id", "")
                if paper_id:
                    tbl_path = self.root / "06_PDF_DataAssets" / "03_tables" / paper_id / "tables.json"
                    if tbl_path.exists():
                        try:
                            tables_data = json.loads(tbl_path.read_text(encoding="utf-8"))
                            for t in tables_data:
                                if t.get("asset_id") in src_ids:
                                    table_meta["table_label"] = t.get("table_label", "")
                                    table_meta["table_type"] = t.get("table_type", "unknown")
                                    table_meta["caption_quality"] = t.get("caption_quality", "none")
                                    table_meta["caption_source"] = t.get("caption_source", "unknown")
                                    table_meta["structure_status"] = t.get("structure_status", "caption_only")
                                    table_meta["structure_confidence"] = t.get("structure_confidence", "none")
                                    table_meta["structure_extraction_method"] = t.get("structure_extraction_method", "unavailable")
                                    table_meta["structured_columns"] = t.get("structured_columns", [])[:15]
                                    table_meta["row_count"] = len(t.get("structured_rows", []))
                                    # Small preview of first rows for searchability
                                    rows = t.get("structured_rows", [])
                                    if rows:
                                        preview = []
                                        for r in rows[:3]:
                                            vals = list(r.values())[:5]
                                            preview.append(" | ".join(str(v)[:60] for v in vals if v))
                                        table_meta["first_rows_preview"] = preview
                                    table_meta["reference_sentences"] = t.get("reference_sentences", [])[:10]
                                    table_meta["linked_result_assets"] = t.get("linked_result_assets", [])
                                    table_meta["linked_claim_assets"] = t.get("linked_claim_assets", [])
                                    break
                        except Exception:
                            pass
            metadata["table"] = table_meta

        return {
            "chunk_id": str(chunk.get("chunk_id", "")),
            "paper_id": str(chunk.get("paper_id", "")),
            "chunk_type": str(chunk.get("chunk_type", "unknown")),
            "text": str(chunk.get("text", "")),
            "linked_evidence_id": str(chunk.get("linked_evidence_id") or ""),
            "confidence": str(chunk.get("confidence", "medium")),
            "vector_ready": bool(chunk.get("vector_ready", False)),
            "vector": [float(v) for v in vector],
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
            "embedding_model": self._embed_config.get("embedding_model", "BAAI/bge-m3"),
            "embedding_version": ASSET_EMBEDDING_VERSION,
            "indexed_at": timestamp,
        }

    def _write_records(self, records: list[dict[str, Any]], force: bool = False) -> None:
        """Write records to LanceDB table, handling duplicates."""
        if not records:
            return

        import lancedb

        db_path = self.lancedb_dir / "lancedb"
        db_path.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(db_path))

        if not self._table_exists():
            db.create_table(self.table_name, data=records)
            logger.info(f"Created table '{self.table_name}' with {len(records)} records")
        else:
            table = db.open_table(self.table_name)
            if force:
                paper_ids = list({r["paper_id"] for r in records if r.get("paper_id")})
                for pid in paper_ids:
                    try:
                        table.delete(f"paper_id = '{pid}'")
                    except Exception:
                        pass
                table.add(records)
                logger.info(f"Added {len(records)} records (force, {len(paper_ids)} papers)")
            else:
                try:
                    existing = table.to_pandas()
                    existing_ids = set(existing["chunk_id"].tolist()) if "chunk_id" in existing.columns else set()
                except Exception:
                    existing_ids = set()
                new_records = [r for r in records if r.get("chunk_id") not in existing_ids]
                duplicates = len(records) - len(new_records)
                if duplicates > 0:
                    logger.info(f"Skipping {duplicates} duplicate chunk_ids")
                if new_records:
                    table.add(new_records)
                    logger.info(f"Added {len(new_records)} new records to '{self.table_name}'")
                else:
                    logger.info(f"No new records (all {len(records)} already exist)")

    def _save_status(self) -> Path:
        """Save embedding status to JSON."""
        status_path = self.root / "06_PDF_DataAssets" / "00_registry" / "asset_embedding_status.json"
        s = self.status()

        # Add run metadata
        status_data = {
            "last_run_time": datetime.now(timezone.utc).isoformat(),
            "table_name": s["table_name"],
            "table_exists": s["table_exists"],
            "embedded_chunk_count": s["embedded_chunk_count"],
            "available_papers": s["available_papers"],
            "available_chunks": s["available_chunks"],
            "vector_ready_chunks": s["vector_ready_chunks"],
            "embedding_model": s["embedding_model"],
            "vector_dimension": s["vector_dimension"],
            "version": ASSET_EMBEDDING_VERSION,
        }

        status_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(status_data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(status_path)
        return status_path


# ── CLI ──

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scientra PDF Data Assets — Phase 0.6 Asset Embedding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scientra.pdf_data_assets.asset_embedding --status
  python -m scientra.pdf_data_assets.asset_embedding --paper-id "Bacillus_thuringiensis..."
  python -m scientra.pdf_data_assets.asset_embedding --all
  python -m scientra.pdf_data_assets.asset_embedding --all --force
        """,
    )
    parser.add_argument("--status", action="store_true", help="Show embedding status")
    parser.add_argument("--paper-id", type=str, help="Embed chunks for a specific paper")
    parser.add_argument("--all", action="store_true", help="Embed all vector-ready chunks")
    parser.add_argument("--force", action="store_true", help="Overwrite existing chunks for the paper")

    args = parser.parse_args()

    engine = AssetEmbeddingEngine()

    if args.status:
        engine.print_status()
        return 0

    if args.all:
        result = engine.embed_all(force=args.force)
        print(f"\n=== Embedding Complete ===")
        print(f"Papers processed: {result.get('papers_processed', 0)}")
        print(f"Total embedded:   {result.get('total_embedded', 0)}")
        print(f"Total skipped:    {result.get('total_skipped', 0)}")
        return 0

    if args.paper_id:
        result = engine.embed_paper(args.paper_id, force=args.force)
        print(f"\n=== Embedding Result ===")
        print(f"Paper ID:  {result.get('paper_id', '?')}")
        print(f"Status:    {result.get('status', '?')}")
        print(f"Total:     {result.get('total', 0)}")
        print(f"Embedded:  {result.get('embedded', 0)}")
        print(f"Skipped:   {result.get('skipped', 0)}")
        if result.get("encode_time_s"):
            print(f"Encode:    {result['encode_time_s']}s")
        return 0 if result.get("status") == "success" else 1

    # Default: status
    engine.print_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
