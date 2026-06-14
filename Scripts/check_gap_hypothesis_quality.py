#!/usr/bin/env python
"""Check Gap-Hypothesis Quality — CLI tool (Phase 2.3.1).

Usage:
    python Scripts/check_gap_hypothesis_quality.py --paper-id {paper_id}
    python Scripts/check_gap_hypothesis_quality.py --all --limit 10
    python Scripts/check_gap_hypothesis_quality.py --all

Output per paper: 03_Assets/ai/quality/gap_hypothesis/{paper_id}.json
Summary:         03_Assets/ai/quality/gap_hypothesis/summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.ai.gap_hypothesis_quality import (
    evaluate_gap_hypothesis_quality,
    evaluate_all_papers,
    OUTPUT_DIR,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Gap-Hypothesis Quality (Phase 2.3.1)"
    )
    parser.add_argument(
        "--paper-id", type=str, default=None,
        help="Evaluate a single paper by ID."
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Evaluate all available papers."
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Limit number of papers (with --all). 0 = all."
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output result as JSON to stdout."
    )

    args = parser.parse_args()

    if args.paper_id:
        result = evaluate_gap_hypothesis_quality(paper_id=args.paper_id)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_single(result)
        return 0

    if args.all:
        summary = evaluate_all_papers(limit=args.limit)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            _print_summary(summary)
        return 0

    parser.print_help()
    return 1


def _print_single(result: dict) -> None:
    paper_id = result.get("paper_id", "?")
    print(f"\n{'='*60}")
    print(f"Quality Report: {paper_id[:70]}")
    print(f"{'='*60}")
    print(f"  Gaps: {result.get('gap_count', 0)}")
    print(f"  Hypotheses: {result.get('hypothesis_count', 0)}")
    print(f"  Overall Score: {result.get('overall_quality_score', 0):.3f}")
    print(f"  Recommendation: {result.get('recommendation', '?').upper()}")

    metrics = result.get("metrics", {})
    if metrics:
        print(f"  Invalid Links: {metrics.get('invalid_linked_gap_count', 0)}")
        print(f"  High Overclaim: {metrics.get('high_overclaim_risk_count', 0)}")
        print(f"  Safety Issues: {metrics.get('safety_ethics_warnings', 0)}")

    # Gap scores
    for s in result.get("gap_scores", []):
        gid = s.get("gap_id", "")[-20:]
        print(f"\n  Gap {gid}:")
        print(f"    Evidence: {s['evidence_grounding_score']:.3f}  "
              f"Specificity: {s['specificity_score']:.3f}  "
              f"Novelty: {s['novelty_score']:.3f}")
        if s.get("overclaim_risk", "low") != "low":
            print(f"    ⚠ Overclaim Risk: {s['overclaim_risk'].upper()}")

    # Hypothesis scores
    for s in result.get("hypothesis_scores", []):
        hid = s.get("hypothesis_id", "")[-20:]
        link = "✓" if s.get("linked_gap_valid") else "✗"
        print(f"\n  Hyp {hid}:")
        print(f"    Link: {link}  Testability: {s['testability_score']:.3f}  "
              f"Rationale: {s['rationale_grounding_score']:.3f}  "
              f"Feasibility: {s['experiment_feasibility_score']:.3f}")
        if s.get("over_specificity_risk", "low") != "low":
            print(f"    ⚠ Over-Specificity: {s['over_specificity_risk'].upper()}")
        for sw in s.get("safety_or_ethics_warning", []):
            print(f"    🛑 Safety: {sw[:100]}")

    # Top warnings
    tw = result.get("top_warnings", [])
    if tw:
        print(f"\n  Top Warnings:")
        for w in tw[:5]:
            print(f"    ⚠ {w[:120]}")

    print(f"\n  Output: {OUTPUT_DIR / f'{paper_id}.json'}")


def _print_summary(summary: dict) -> None:
    print(f"\n{'='*60}")
    print("Gap-Hypothesis Quality Summary")
    print(f"{'='*60}")
    print(f"  Papers: {summary.get('total_papers', 0)}")
    print(f"  Accept: {summary.get('accept_count', 0)}")
    print(f"  Manual Review: {summary.get('manual_review_count', 0)}")
    print(f"  Reject: {summary.get('reject_count', 0)}")
    print(f"  Insufficient Data: {summary.get('insufficient_data_count', 0)}")
    print(f"  Average Score: {summary.get('average_quality_score', 0):.3f}")
    print(f"  Invalid Links: {summary.get('invalid_linked_gap_count', 0)}")
    print(f"  High Overclaim: {summary.get('high_overclaim_risk_count', 0)}")

    tw = summary.get("top_warnings", [])
    if tw:
        print(f"\n  Top Warnings:")
        for w in tw[:10]:
            print(f"    ⚠ {w[:120]}")

    print(f"\n  Output: {OUTPUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    sys.exit(main())
