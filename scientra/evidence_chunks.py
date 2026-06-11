"""Evidence Chunks Generator — converts evidence.json into searchable chunks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHUNK_VERSION = "v2"


def generate_chunks(evidence: dict[str, Any], max_chars: int = 1200) -> dict[str, Any]:
    """Convert evidence.json fields into flat searchable chunks."""
    pid = evidence.get("paper_id", "")
    chunks: list[dict[str, Any]] = []
    meta = {
        "title": evidence.get("title", ""),
        "year": evidence.get("year"),
        "journal": evidence.get("journal", ""),
    }

    field_map = [
        ("key_results", "key_result", "result"),
        ("core_findings", "core_finding", "finding"),
        ("discussion_points", "discussion_point", "point"),
        ("limitations", "limitation", "limitation"),
        ("open_questions", "open_question", "question"),
        ("methods", "method", "name"),
        ("claims", "claim", "claim"),
    ]

    for field, chunk_type, text_key in field_map:
        items = evidence.get(field, [])
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            text = str(item.get(text_key, item.get("text", ""))).strip()
            if len(text) < 15:
                continue
            chunk = {
                "chunk_id": f"{pid}:{chunk_type}:{i:04d}",
                "paper_id": pid,
                "chunk_type": chunk_type,
                "text": text[:max_chars],
                "source_section": item.get("section", item.get("source", "")),
                "quote": str(item.get("quote", ""))[:240],
                "confidence": item.get("confidence", "medium"),
                "metadata": {
                    **meta,
                    "method": str(item.get("method", "")),
                    "direction": str(item.get("direction", "")),
                    "evidence_type": str(item.get("evidence_type", "")),
                },
            }
            chunks.append(chunk)

    return {
        "paper_id": pid,
        "chunk_version": CHUNK_VERSION,
        "evidence_hash": _hash_evidence(evidence),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def _hash_evidence(evidence: dict[str, Any]) -> str:
    """Simple hash of key evidence fields for change detection."""
    import hashlib
    key_fields = ["key_results", "core_findings", "discussion_points", "limitations", "open_questions", "methods", "claims"]
    data = json.dumps({k: evidence.get(k, []) for k in key_fields}, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def run_chunk_generation(root: str | Path, force: bool = False) -> dict[str, Any]:
    """Generate evidence_chunks.json for all papers with evidence.json."""
    root = Path(root).resolve()
    evidence_dir = root / "03_Evidence"
    report: dict[str, Any] = {"total": 0, "generated": 0, "skipped": 0, "failed": 0, "chunks_total": 0}

    for paper_dir in sorted(evidence_dir.iterdir()):
        if not paper_dir.is_dir():
            continue
        ev_path = paper_dir / "evidence.json"
        if not ev_path.exists():
            continue
        report["total"] += 1
        chunk_path = paper_dir / "evidence_chunks.json"
        if chunk_path.exists() and not force:
            report["skipped"] += 1
            continue
        try:
            evidence = json.loads(ev_path.read_text(encoding="utf-8"))
            chunks = generate_chunks(evidence)
            _safe_write(chunk_path, chunks)
            report["generated"] += 1
            report["chunks_total"] += chunks["chunk_count"]
        except Exception as exc:
            report["failed"] += 1

    _safe_write(evidence_dir / "evidence_chunks_report.json", report)
    return report


def _safe_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    import time
    for _ in range(3):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.3)
    tmp.replace(path)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Evidence Chunks Generator V2")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    report = run_chunk_generation(args.root, force=args.force)
    print(f"Total: {report['total']}  Generated: {report['generated']}  Skipped: {report['skipped']}  Failed: {report['failed']}  Chunks: {report['chunks_total']}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
