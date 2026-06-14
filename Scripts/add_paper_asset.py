#!/usr/bin/env python
"""Add supplementary assets to an existing paper (Phase 4.0.1).

Usage:
    # By paper ID
    python Scripts/add_paper_asset.py --paper-id paper_xxx --file "supplementary.pdf"

    # By DOI
    python Scripts/add_paper_asset.py --doi "10.xxxx/xxxx" --file "Table_S1.xlsx"

    # By title
    python Scripts/add_paper_asset.py --title "Transgenic cotton coexpressing Vip3A" --dir "supplementary_files/"

    # By query
    python Scripts/add_paper_asset.py --query "Vip3A cotton" --file "supplementary.pdf"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve_paper_id(args) -> str:
    """Resolve paper_id from CLI arguments.

    Priority: --paper-id > --doi > --title > --query
    """
    if args.paper_id:
        return args.paper_id

    from scientra.papers.paper_lookup import (
        find_paper_by_doi,
        find_paper_by_title,
        search_papers,
        find_paper_by_id,
    )

    if args.doi:
        entry = find_paper_by_doi(args.doi)
        if entry:
            pid = entry["paper_id"]
            print(f"  DOI resolved: {args.doi} -> {pid} ({entry.get('title', '')[:60]})")
            return pid
        print(f"  Error: DOI not found: {args.doi}")
        sys.exit(1)

    if args.title:
        entry = find_paper_by_title(args.title, fuzzy=True)
        if entry:
            pid = entry["paper_id"]
            print(f"  Title resolved: '{args.title[:60]}' -> {pid}")
            return pid
        print(f"  Error: Title not found: {args.title[:60]}")
        sys.exit(1)

    if args.query:
        results = search_papers(args.query, limit=10)
        if len(results) == 0:
            print(f"  Error: No papers match query: {args.query}")
            sys.exit(1)
        if len(results) == 1:
            entry = results[0]
            pid = entry["paper_id"]
            print(f"  Query resolved: '{args.query}' -> {pid} ({entry.get('title', '')[:60]})")
            return pid

        # Multiple matches — show candidates
        print(f"\n  Multiple papers match '{args.query}':\n")
        print(f"  {'#':<4} {'Title':<50} {'Year':<6} {'DOI':<30}")
        print(f"  {'-'*4} {'-'*50} {'-'*6} {'-'*30}")
        for i, entry in enumerate(results[:10], 1):
            title = entry.get("title", "")[:48]
            year = entry.get("year", "")
            doi = entry.get("doi", "")[:28]
            print(f"  {i:<4} {title:<50} {year:<6} {doi:<30}")

        print(f"\n  Please re-run with --paper-id <id> or narrow your query.")
        print(f"  Example paper IDs:")
        for entry in results[:3]:
            print(f"    --paper-id {entry['paper_id']}  ({entry.get('title', '')[:50]})")
        sys.exit(1)

    print("  Error: Provide --paper-id, --doi, --title, or --query")
    sys.exit(1)


def main() -> int:
    p = argparse.ArgumentParser(description="Add assets to a paper")
    p.add_argument("--paper-id", help="Paper ID (e.g., paper_d0cf4389f4ef6e06)")
    p.add_argument("--doi", help="Resolve paper by DOI")
    p.add_argument("--title", help="Resolve paper by title (fuzzy match)")
    p.add_argument("--query", help="Search papers by query string")
    p.add_argument("--file", help="Path to a single file to add")
    p.add_argument("--dir", help="Path to a directory of files to add")
    p.add_argument("--asset-type", help="Override asset type classification")
    p.add_argument("--copy-mode", default="copy", choices=["copy", "move"])
    p.add_argument("--source", default="manual_upload")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not args.file and not args.dir:
        print("Error: --file or --dir required.")
        return 1

    # Resolve paper_id
    paper_id = _resolve_paper_id(args)

    # Show workspace info
    from scientra.papers.paper_registry import get_paper_entry
    entry = get_paper_entry(paper_id)
    if entry:
        print(f"  Paper:   {entry.get('title', '')[:70]}")
        print(f"  Year:    {entry.get('year', '')}")
        print(f"  Workspace: {entry.get('source_dir', '')}")

    files_to_add: list[Path] = []
    if args.file:
        fp = Path(args.file).resolve()
        if not fp.exists():
            print(f"Error: File not found: {args.file}")
            return 1
        files_to_add.append(fp)
    if args.dir:
        dp = Path(args.dir).resolve()
        if not dp.is_dir():
            print(f"Error: Directory not found: {args.dir}")
            return 1
        files_to_add.extend(sorted(dp.iterdir()))

    if args.dry_run:
        print(f"\n  DRY RUN -- {len(files_to_add)} file(s) would be added to {paper_id}")
        for f in files_to_add:
            print(f"    {f.name}")
        print()
        return 0

    from scientra.assets.asset_storage import register_asset_for_paper

    registered = 0
    skipped = 0
    results: list[dict] = []

    for fp in files_to_add:
        if not fp.is_file():
            continue
        try:
            asset = register_asset_for_paper(
                paper_id=paper_id,
                file_path=str(fp),
                asset_type=args.asset_type,
                source=args.source,
                copy_mode=args.copy_mode,
            )
            result = asset.to_dict()
            results.append(result)
            if asset.status == "skipped":
                skipped += 1
            else:
                registered += 1
        except Exception as e:
            results.append({"file": fp.name, "error": str(e)})
            skipped += 1

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  Asset Registration: {paper_id}")
    print(f"{sep}")
    print(f"  Registered:  {registered}")
    print(f"  Skipped:     {skipped}")

    for r in results:
        aid = r.get("asset_id", "ERROR")
        fname = r.get("filename", r.get("file", "?"))
        atype = r.get("asset_type", "?")
        status = r.get("status", "?")
        warnings = r.get("warnings", [])
        errors = r.get("error", [])
        err = f"  ERROR: {errors}" if errors else ""
        print(f"  [{status}] {aid}  {fname}  ({atype}){err}")
        for w in (warnings or []):
            print(f"         Warning: {w}")

    # Show actual registry path
    from scientra.assets.asset_registry import get_registry_path
    reg_path = get_registry_path(paper_id)
    print(f"\n  Registry: {reg_path}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
