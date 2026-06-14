#!/usr/bin/env python
"""Initialize paper_assets.json for all existing papers (Phase 4.0).

Usage:
    python Scripts/init_paper_assets.py
    python Scripts/init_paper_assets.py --dry-run
    python Scripts/init_paper_assets.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.assets.asset_registry import (
    init_registry_for_paper,
    load_registry,
    get_paper_dir,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Initialize paper asset registries")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    project_root = Path(__file__).resolve().parent.parent

    # Load all paper metadata
    import yaml
    yaml_dir = project_root / "02_Metadata" / "yaml"
    pdf_dir = project_root / "01_PDF"

    papers: list[dict] = []
    if yaml_dir.exists():
        for yf in sorted(yaml_dir.glob("*.metadata.yaml")):
            try:
                doc = yaml.safe_load(yf.read_text(encoding="utf-8"))
                if doc:
                    papers.append(doc)
            except Exception:
                pass

    if not papers:
        print("No paper metadata found.")
        return 1

    # Stats
    registries_created = 0
    registries_updated = 0
    missing_main_pdf = 0
    errors = 0
    details: list[dict] = []

    for paper in papers:
        paper_id = paper.get("paper_id", "")
        key = paper.get("key", "")
        if not paper_id:
            continue

        # Find main PDF
        main_pdf_path = None
        # Try matching by key (stem) in 01_PDF
        if key and pdf_dir.exists():
            candidate = pdf_dir / f"{key}.pdf"
            if candidate.exists():
                main_pdf_path = str(candidate)

        # Also try matching by paper_id hash in filename
        if not main_pdf_path and pdf_dir.exists():
            short_hash = paper_id.replace("paper_", "") if paper_id.startswith("paper_") else paper_id
            for pdf_file in pdf_dir.glob("*.pdf"):
                if short_hash[:8] in pdf_file.stem:
                    main_pdf_path = str(pdf_file)
                    break

        if args.dry_run:
            existing = load_registry(paper_id)
            detail = {
                "paper_id": paper_id,
                "key": key,
                "title": str(paper.get("title", ""))[:80],
                "main_pdf_found": main_pdf_path is not None,
                "registry_exists": existing is not None,
            }
            details.append(detail)
            if not main_pdf_path:
                missing_main_pdf += 1
            if existing:
                registries_updated += 1
            continue

        try:
            existing = load_registry(paper_id)
            if existing:
                # Update if no main_pdf registered
                if not existing.main_pdf and main_pdf_path:
                    existing.main_pdf = {
                        "asset_id": "main_pdf",
                        "paper_id": paper_id,
                        "asset_type": "main_pdf",
                        "filename": Path(main_pdf_path).name,
                        "original_filename": Path(main_pdf_path).name,
                        "relative_path": "",
                        "source_path": str(Path(main_pdf_path).resolve()),
                        "sha256": "",
                        "size_bytes": Path(main_pdf_path).stat().st_size,
                        "mime_type": "application/pdf",
                        "extension": ".pdf",
                        "source": "initial_import",
                        "status": "registered",
                        "created_at": existing.last_updated,
                        "updated_at": existing.last_updated,
                        "notes": "Main PDF — linked from 01_PDF",
                    }
                    from scientra.assets.asset_registry import save_registry
                    save_registry(existing)
                registries_updated += 1
            else:
                init_registry_for_paper(paper_id, main_pdf_path)
                registries_created += 1

            if not main_pdf_path:
                missing_main_pdf += 1
        except Exception:
            errors += 1

    if args.json:
        print(json.dumps({
            "total_papers": len(papers),
            "registries_created": registries_created,
            "registries_updated": registries_updated,
            "missing_main_pdf": missing_main_pdf,
            "errors": errors,
            "details": details if args.dry_run else [],
        }, ensure_ascii=False, indent=2))
        return 0

    _sep = "=" * 60
    print(f"\n{_sep}")
    print("  Paper Asset Registry Initialization")
    print(f"{_sep}")
    print(f"  Total papers:             {len(papers)}")
    if args.dry_run:
        print(f"  Registries exist:         {registries_updated}")
        print(f"  Registries to create:     {len(papers) - registries_updated}")
    else:
        print(f"  Registries created:       {registries_created}")
        print(f"  Registries updated:       {registries_updated}")
    print(f"  Missing main PDF:         {missing_main_pdf}")
    print(f"  Errors:                   {errors}")

    if args.dry_run and details:
        print(f"\n  Paper Details:")
        for d in details[:10]:
            status = "EXISTS" if d["registry_exists"] else "NEW"
            pdf = "PDF" if d["main_pdf_found"] else "NO_PDF"
            print(f"    [{status}] [{pdf}] {d['paper_id']}  {d['title'][:60]}")
        if len(details) > 10:
            print(f"    ... and {len(details) - 10} more")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
