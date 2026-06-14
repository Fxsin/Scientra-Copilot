#!/usr/bin/env python
"""
P1.5 — Evidence Input Comparison CLI.

Compare evidence extraction results between legacy raw text and hybrid
final markdown WITHOUT modifying the main pipeline.

Usage:
    python Scripts/compare_evidence_inputs.py --paper-id paper_001
    python Scripts/compare_evidence_inputs.py --all --limit 20
    python Scripts/compare_evidence_inputs.py --all --min-quality 0.70
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve_root() -> Path:
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "Config" / "workflow_config.yaml").exists():
        return candidate
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare evidence extraction: legacy raw text vs hybrid final markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Scripts/compare_evidence_inputs.py --paper-id paper_001
  python Scripts/compare_evidence_inputs.py --all --limit 20
  python Scripts/compare_evidence_inputs.py --all --min-quality 0.70
  python Scripts/compare_evidence_inputs.py --paper-id paper_001 --json
        """,
    )
    parser.add_argument(
        "--paper-id", type=str, default=None,
        help="Compare a single paper by ID",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Compare all papers with hybrid final markdown",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit number of papers when using --all",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Output directory (default: 02_Parse/reports/hybrid_validation/)",
    )
    parser.add_argument(
        "--min-quality", type=float, default=0.65,
        help="Minimum hybrid parse quality score to include (default: 0.65)",
    )
    parser.add_argument(
        "--root", type=Path, default=None,
        help="Project root directory (auto-detected if not specified)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON instead of human-readable format",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else _resolve_root()

    if not args.paper_id and not args.all:
        parser.print_help()
        print("\nError: Specify --paper-id or --all", file=sys.stderr)
        return 2

    from scientra.parsers.evidence_input_comparison import (
        compare_all_papers,
        compare_evidence_inputs,
    )

    if args.paper_id:
        # -- Single paper mode --
        report = compare_evidence_inputs(
            paper_id=args.paper_id,
            root=root,
        )

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_single_report(report)

        return 0

    elif args.all:
        # -- Batch mode --
        print(f"Running comparison on up to {args.limit or 'all'} papers...")
        summary = compare_all_papers(
            root=root,
            limit=args.limit,
            min_quality=args.min_quality,
        )

        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            _print_summary_report(summary)

        return 0

    return 1


def _print_single_report(report: dict[str, Any]) -> None:
    """Print a human-readable single-paper comparison report."""
    paper_id = report.get("paper_id", "unknown")
    rec = report.get("recommendation", "insufficient_data")
    sources = report.get("sources", {})
    comp = report.get("comparison", {})

    rec_label = {
        "use_hybrid_markdown": "[HYBRID] Use Hybrid Markdown",
        "use_legacy_raw_text": "[LEGACY] Use Legacy Raw Text",
        "manual_review": "[REVIEW] Manual Review Needed",
        "insufficient_data": "[NODATA] Insufficient Data",
    }.get(rec, rec)

    print(f"\n{'='*60}")
    print(f"  Evidence Input Comparison: {paper_id}")
    print(f"{'='*60}")
    print(f"  Recommendation: {rec_label}")
    print()

    # Sources
    print("  -- Sources --")
    print(f"  Legacy text available:    {sources.get('legacy_raw_text_available', False)}")
    print(f"  Hybrid markdown available: {sources.get('hybrid_final_markdown_available', False)}")
    print(f"  Hybrid parse quality:     {sources.get('hybrid_parse_quality_score', 0):.2f}")
    print()

    # Legacy stats
    legacy = report.get("legacy", {})
    if legacy.get("status") == "success":
        lt = legacy.get("text_stats", {})
        le = legacy.get("evidence_stats", {})
        ls = legacy.get("section_stats", {})
        print("  -- Legacy Raw Text --")
        print(f"  Text length:        {lt.get('text_length', 0):,}")
        print(f"  Headings:           {lt.get('heading_count', 0)}")
        print(f"  Figure refs:        {lt.get('figure_reference_count', 0)}")
        print(f"  Table refs:         {lt.get('table_reference_count', 0)}")
        print(f"  Malformed ratio:    {lt.get('malformed_text_ratio', 0):.6f}")
        print(f"  Sections detected:  {ls.get('section_count', 0)}")
        print(f"  Methods found:      {ls.get('method_section_detected', False)}")
        print(f"  Results found:      {ls.get('result_section_detected', False)}")
        print(f"  Total evidence:     {le.get('total_evidence_count', 0)}")
        print(f"  Key results:        {le.get('key_results_count', 0)}")
        print(f"  Methods extracted:  {le.get('methods_count', 0)}")
        print()

    # Hybrid stats
    hybrid = report.get("hybrid", {})
    if hybrid.get("status") == "success":
        ht = hybrid.get("text_stats", {})
        he = hybrid.get("evidence_stats", {})
        hs = hybrid.get("section_stats", {})
        print("  -- Hybrid Final Markdown --")
        print(f"  Text length:        {ht.get('text_length', 0):,}")
        print(f"  Headings:           {ht.get('heading_count', 0)}")
        print(f"  Figure refs:        {ht.get('figure_reference_count', 0)}")
        print(f"  Table refs:         {ht.get('table_reference_count', 0)}")
        print(f"  Malformed ratio:    {ht.get('malformed_text_ratio', 0):.6f}")
        print(f"  Sections detected:  {hs.get('section_count', 0)}")
        print(f"  Methods found:      {hs.get('method_section_detected', False)}")
        print(f"  Results found:      {hs.get('result_section_detected', False)}")
        print(f"  Total evidence:     {he.get('total_evidence_count', 0)}")
        print(f"  Key results:        {he.get('key_results_count', 0)}")
        print(f"  Methods extracted:  {he.get('methods_count', 0)}")
        print()

    # Comparison deltas
    if comp and "text_length_delta" in comp:
        print("  -- Deltas (Hybrid - Legacy) --")
        print(f"  Text length:        {comp.get('text_length_delta', 0):+,}")
        print(f"  Text ratio:         {comp.get('text_length_ratio', 0):.2%}")
        print(f"  Headings:           {comp.get('heading_count_delta', 0):+}")
        print(f"  Malformed ratio:    {comp.get('malformed_text_ratio_delta', 0):+.6f}")
        print(f"  Evidence count:     {comp.get('evidence_count_delta', 0):+}")
        print(f"  Evidence ratio:     {comp.get('evidence_count_ratio', 0):.2%}")
        print(f"  Sections:           {comp.get('section_count_delta', 0):+}")
        print(f"  Figure refs:        {comp.get('figure_reference_delta', 0):+}")
        print(f"  Table refs:         {comp.get('table_reference_delta', 0):+}")
        print()

    print(f"  Report saved to: {report.get('_report_path', 'N/A')}")
    print()


def _print_summary_report(summary: dict[str, Any]) -> None:
    """Print a human-readable batch summary report."""
    total = summary.get("total_papers_compared", 0)
    recs = summary.get("recommendations", {})

    print(f"\n{'='*60}")
    print(f"  Evidence Input Comparison — Batch Summary")
    print(f"{'='*60}")
    print(f"  Papers compared:              {total}")
    print(f"  Avg hybrid quality score:     {summary.get('average_hybrid_quality_score', 0):.3f}")
    print(f"  Avg legacy evidence count:    {summary.get('average_legacy_evidence_count', 0):.1f}")
    print(f"  Avg hybrid evidence count:    {summary.get('average_hybrid_evidence_count', 0):.1f}")
    print()
    print("  -- Recommendations --")
    print(f"  [HYBRID] Use Hybrid:     {recs.get('use_hybrid_markdown', 0)} ({summary.get('hybrid_recommended_pct', 0):.1f}%)")
    print(f"  [LEGACY] Use Legacy:     {recs.get('use_legacy_raw_text', 0)} ({summary.get('legacy_recommended_pct', 0):.1f}%)")
    print(f"  [REVIEW] Manual Review:  {recs.get('manual_review', 0)} ({summary.get('manual_review_pct', 0):.1f}%)")
    print(f"  [NODATA] Insufficient:   {recs.get('insufficient_data', 0)}")
    print()

    top_failures = summary.get("top_failure_reasons", {})
    if top_failures:
        print("  -- Top Failure Reasons --")
        for reason, count in top_failures.items():
            print(f"  {reason[:80]}: {count}")
        print()

    print(f"  Summary saved to: {summary.get('_summary_path', 'N/A')}")
    print()

    # Quick recommendation on whether to enable prefer_hybrid
    hybrid_pct = summary.get("hybrid_recommended_pct", 0)
    manual_pct = summary.get("manual_review_pct", 0)
    avg_hybrid_ev = summary.get("average_hybrid_evidence_count", 0)
    avg_legacy_ev = summary.get("average_legacy_evidence_count", 0)

    if hybrid_pct >= 70 and manual_pct <= 20 and avg_hybrid_ev >= avg_legacy_ev * 0.7:
        print("  [READY] Set prefer_hybrid_markdown_for_evidence: true")
        print(f"     {hybrid_pct:.0f}% of papers recommend hybrid markdown.")
        print(f"     Only {manual_pct:.0f}% need manual review.")
    elif hybrid_pct >= 50:
        print("  [CONDITIONAL] Enable with monitoring. Manual review rate is elevated.")
    else:
        print("  [NOT-YET] Hybrid markdown quality is not consistently better than legacy.")
        print("     Continue using legacy raw text for evidence extraction.")


if __name__ == "__main__":
    raise SystemExit(main())
