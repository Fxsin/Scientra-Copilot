#!/usr/bin/env python
"""Build Figure Intelligence for papers (P4.1).

Usage:
    # Single paper — rule mode
    python Scripts/build_figure_intelligence.py --paper-id paper_xxxxx --mode rule --verbose

    # Single paper — auto mode (try LLM, fallback to rule)
    python Scripts/build_figure_intelligence.py --paper-id paper_xxxxx --mode auto

    # Single paper — LLM mode
    python Scripts/build_figure_intelligence.py --paper-id paper_xxxxx --mode llm

    # Dry run
    python Scripts/build_figure_intelligence.py --paper-id paper_xxxxx --mode rule --dry-run

    # Force rebuild
    python Scripts/build_figure_intelligence.py --paper-id paper_xxxxx --force

    # All papers
    python Scripts/build_figure_intelligence.py --all --mode rule
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
        papers = reg if isinstance(reg, list) else reg.get("papers", [])
        return [p.get("paper_id", "") for p in papers if p.get("paper_id")]

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


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build Figure Intelligence for papers (P4.1)",
    )
    p.add_argument("--paper-id", help="Paper ID")
    p.add_argument("--all", action="store_true", help="Process all papers")
    p.add_argument("--doi", help="Resolve paper by DOI")
    p.add_argument("--title", help="Resolve paper by title (fuzzy)")
    p.add_argument("--query", help="Search papers by query")
    p.add_argument("--mode", default="auto", choices=["auto", "llm", "rule"],
                   help="Interpretation mode (default: auto)")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p.add_argument("--force", action="store_true", help="Force rebuild, overwrite existing")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    args = p.parse_args()

    paper_ids = _resolve_paper_ids(args)

    if args.dry_run:
        print("=" * 60)
        print("  DRY RUN — Figure Intelligence P4.1")
        print("=" * 60)
        print(f"  Papers to process: {len(paper_ids)}")
        print(f"  Mode: {args.mode}")
        for pid in paper_ids[:10]:
            print(f"    {pid}")
        if len(paper_ids) > 10:
            print(f"    ... and {len(paper_ids) - 10} more")
        print()
        return 0

    from scientra.assets.figure_intelligence import FigureIntelligenceRunner

    total_processed = 0
    total_figures = 0
    total_errors = 0
    all_modes: dict[str, int] = {}

    print("=" * 60)
    print("  Figure Intelligence — P4.1")
    print("=" * 60)
    print(f"  Mode: {args.mode}")
    print()

    for i, paper_id in enumerate(paper_ids):
        if args.verbose:
            print(f"[{i + 1}/{len(paper_ids)}] {paper_id}")

        try:
            runner = FigureIntelligenceRunner(mode=args.mode)
            result = runner.run(paper_id, force=args.force)

            if result.get("success"):
                total_processed += 1
                fc = result.get("figure_count", 0)
                total_figures += fc
                mode_used = result.get("mode_used", "?")
                all_modes[mode_used] = all_modes.get(mode_used, 0) + 1

                if args.verbose:
                    print(f"  Figures:      {fc}")
                    print(f"  Mode used:    {mode_used}")
                    ev_types = result.get("evidence_types", {})
                    if ev_types:
                        print(f"  Types:        {dict(sorted(ev_types.items()))}")
                    qd = result.get("quality_distribution", {})
                    if qd:
                        print(f"  Quality:      {qd}")
                    oc = result.get("overclaim_summary", {})
                    if oc:
                        print(f"  Overclaim:    {oc}")
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
    print(f"  Total figures:     {total_figures}")
    print(f"  Errors:            {total_errors}")
    print(f"  Modes used:        {all_modes}")
    print()
    print(f"  Output: {{paper_dir}}/figure_intelligence/")
    print(f"    - figure_contexts.json")
    print(f"    - figure_interpretations.json")
    print(f"    - figure_cards.json")
    print(f"    - figure_quality_report.json")
    print(f"    - figure_intelligence_summary.md")
    print()

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
