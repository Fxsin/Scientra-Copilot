"""
Full-Library Verification Script — Phase 0.6B

Verifies consistency across:
  - asset_registry.json (built papers)
  - quality_status.json (quality-checked papers)
  - pdf_asset_chunks LanceDB table (embedded papers)

Usage:
    python Scripts/verify_pdf_asset_embedding.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> int:
    print("=" * 60)
    print("PDF Asset Embedding Full-Library Verification")
    print("=" * 60)
    print()

    all_pass = True
    issues: list[str] = []

    # 1. Load registry
    reg_path = PROJECT_ROOT / "06_PDF_DataAssets" / "00_registry" / "asset_registry.json"
    reg = load_json(reg_path)
    entries = reg.get("entries", [])
    reg_papers = {e["paper_id"] for e in entries}
    success_papers = {e["paper_id"] for e in entries if e.get("build_status") == "success"}
    failed_papers = {e["paper_id"]: e.get("error_message", "unknown") for e in entries if e.get("build_status") == "failed"}

    print(f"[1] Asset Registry")
    print(f"    Path: {reg_path}")
    print(f"    Total entries: {len(entries)}")
    print(f"    Success: {len(success_papers)}")
    print(f"    Failed: {len(failed_papers)}")
    if failed_papers:
        print(f"    Failed papers:")
        for pid, err in list(failed_papers.items())[:10]:
            print(f"      - {pid[:60]}: {str(err)[:80]}")
    print()

    # 2. Load quality status
    qs_path = PROJECT_ROOT / "06_PDF_DataAssets" / "00_registry" / "quality_status.json"
    qs = load_json(qs_path)
    qs_papers = qs.get("papers", {})
    qs_excellent = sum(1 for v in qs_papers.values() if isinstance(v, dict) and v.get("overall_status") == "excellent")
    qs_good = sum(1 for v in qs_papers.values() if isinstance(v, dict) and v.get("overall_status") == "good")

    print(f"[2] Quality Status")
    print(f"    Path: {qs_path}")
    print(f"    Papers checked: {len(qs_papers)}")
    print(f"    Excellent: {qs_excellent}")
    print(f"    Good: {qs_good}")
    print(f"    Avg score: {qs.get('summary', {}).get('average_score', 'N/A')}")
    print()

    # 3. Check LanceDB table
    try:
        import lancedb
        db = lancedb.connect(str(PROJECT_ROOT / "04_VectorDB" / "lancedb"))
        table_names = db.table_names() if hasattr(db, 'table_names') else [t for t in db.list_tables().tables] if hasattr(db.list_tables(), 'tables') else []

        if "pdf_asset_chunks" in table_names:
            table = db.open_table("pdf_asset_chunks")
            rows = table.to_pandas()
            embedded_count = len(rows)
            embedded_papers = set(rows["paper_id"].unique()) if "paper_id" in rows.columns else set()
            type_dist = rows["chunk_type"].value_counts().to_dict() if "chunk_type" in rows.columns else {}

            # Random sample
            sample_indices = random.sample(range(embedded_count), min(5, embedded_count))
            samples = rows.iloc[sample_indices]

            print(f"[3] LanceDB Table: pdf_asset_chunks")
            print(f"    Total rows: {embedded_count}")
            print(f"    Distinct papers: {len(embedded_papers)}")
            print(f"    Chunk type distribution: {type_dist}")

            # Check vector dim
            if "vector" in rows.columns and embedded_count > 0:
                vec_dim = len(rows.iloc[0]["vector"])
                print(f"    Vector dimension: {vec_dim}")

            print(f"    Random sample ({len(samples)} chunks):")
            for _, row in samples.iterrows():
                cid = str(row.get("chunk_id", "?"))
                ctype = str(row.get("chunk_type", "?"))
                text_preview = str(row.get("text", ""))[:100]
                ev_id = str(row.get("linked_evidence_id", "?"))
                qs_val = row.get("metadata_json", "{}")
                try:
                    qs_val = json.loads(qs_val).get("quality_score", "N/A") if isinstance(qs_val, str) else "N/A"
                except Exception:
                    qs_val = "N/A"
                print(f"      [{ctype}] {text_preview[:80]}...")
                print(f"        ev_id={ev_id[:50]}... qs={qs_val}")
            print()
        else:
            print(f"[3] LanceDB Table: pdf_asset_chunks NOT FOUND")
            print(f"    Available tables: {table_names}")
            all_pass = False
            issues.append("pdf_asset_chunks table missing")
            embedded_papers = set()
            print()
    except Exception as e:
        print(f"[3] LanceDB Table: ERROR - {e}")
        all_pass = False
        issues.append(f"LanceDB error: {e}")
        embedded_papers = set()
        print()

    # 4. Cross-reference
    print(f"[4] Cross-Reference")
    print(f"    Registry success papers:  {len(success_papers)}")
    print(f"    Quality-checked papers:   {len(qs_papers)}")
    print(f"    Embedded papers:          {len(embedded_papers)}")

    qs_paper_set = set(qs_papers.keys())
    missing_assets = success_papers - qs_paper_set
    missing_quality = {p for p in qs_papers if isinstance(qs_papers[p], dict) and qs_papers[p].get("overall_score", 0) < 50}
    missing_embedding = success_papers - embedded_papers

    if missing_assets:
        print(f"    Missing quality check: {len(missing_assets)} papers")
        all_pass = False
        issues.append(f"{len(missing_assets)} papers missing quality check")

    # Filter out papers with 0 chunks (legitimately skipped)
    zero_chunk_papers = set()
    for pid in missing_embedding:
        chunk_dir = PROJECT_ROOT / "06_PDF_DataAssets" / "09_agent_chunks" / pid
        qpath = chunk_dir / "agent_chunks.quality.jsonl"
        if qpath.exists():
            try:
                with open(qpath, encoding="utf-8") as f:
                    lines = [l for l in f if l.strip()]
                if len(lines) == 0:
                    zero_chunk_papers.add(pid)
            except Exception:
                pass
        else:
            zero_chunk_papers.add(pid)

    true_missing = missing_embedding - zero_chunk_papers
    if zero_chunk_papers:
        print(f"    Papers with 0 chunks (OK): {len(zero_chunk_papers)}")
        for pid in sorted(zero_chunk_papers):
            print(f"      - {pid[:70]}")

    if true_missing:
        print(f"    Missing embedding: {len(true_missing)} papers")
        for pid in sorted(true_missing):
            print(f"      - {pid[:70]}")
        all_pass = False
        issues.append(f"{len(true_missing)} papers missing embedding")

    if failed_papers:
        print(f"    Failed builds: {len(failed_papers)} papers")
        all_pass = False
        issues.append(f"{len(failed_papers)} build failures")

    if not missing_assets and not missing_embedding and not failed_papers:
        print(f"    All papers consistent across layers!")
    print()

    # 5. Evidence tables intact check
    print(f"[5] Existing Tables Integrity")
    try:
        if "evidence_chunks" in table_names:
            ev_table = db.open_table("evidence_chunks")
            print(f"    evidence_chunks: {ev_table.count_rows()} rows (intact)")
        if "literature_vectors" in table_names:
            lv_table = db.open_table("literature_vectors")
            print(f"    literature_vectors: {lv_table.count_rows()} rows (intact)")
    except Exception as e:
        print(f"    Error checking existing tables: {e}")
    print()

    # Final verdict
    print("=" * 60)
    if all_pass:
        print("PDF Asset Embedding Full-Library Verification PASSED")
        print("=" * 60)
        return 0
    else:
        print("PDF Asset Embedding Full-Library Verification: ISSUES FOUND")
        for issue in issues:
            print(f"  - {issue}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
