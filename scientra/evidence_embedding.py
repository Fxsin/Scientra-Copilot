"""
Evidence Chunks Embedding — writes evidence_chunks to LanceDB via BGE-M3.
Optional, non-blocking. Failure does not affect the main workflow.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("evidence_embedding")
    logging.basicConfig(level=logging.INFO)

TABLE_NAME = "evidence_chunks"


def _safe_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for _ in range(3):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.3)
    tmp.replace(path)


def run_evidence_embedding(root: str | Path, force: bool = False, batch_size: int = 32) -> dict[str, Any]:
    """Main entry: embed all evidence chunks into LanceDB."""
    root = Path(root).resolve()
    evidence_dir = root / "03_Evidence"
    db_dir = root / "04_VectorDB" / "lancedb"

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_papers": 0, "total_chunks": 0, "embedded": 0, "skipped": 0, "failed": 0,
        "errors": [],
    }

    # Collect all chunks
    all_chunks: list[dict[str, Any]] = []
    for paper_dir in sorted(evidence_dir.iterdir()):
        if not paper_dir.is_dir():
            continue
        chunk_path = paper_dir / "evidence_chunks.json"
        if not chunk_path.exists():
            continue
        report["total_papers"] += 1
        try:
            data = json.loads(chunk_path.read_text(encoding="utf-8"))
            for c in data.get("chunks", []):
                all_chunks.append(c)
        except Exception as exc:
            report["failed"] += 1
            report["errors"].append(f"{paper_dir.name}: {exc}")

    report["total_chunks"] = len(all_chunks)
    if not all_chunks:
        report["errors"].append("No evidence chunks found")
        _safe_write(evidence_dir / "evidence_embedding_report.json", report)
        return report

    # Load BGE-M3
    try:
        from scientra.embedding import BgeM3Embedder
        embedder = BgeM3Embedder(model_name="BAAI/bge-m3", device="auto")
        embedder.load()
    except Exception as exc:
        report["errors"].append(f"BGE-M3 load failed: {exc}")
        _safe_write(evidence_dir / "evidence_embedding_report.json", report)
        return report

    # Open or create LanceDB table
    try:
        import lancedb
        db_dir.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(db_dir))
        table_names = db.table_names()
        if TABLE_NAME in table_names and not force:
            table = db.open_table(TABLE_NAME)
            logger.info(f"Table '{TABLE_NAME}' exists, appending")
        else:
            table = None
    except Exception as exc:
        report["errors"].append(f"LanceDB init failed: {exc}")
        _safe_write(evidence_dir / "evidence_embedding_report.json", report)
        return report

    # Embed in batches
    vectors: list[list[float]] = []
    records: list[dict[str, Any]] = []
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        try:
            texts = [c["text"] for c in batch]
            vecs = embedder.encode(texts, batch_size=len(texts))
            for c, v in zip(batch, vecs):
                vectors.append(v)
                records.append({
                    "chunk_id": str(c.get("chunk_id", "")),
                    "paper_id": str(c.get("paper_id", "")),
                    "chunk_type": str(c.get("chunk_type", "")),
                    "text": str(c.get("text", ""))[:2000],
                    "source_section": str(c.get("source_section", "")),
                    "quote": str(c.get("quote", ""))[:240],
                    "confidence": str(c.get("confidence", "medium")),
                    "title": str(c.get("metadata", {}).get("title", "")),
                    "year": c.get("metadata", {}).get("year"),
                    "journal": str(c.get("metadata", {}).get("journal", "")),
                    "vector": v.tolist() if hasattr(v, "tolist") else list(v),
                })
            report["embedded"] += len(batch)
            logger.info(f"Evidence embedding: {report['embedded']}/{report['total_chunks']}")
        except Exception as exc:
            report["failed"] += len(batch)
            report["errors"].append(f"Batch {i}: {exc}")

    # Write to LanceDB
    if records:
        try:
            if table is None:
                db.create_table(TABLE_NAME, data=records)
            else:
                table.add(records)
            logger.info(f"Evidence chunks written to '{TABLE_NAME}': {len(records)} records")
        except Exception as exc:
            report["errors"].append(f"LanceDB write failed: {exc}")

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _safe_write(evidence_dir / "evidence_embedding_report.json", report)
    _write_md_report(evidence_dir / "evidence_embedding_report.md", report)
    return report


def _write_md_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Evidence Embedding Report",
        f"**Started:** {report.get('started_at', '')}",
        f"**Finished:** {report.get('finished_at', '')}",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Papers | {report['total_papers']} |",
        f"| Chunks | {report['total_chunks']} |",
        f"| Embedded | {report['embedded']} |",
        f"| Skipped | {report['skipped']} |",
        f"| Failed | {report['failed']} |",
    ]
    if report.get("errors"):
        lines.append("\n## Errors")
        for e in report["errors"][:20]:
            lines.append(f"- {e}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Evidence Chunks Embedding")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    report = run_evidence_embedding(args.root, force=args.force)
    print(f"Chunks: {report['total_chunks']}  Embedded: {report['embedded']}  Failed: {report['failed']}")
    return 0 if report["failed"] < report["embedded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
