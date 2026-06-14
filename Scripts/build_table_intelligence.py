#!/usr/bin/env python
"""Build Table Intelligence for papers (P4.2).

Usage:
    python Scripts/build_table_intelligence.py --paper-id paper_xxxxx --mode rule --verbose
    python Scripts/build_table_intelligence.py --paper-id paper_xxxxx --mode auto
    python Scripts/build_table_intelligence.py --paper-id paper_xxxxx --mode llm
    python Scripts/build_table_intelligence.py --all --mode rule
    python Scripts/build_table_intelligence.py --paper-id paper_xxxxx --max-sample-rows 30
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
            print("Error: Paper registry is empty.")
            sys.exit(1)
        papers = reg if isinstance(reg, list) else reg.get("papers", [])
        return [p.get("paper_id", "") for p in papers if p.get("paper_id")]
    if args.doi or args.title or args.query:
        from scientra.papers.paper_lookup import find_paper_by_doi, find_paper_by_title, search_papers
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


def main() -> int:
    p = argparse.ArgumentParser(description="Build Table Intelligence for papers (P4.2)")
    p.add_argument("--paper-id")
    p.add_argument("--all", action="store_true")
    p.add_argument("--doi"); p.add_argument("--title"); p.add_argument("--query")
    p.add_argument("--mode", default="auto", choices=["auto", "llm", "rule"])
    p.add_argument("--max-sample-rows", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    paper_ids = _resolve_paper_ids(args)

    if args.dry_run:
        print("=" * 60)
        print("  DRY RUN — Table Intelligence P4.2")
        print("=" * 60)
        print(f"  Papers: {len(paper_ids)}  Mode: {args.mode}  Sample rows: {args.max_sample_rows}")
        for pid in paper_ids[:10]:
            print(f"    {pid}")
        if len(paper_ids) > 10:
            print(f"    ... and {len(paper_ids) - 10} more")
        print()
        return 0

    from scientra.assets.table_intelligence import TableIntelligenceRunner

    total_processed = 0
    total_tables = 0
    total_errors = 0

    print("=" * 60)
    print("  Table Intelligence — P4.2")
    print("=" * 60)
    print(f"  Mode: {args.mode}  Sample rows: {args.max_sample_rows}")
    print()

    for i, paper_id in enumerate(paper_ids):
        if args.verbose:
            print(f"[{i + 1}/{len(paper_ids)}] {paper_id}")

        try:
            runner = TableIntelligenceRunner(mode=args.mode, max_sample_rows=args.max_sample_rows)
            result = runner.run(paper_id, force=args.force)
            if result.get("success"):
                total_processed += 1
                tc = result.get("table_count", 0)
                total_tables += tc
                if args.verbose:
                    print(f"  Tables:       {tc}")
                    print(f"  Mode used:    {result.get('mode_used', '?')}")
                    types = result.get("table_types", {})
                    if types:
                        print(f"  Types:        {dict(sorted(types.items()))}")
                    qd = result.get("quality_distribution", {})
                    if qd:
                        print(f"  Quality:      {qd}")
                    print()
            else:
                total_errors += 1
                if args.verbose:
                    print(f"  Error: {result.get('error', 'Unknown')}")
                    print()
        except Exception as e:
            total_errors += 1
            if args.verbose:
                print(f"  Exception: {e}")
                print()

    print("=" * 60)
    print(f"  Papers processed:  {total_processed}")
    print(f"  Total tables:      {total_tables}")
    print(f"  Errors:            {total_errors}")
    print()
    print(f"  Output: {{paper_dir}}/table_intelligence/")
    print(f"    - table_contexts.json, table_structures.json, table_schemas.json")
    print(f"    - table_statistics.json, table_interpretations.json")
    print(f"    - table_cards.json, table_quality_report.json")
    print(f"    - table_intelligence_summary.md")
    print()
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
