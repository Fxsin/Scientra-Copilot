#!/usr/bin/env python
"""Opportunity Expert Review CLI (Phase 3.5).

Usage:
    python Scripts/review_research_opportunities.py --top-k 10
    python Scripts/review_research_opportunities.py --top-k 5 --min-score 0.75
    python Scripts/review_research_opportunities.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.ai.opportunity_expert_review import review_research_opportunities


def main() -> int:
    p = argparse.ArgumentParser(description="Opportunity Expert Review")
    p.add_argument("--top-k", type=int, default=10,
                   help="Number of top opportunities to review (default: 10)")
    p.add_argument("--min-score", type=float, default=0.65,
                   help="Minimum opportunity score (default: 0.65)")
    p.add_argument("--no-evolution", action="store_true",
                   help="Exclude evolution context from review")
    p.add_argument("--json", action="store_true",
                   help="Output full JSON instead of report")
    args = p.parse_args()

    config: dict = {
        "top_k": args.top_k,
        "min_opportunity_score": args.min_score,
        "include_evolution_context": not args.no_evolution,
    }

    result = review_research_opportunities(top_k=args.top_k, config=config)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    _print_report(result)
    return 0


def _print_report(result: dict) -> None:
    summary = result.get("summary", {})
    reviews = result.get("reviews", [])

    _hdr = "=" * 70
    print(f"\n{_hdr}")
    print("  Opportunity Expert Review -- Phase 3.5")
    print(f"{_hdr}")
    print(f"  Status:                 {result.get('status', 'unknown')}")
    if result.get("message"):
        print(f"  Message:                {result['message']}")
    print(f"  Reviewed count:         {summary.get('reviewed_count', 0)}")
    print(f"  Accept:                 {summary.get('accept_count', 0)}")
    print(f"  Revise:                 {summary.get('revise_count', 0)}")
    print(f"  Reject:                 {summary.get('reject_count', 0)}")
    print(f"  Insufficient data:      {summary.get('insufficient_data_count', 0)}")
    print(f"  Errors:                 {summary.get('error_count', 0)}")
    print(f"  Avg review confidence:  {summary.get('average_review_confidence', 0):.3f}")
    print(f"  Total cost:             ${summary.get('total_cost_usd', 0):.6f}")
    print(f"  Cost per review:        ${summary.get('cost_per_review_usd', 0):.6f}")
    print()

    if not reviews:
        print("  No reviews generated.")
        print()
        return

    # Status distribution
    sd = summary.get("status_distribution", {})
    if sd:
        print(f"  Review Status Distribution:")
        for status, count in sorted(sd.items()):
            bar = "#" * min(count, 30)
            label = status.replace("_", " ").title()
            print(f"    {label:20s} {count:3d} {bar}")
        print()

    # Per-opportunity summary
    print(f"  Per-Opportunity Review Results:")
    sep = "-" * 85
    print(f"  {'#':<4} {'Score':<8} {'Status':<18} {'Conf':<7} Title")
    print(f"  {sep[:85]}")
    for i, r in enumerate(reviews, 1):
        title = r.get("title", "")[:55]
        status = r.get("review_status", "?").replace("_", " ")
        conf = r.get("review_confidence", 0.0)
        score = r.get("opportunity_score", 0.0)
        print(f"  {i:<4} {score:.3f}   {status:<18} {conf:.3f}  {title}")
    print()

    # Detailed reviews
    for i, r in enumerate(reviews[:5], 1):
        print(f"  {'-'*66}")
        print(f"  [#{i}] {r.get('title', '')[:80]}")
        print(f"  Status: {r.get('review_status', '?').replace('_', ' ').upper()}  |  "
              f"Confidence: {r.get('review_confidence', 0):.2f}  |  Score: {r.get('opportunity_score', 0):.3f}")
        print()
        if r.get("scientific_importance"):
            print(f"  Scientific Importance: {r['scientific_importance'][:200]}")
        if r.get("evidence_strength_assessment"):
            print(f"  Evidence Strength:     {r['evidence_strength_assessment'][:200]}")
        if r.get("technical_feasibility"):
            print(f"  Technical Feasibility: {r['technical_feasibility'][:200]}")
        if r.get("novelty_assessment"):
            print(f"  Novelty:               {r['novelty_assessment'][:200]}")
        if r.get("major_risks"):
            print(f"  Major Risks ({len(r['major_risks'])}):")
            for risk in r["major_risks"][:3]:
                print(f"    - {risk[:120]}")
        if r.get("key_missing_evidence"):
            print(f"  Missing Evidence ({len(r['key_missing_evidence'])}):")
            for me in r["key_missing_evidence"][:3]:
                print(f"    - {me[:120]}")
        if r.get("recommended_next_steps"):
            print(f"  Recommended Next Steps:")
            for ns in r["recommended_next_steps"][:3]:
                print(f"    -> {ns[:120]}")
        if r.get("expected_impact"):
            print(f"  Expected Impact:       {r['expected_impact'][:200]}")
        if r.get("review_warnings"):
            for w in r["review_warnings"]:
                print(f"  WARNING: {w[:120]}")
        usage = r.get("usage", {})
        if usage.get("cost_estimate", 0) > 0:
            print(f"  Cost: ${usage['cost_estimate']:.6f}  |  "
                  f"Tokens: {usage.get('total_tokens', 0)}")
        print()

    out = Path("05_Knowledge/research_opportunity_reviews")
    print(f"  Output:  {out / 'opportunity_reviews.json'}")
    print(f"  Summary: {out / 'opportunity_review_summary.json'}")
    print()


if __name__ == "__main__":
    sys.exit(main())
