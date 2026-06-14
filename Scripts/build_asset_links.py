#!/usr/bin/env python
"""Build asset links for a paper (P4.0.4 Asset Linking Engine).

Usage:
    # Single paper (dry run)
    python Scripts/build_asset_links.py --paper-id paper_xxxxx --dry-run

    # Single paper
    python Scripts/build_asset_links.py --paper-id paper_xxxxx

    # Single paper with verbose output
    python Scripts/build_asset_links.py --paper-id paper_xxxxx --verbose

    # Force rebuild (overwrite existing)
    python Scripts/build_asset_links.py --paper-id paper_xxxxx --force

    # All papers
    python Scripts/build_asset_links.py --all

    # All papers with dry run
    python Scripts/build_asset_links.py --all --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve_paper_ids(args) -> list[str]:
    """Resolve paper IDs from CLI arguments."""
    if args.paper_id:
        return [args.paper_id]

    if args.all:
        from scientra.papers.paper_registry import load_paper_registry
        reg = load_paper_registry()
        if not reg:
            print("Error: Paper registry is empty.")
            sys.exit(1)
        return [entry["paper_id"] for entry in reg.get("papers", [])]

    # Try resolving by DOI, title, or query
    if args.doi or args.title or args.query:
        from scientra.papers.paper_lookup import (
            find_paper_by_doi,
            find_paper_by_title,
            search_papers,
        )
        if args.doi:
            entry = find_paper_by_doi(args.doi)
            if entry:
                return [entry["paper_id"]]
        if args.title:
            entry = find_paper_by_title(args.title, fuzzy=True)
            if entry:
                return [entry["paper_id"]]
        if args.query:
            results = search_papers(args.query, limit=1)
            if results:
                return [results[0]["paper_id"]]

    print("Error: Provide --paper-id, --all, --doi, --title, or --query")
    sys.exit(1)


def _resolve_paper_id(args) -> str:
    """Resolve a single paper_id from CLI arguments."""
    ids = _resolve_paper_ids(args)
    if len(ids) > 1 and args.paper_id is None and args.all:
        # --all flag, but called from single-paper path
        pass
    return ids[0]


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build asset links for papers (P4.0.4 Asset Linking Engine)",
    )
    p.add_argument("--paper-id", help="Paper ID (e.g., paper_d0cf4389f4ef6e06)")
    p.add_argument("--all", action="store_true", help="Process all papers in registry")
    p.add_argument("--doi", help="Resolve paper by DOI")
    p.add_argument("--title", help="Resolve paper by title (fuzzy match)")
    p.add_argument("--query", help="Search papers by query string")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    p.add_argument("--force", action="store_true", help="Force rebuild, overwrite existing outputs")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    args = p.parse_args()

    # Resolve paper IDs
    paper_ids = _resolve_paper_ids(args)

    if args.dry_run:
        print("=" * 60)
        print("  DRY RUN — Asset Linking Engine")
        print("=" * 60)
        print(f"  Papers to process: {len(paper_ids)}")
        for pid in paper_ids[:10]:
            print(f"    {pid}")
        if len(paper_ids) > 10:
            print(f"    ... and {len(paper_ids) - 10} more")
        print()

        if args.verbose:
            # Show what would happen for each paper
            from scientra.assets.linking import CitationParser, AssetGraphBuilder
            builder = AssetGraphBuilder()
            for pid in paper_ids[:5]:
                parser = CitationParser(builder.root)
                mentions = parser.parse_all_sources(pid)
                print(f"  {pid}: {len(mentions)} citations found (dry run)")
        print()
        return 0

    from scientra.assets.linking import AssetGraphBuilder

    builder = AssetGraphBuilder()
    total_processed = 0
    total_citations = 0
    total_links = 0
    total_errors = 0

    print("=" * 60)
    print("  Asset Linking Engine — P4.0.4")
    print("=" * 60)
    print()

    for i, paper_id in enumerate(paper_ids):
        if args.verbose:
            print(f"[{i + 1}/{len(paper_ids)}] Processing: {paper_id}")

        try:
            result = builder.build(paper_id, force=args.force)

            if result.get("success"):
                total_processed += 1
                total_citations += result.get("citation_count", 0)
                total_links += result.get("link_count", 0)

                if args.verbose:
                    print(f"  Citations:    {result.get('citation_count', 0)}")
                    print(f"  Links:        {result.get('link_count', 0)}")
                    print(f"  Evidence:     {result.get('evidence_link_count', 0)}")
                    print(f"  Unmatched:    {result.get('unmatched_asset_count', 0)}")
                    print(f"  Low conf:     {result.get('low_confidence_count', 0)}")
                    methods = result.get("match_methods", {})
                    if methods:
                        print(f"  Methods:      {methods}")
                    print()
            else:
                total_errors += 1
                if args.verbose:
                    print(f"  Error: {result.get('error', 'Unknown error')}")
                    print()
        except Exception as e:
            total_errors += 1
            if args.verbose:
                print(f"  Exception: {e}")
                print()

    sep = "=" * 60
    print(sep)
    print(f"  Summary")
    print(sep)
    print(f"  Papers processed:  {total_processed}")
    print(f"  Total citations:   {total_citations}")
    print(f"  Total links:       {total_links}")
    print(f"  Errors:            {total_errors}")
    print()
    print(f"  Output files are in: {{paper_dir}}/links/")
    print(f"    - citation_mentions.json")
    print(f"    - asset_links.json")
    print(f"    - evidence_asset_links.json")
    print(f"    - unmatched_assets.json")
    print(f"    - unmatched_mentions.json")
    print(f"    - low_confidence_links.json")
    print(f"    - asset_graph_summary.md")
    print()

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
