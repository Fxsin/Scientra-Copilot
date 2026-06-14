#!/usr/bin/env python
"""Research Opportunity Ranking CLI (Phase 3.3).

Usage:
    python Scripts/rank_research_opportunities.py
    python Scripts/rank_research_opportunities.py --top-k 20
    python Scripts/rank_research_opportunities.py --min-paper-count 3
    python Scripts/rank_research_opportunities.py --json
"""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.ai.opportunity_ranking import rank_research_opportunities


def main() -> int:
    p = argparse.ArgumentParser(description="Research Opportunity Ranking")
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--min-paper-count", type=int, default=1)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = rank_research_opportunities(
        top_k=args.top_k, min_paper_count=args.min_paper_count,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    _print_report(result)
    return 0


def _print_report(result: dict) -> None:
    summary = result.get("summary", {})
    opps = result.get("opportunities", [])

    print(f"\n{'='*70}")
    print("  Research Opportunity Ranking")
    print(f"{'='*70}")
    print(f"  Total opportunities:     {result.get('total_opportunities', 0)}")
    print(f"  Top K shown:             {summary.get('top_k', 0)}")
    print(f"  Avg score:               {summary.get('average_opportunity_score', 0):.3f}")
    print(f"  Score range:             {summary.get('score_min', 0):.3f} – {summary.get('score_max', 0):.3f}")
    print()

    # Category distribution
    cat = summary.get("category_distribution", {})
    if cat:
        print("  Category Distribution:")
        for cname, count in cat.items():
            bar = "█" * min(count, 30)
            print(f"    {cname:32s} {count:2d} {bar}")
        print()

    # Key counts
    for label, key in [
        ("High confidence next step", "high_confidence_next_step"),
        ("High impact open question", "high_impact_open_question"),
        ("Underexplored mechanism", "underexplored_mechanism"),
        ("Translation gap", "translation_gap"),
        ("Contradiction to resolve", "contradiction_to_resolve"),
    ]:
        print(f"  {label}: {summary.get(key, 0)}")
    print()

    # Top opportunities
    if opps:
        print(f"  Top {min(len(opps), 20)} Opportunities:")
        print(f"  {'#':<4} {'Score':<7} {'Papers':<7} {'Risk':<8} {'Category':<30} Title")
        print(f"  {'-'*4} {'-'*7} {'-'*7} {'-'*8} {'-'*30} {'-'*45}")
        for i, o in enumerate(opps[:20], 1):
            title = o.get("title", "")[:80]
            cat_name = o.get("category", "?").replace("_", " ")
            print(f"  {i:<4} {o['opportunity_score']:.3f}   {o['supporting_paper_count']:<7} "
                  f"{o.get('risk_level', '?'):<8} {cat_name:<30} {title}")
        print()

        # Details for top 5
        print(f"  Top 5 Details:")
        for o in opps[:5]:
            print(f"\n  [#{o['opportunity_id']}] Score: {o['opportunity_score']:.3f} | "
                  f"Category: {o['category'].replace('_', ' ')}")
            print(f"  Papers: {o['supporting_paper_count']} | Gaps: {o['supporting_gap_count']} | "
                  f"Hyps: {o['supporting_hypothesis_count']}")
            print(f"  Evidence: {o.get('evidence_support_level', '?')} | "
                  f"Testability: {o.get('testability', '?')} | Risk: {o.get('risk_level', '?')}")
            print(f"  Scores: E={o['evidence_score']:.2f} F={o['feasibility_score']:.2f} "
                  f"N={o['novelty_score']:.2f} I={o['impact_score']:.2f} "
                  f"C={o['confidence_score']:.2f} P={o['risk_penalty']:.2f}")
            if o.get("representative_hypothesis"):
                print(f"  Hypothesis: {o['representative_hypothesis'][:150]}")
            if o.get("suggested_next_steps"):
                for ns in o["suggested_next_steps"][:2]:
                    print(f"  → {ns[:120]}")
        print()

    out = Path("05_Knowledge/research_opportunities")
    print(f"  Output: {out / 'opportunity_ranking.json'}")
    print(f"  Summary: {out / 'opportunity_summary.json'}")
    print()


if __name__ == "__main__":
    sys.exit(main())
