#!/usr/bin/env python
"""Cross-Paper Hypothesis Fusion CLI (Phase 3.2).

Usage:
    python Scripts/fuse_cross_paper_hypotheses.py
    python Scripts/fuse_cross_paper_hypotheses.py --threshold 0.72
    python Scripts/fuse_cross_paper_hypotheses.py --min-community-size 2
    python Scripts/fuse_cross_paper_hypotheses.py --json
"""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.ai.cross_paper_hypothesis_fusion import (
    fuse_cross_paper_hypotheses,
    DEFAULT_THRESHOLD, DEFAULT_MIN_COMMUNITY_SIZE,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Cross-Paper Hypothesis Fusion")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--min-community-size", type=int, default=DEFAULT_MIN_COMMUNITY_SIZE)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = fuse_cross_paper_hypotheses(
        threshold=args.threshold, min_community_size=args.min_community_size,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    _print_report(result)
    return 0


def _print_report(result: dict) -> None:
    summary = result.get("summary", {})
    quality = result.get("quality", {})
    clusters = result.get("hypothesis_clusters", [])

    print(f"\n{'='*70}")
    print("  Cross-Paper Hypothesis Fusion Report")
    print(f"  Method: {summary.get('fusion_method', '?')} (BGE-M3 + community_detection)")
    print(f"{'='*70}")
    print(f"  Total hypotheses:          {result.get('total_hypotheses', 0)}")
    print(f"  Total clusters:            {summary.get('total_hypothesis_clusters', 0)}")
    print(f"  Multi-paper:               {summary.get('multi_paper_hypothesis_clusters', 0)}")
    print(f"  Strong multi-paper:        {summary.get('strong_multi_paper_hypothesis_clusters', 0)}")
    print(f"  Threshold:                 {summary.get('threshold_used', '?')}")
    print()

    # Quality
    print("  Quality:")
    print(f"    Recommendation:          {quality.get('recommendation', '?').upper()}")
    print(f"    Average score:            {quality.get('average_quality_score', 0):.3f}")
    print(f"    Invalid links:            {quality.get('invalid_gap_cluster_links', 0)}")
    print(f"    High risk hyps:           {quality.get('high_risk_hypothesis_count', 0)}")
    print(f"    Overclaim:                {quality.get('overclaim_risk_count', 0)}")
    print(f"    Low confidence:           {quality.get('low_confidence_cluster_count', 0)}")
    print(f"    Missing predictions:      {quality.get('missing_testable_prediction_count', 0)}")
    print()

    # Top 10
    top = sorted(clusters, key=lambda c: (-c["paper_count"], -c["confidence_mean"]))[:10]
    if top:
        print(f"  Top 10 Unified Hypotheses:")
        print(f"  {'#':<4} {'P':<4} {'Gaps':<5} {'Risk':<16} {'Conf':<7} Hypothesis")
        print(f"  {'-'*4} {'-'*4} {'-'*5} {'-'*16} {'-'*7} {'-'*55}")
        for i, c in enumerate(top, 1):
            rd = c.get("risk_level_distribution", {})
            risk_str = f"L:{rd.get('low',0)} M:{rd.get('medium',0)} H:{rd.get('high',0)}"
            stmt = c.get("unified_hypothesis_statement", "")[:110]
            print(f"  {i:<4} {c['paper_count']:<4} {c['gap_count']:<5} "
                  f"{risk_str:<16} {c['confidence_mean']:.2f}    {stmt}")
        print()

    # Multi/strong details
    strong = [c for c in clusters if c["support_level"] in ("multi_paper", "strong_multi_paper")]
    if strong:
        print(f"  Multi-Paper Hypothesis Clusters ({len(strong)}):")
        for c in strong[:8]:
            print(f"\n  [{c['support_level']}] {c['unified_hypothesis_statement'][:130]}")
            print(f"    Papers: {c['paper_count']} | Gaps: {c['gap_count']} | "
                  f"Conf: {c['confidence_mean']:.2f} | Quality: {c['quality_score_mean']:.2f}")
            rd = c.get("risk_level_distribution", {})
            print(f"    Risk: L:{rd.get('low',0)} M:{rd.get('medium',0)} H:{rd.get('high',0)}")
            if c.get("testable_predictions"):
                print(f"    Prediction: {c['testable_predictions'][0][:120]}")
            if c.get("suggested_experiments"):
                exp = c["suggested_experiments"][0][:120]
                print(f"    Experiment: {exp}")
        print()

    out_dir = Path("05_Knowledge/cross_paper_hypotheses")
    print(f"  Output: {out_dir / 'hypothesis_clusters.json'}")
    print(f"  Summary: {out_dir / 'hypothesis_fusion_summary.json'}")
    print(f"  Quality: {out_dir / 'hypothesis_fusion_quality.json'}")
    print()


if __name__ == "__main__":
    sys.exit(main())
