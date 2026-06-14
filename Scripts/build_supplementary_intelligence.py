#!/usr/bin/env python
"""Build Supplementary Intelligence for papers (P4.3) — Storage Layout v3.

Usage:
    python Scripts/build_supplementary_intelligence.py --paper-id paper_xxxxx --mode rule --verbose
    python Scripts/build_supplementary_intelligence.py --paper-id paper_xxxxx --mode auto
    python Scripts/build_supplementary_intelligence.py --all --mode rule
    python Scripts/build_supplementary_intelligence.py --paper-id paper_xxxxx --embed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve_paper_ids(args) -> list[str]:
    if args.paper_id:
        return [args.paper_id]
    if args.all:
        from scientra.papers.paper_registry import load_paper_registry
        reg = load_paper_registry()
        if not reg:
            print("Error: Paper registry empty.")
            sys.exit(1)
        papers = reg if isinstance(reg, list) else reg.get("papers", [])
        return [p.get("paper_id", "") for p in papers if p.get("paper_id")]
    if args.doi:
        from scientra.papers.paper_lookup import find_paper_by_doi
        e = find_paper_by_doi(args.doi)
        if e:
            return [e["paper_id"]]
    if args.title:
        from scientra.papers.paper_lookup import find_paper_by_title
        e = find_paper_by_title(args.title, fuzzy=True)
        if e:
            return [e["paper_id"]]
    print("Error: Provide --paper-id, --all, --doi, or --title")
    sys.exit(1)


def main() -> int:
    p = argparse.ArgumentParser(description="Build Supplementary Intelligence (P4.3)")
    p.add_argument("--paper-id")
    p.add_argument("--all", action="store_true")
    p.add_argument("--doi"); p.add_argument("--title")
    p.add_argument("--mode", default="auto", choices=["auto", "llm", "rule"])
    p.add_argument("--max-chunk-size", type=int, default=1200)
    p.add_argument("--chunk-overlap", type=int, default=150)
    p.add_argument("--embed", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    paper_ids = _resolve_paper_ids(args)

    if args.dry_run:
        print("=" * 60)
        print("  DRY RUN — Supplementary Intelligence P4.3")
        print("=" * 60)
        print(f"  Papers: {len(paper_ids)}  Mode: {args.mode}  Embed: {args.embed}")
        print(f"  Chunk size: {args.max_chunk_size}  Overlap: {args.chunk_overlap}")
        for pid in paper_ids[:10]:
            print(f"    {pid}")
        if len(paper_ids) > 10:
            print(f"    ... +{len(paper_ids) - 10} more")
        print()
        return 0

    from scientra.assets.supplementary_intelligence import SupplementaryIntelligenceRunner

    total, total_supp, total_err = 0, 0, 0
    print("=" * 60)
    print("  Supplementary Intelligence — P4.3 (Storage Layout v3)")
    print("=" * 60)
    print(f"  Mode: {args.mode}  Embed: {args.embed}")
    print()

    for i, pid in enumerate(paper_ids):
        if args.verbose:
            print(f"[{i + 1}/{len(paper_ids)}] {pid}")
        try:
            runner = SupplementaryIntelligenceRunner(
                mode=args.mode, max_chunk_size=args.max_chunk_size,
                chunk_overlap=args.chunk_overlap, embed=args.embed,
            )
            result = runner.run(pid, force=args.force)
            if result.get("success"):
                total += 1
                sc = result.get("supplementary_count", 0)
                total_supp += sc
                if args.verbose:
                    print(f"  Files: {sc}  Sections: {result.get('total_sections', 0)}  Evidence: {result.get('total_evidence', 0)}  Chunks: {result.get('total_chunks', 0)}  Mode: {result.get('mode_used', '?')}")
                    print()
            else:
                total_err += 1
                if args.verbose:
                    print(f"  {result.get('error', result.get('message', 'Unknown'))}")
                    print()
        except Exception as e:
            total_err += 1
            if args.verbose:
                print(f"  Exception: {e}")
                print()

    print("=" * 60)
    print(f"  Papers: {total}  Files: {total_supp}  Errors: {total_err}")
    print(f"  Output: {runner._v3_path('03_Assets/supplementary_intelligence') if total > 0 else 'N/A'}")
    print()
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
