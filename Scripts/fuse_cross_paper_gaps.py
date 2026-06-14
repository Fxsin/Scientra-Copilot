#!/usr/bin/env python
"""Cross-Paper Gap Fusion CLI V2 — Embedding Community Detection (Phase 3.1.1).

Usage:
    python Scripts/fuse_cross_paper_gaps.py
    python Scripts/fuse_cross_paper_gaps.py --threshold 0.72
    python Scripts/fuse_cross_paper_gaps.py --threshold 0.68
    python Scripts/fuse_cross_paper_gaps.py --threshold 0.75
    python Scripts/fuse_cross_paper_gaps.py --allow-cross-type
    python Scripts/fuse_cross_paper_gaps.py --min-community-size 2
    python Scripts/fuse_cross_paper_gaps.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.ai.cross_paper_gap_fusion import (
    fuse_cross_paper_gaps,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_THRESHOLD,
    DEFAULT_MIN_COMMUNITY_SIZE,
    DEFAULT_ALLOW_CROSS_TYPE,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cross-Paper Gap Fusion V2 — Embedding Community Detection"
    )
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"Cosine similarity threshold (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--min-community-size", type=int, default=DEFAULT_MIN_COMMUNITY_SIZE,
        help=f"Minimum community size (default: {DEFAULT_MIN_COMMUNITY_SIZE})",
    )
    parser.add_argument(
        "--allow-cross-type", action="store_true", default=DEFAULT_ALLOW_CROSS_TYPE,
        help="Allow clustering across different gap types",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output result as JSON to stdout",
    )
    args = parser.parse_args()

    result = fuse_cross_paper_gaps(
        threshold=args.threshold,
        min_community_size=args.min_community_size,
        allow_cross_type=args.allow_cross_type,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    _print_report(result)
    return 0


def _print_report(result: dict) -> None:
    summary = result.get("summary", {})
    clusters = result.get("clusters", [])

    print(f"\n{'='*70}")
    print(f"  Cross-Paper Gap Fusion V2 Report")
    print(f"  Method: {summary.get('fusion_method', '?')}")
    print(f"{'='*70}")
    print(f"  Status:              {result.get('status', '?')}")
    print(f"  Total gaps:          {result.get('total_gaps', 0)}")
    print(f"  Total papers:        {result.get('total_papers', 0)}")
    print(f"  Total clusters:      {summary.get('total_clusters', 0)}")
    print(f"  Single-paper:        {summary.get('single_paper_clusters', 0)}")
    print(f"  Multi-paper:         {summary.get('multi_paper_clusters', 0)}")
    print(f"  Strong multi-paper:  {summary.get('strong_multi_paper_clusters', 0)}")
    print(f"  Average cluster size:{summary.get('average_cluster_size', 0):.2f}")
    print(f"  Largest cluster:     {summary.get('largest_cluster_size', 0)}")
    print(f"  Threshold used:      {summary.get('threshold_used', '?')}")
    print(f"  Cross-type:          {summary.get('allow_cross_type', '?')}")
    print()

    # Gap type distribution
    type_dist = summary.get("gap_type_distribution", {})
    if type_dist:
        print("  Gap Type Distribution:")
        max_count = max(type_dist.values()) if type_dist else 1
        for gtype, count in type_dist.items():
            bar_len = int(count / max_count * 40)
            bar = "█" * bar_len
            print(f"    {gtype:20s} {count:3d} {bar}")
        print()

    # Top 10 clusters
    top = sorted(clusters, key=lambda c: (-c["paper_count"], -c["confidence_mean"]))[:10]
    if top:
        print(f"  Top 10 Unified Gaps:")
        print(f"  {'#':<4} {'P':<4} {'Size':<5} {'Support':<20} {'Conf':<7} {'Sim':<7} Gap")
        print(f"  {'-'*4} {'-'*4} {'-'*5} {'-'*20} {'-'*7} {'-'*7} {'-'*50}")
        for i, c in enumerate(top, 1):
            stmt = c.get("unified_gap_statement", "")[:100]
            sim = c.get("average_similarity", 0)
            print(
                f"  {i:<4} {c['paper_count']:<4} {c['member_gap_count']:<5} "
                f"{c['support_level']:<20} {c['confidence_mean']:.2f}    "
                f"{sim:.3f}    {stmt}"
            )
        print()

    # Multi/strong details
    strong = [c for c in clusters if c["support_level"] in ("multi_paper", "strong_multi_paper")]
    if strong:
        print(f"  Multi-Paper Clusters ({len(strong)}):")
        print()
        for c in strong[:15]:
            print(f"  [{c['gap_type']}] {c['unified_gap_statement'][:120]}")
            print(f"    Papers: {c['paper_count']} | Gaps: {c['member_gap_count']} | "
                  f"Support: {c['support_level']} | Conf: {c['confidence_mean']:.2f} | "
                  f"Sim: {c.get('average_similarity', 0):.3f}")
            if c.get("semantic_keywords"):
                print(f"    Keywords: {', '.join(c['semantic_keywords'][:10])}")
            if c.get("why_it_matters_merged"):
                print(f"    Why: {c['why_it_matters_merged'][:150]}")
            print()

    print(f"  Output: {DEFAULT_OUTPUT_DIR / 'gap_clusters.json'}")
    print(f"  Summary: {DEFAULT_OUTPUT_DIR / 'gap_fusion_summary.json'}")
    print()


if __name__ == "__main__":
    sys.exit(main())
