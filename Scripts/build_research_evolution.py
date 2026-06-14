#!/usr/bin/env python
"""Research Evolution Builder CLI (Phase 3.4).

Usage:
    python Scripts/build_research_evolution.py
    python Scripts/build_research_evolution.py --phase-mode auto
    python Scripts/build_research_evolution.py --window-years 5
    python Scripts/build_research_evolution.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.ai.research_evolution import build_research_evolution


def main() -> int:
    p = argparse.ArgumentParser(description="Research Evolution Builder")
    p.add_argument("--phase-mode", default="auto", choices=["auto"])
    p.add_argument("--window-years", type=int, default=None,
                   help="Override window size (default: auto based on year span)")
    p.add_argument("--min-papers-per-phase", type=int, default=3)
    p.add_argument("--json", action="store_true",
                   help="Output full JSON instead of report")
    args = p.parse_args()

    config: dict = {
        "phase_mode": args.phase_mode,
        "min_papers_per_phase": args.min_papers_per_phase,
    }
    if args.window_years is not None:
        config["window_years_long_span"] = args.window_years
        config["window_years_short_span"] = args.window_years

    result = build_research_evolution(config=config)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    _print_report(result)
    return 0


def _print_report(result: dict) -> None:
    summary = result.get("summary", {})
    phases = result.get("phases", [])
    gap_evolution = result.get("gap_evolution", [])
    hypothesis_evolution = result.get("hypothesis_evolution", [])
    opportunity_evolution = result.get("opportunity_evolution", [])

    print(f"\n{'='*70}")
    print("  Research Evolution Analysis — Phase 3.4")
    print(f"{'='*70}")
    print(f"  Status:               {result.get('status', 'unknown')}")
    print(f"  Total papers:         {summary.get('total_papers', 0)}")
    print(f"  Year span:            {summary.get('year_min', 0)} – {summary.get('year_max', 0)} "
          f"({summary.get('year_span', 0)} years)")
    print(f"  Phase count:          {summary.get('phase_count', 0)}")
    print(f"  Phase window:         {summary.get('phase_window_years', 'auto')} years")
    print(f"  Gap clusters:         {summary.get('total_gap_clusters', 0)}")
    print(f"  Hypothesis clusters:  {summary.get('total_hypothesis_clusters', 0)}")
    print(f"  Opportunities:        {summary.get('total_opportunities', 0)}")
    print()

    # ── Phases overview ──
    if phases:
        print(f"  {'─'*66}")
        print(f"  Phases Overview:")
        print(f"  {'Phase':<12} {'Year Range':<14} {'Papers':<8} {'Dominant Topics'}")
        print(f"  {'─'*12} {'─'*14} {'─'*8} {'─'*40}")
        for ph in phases:
            topics = ", ".join(ph.get("dominant_topics", [])[:4])
            print(f"  {ph['phase_id']:<12} {ph['year_range']:<14} {ph['paper_count']:<8} {topics[:55]}")
        print()

    # ── Gap trend distribution ──
    gap_trends = summary.get("gap_trend_distribution", {})
    if gap_trends:
        print(f"  Gap Trend Distribution:")
        for trend, count in sorted(gap_trends.items()):
            bar = "█" * min(count, 40)
            print(f"    {trend:20s} {count:4d} {bar}")
        print()

    # ── Hypothesis trend distribution ──
    hyp_trends = summary.get("hypothesis_trend_distribution", {})
    if hyp_trends:
        print(f"  Hypothesis Trend Distribution:")
        for trend, count in sorted(hyp_trends.items()):
            bar = "█" * min(count, 40)
            print(f"    {trend:20s} {count:4d} {bar}")
        print()

    # ── Opportunity trend distribution ──
    opp_trends = summary.get("opportunity_trend_distribution", {})
    if opp_trends:
        print(f"  Opportunity Trend Distribution:")
        for trend, count in sorted(opp_trends.items()):
            bar = "█" * min(count, 40)
            print(f"    {trend:20s} {count:4d} {bar}")
        print()

    # ── Top 10 Persistent Gaps ──
    top_pg = summary.get("top_persistent_gaps", [])
    if top_pg:
        print(f"  Top {len(top_pg)} Persistent Gaps:")
        print(f"  {'#':<4} {'Papers':<8} {'Persistence':<12} Title")
        print(f"  {'─'*4} {'─'*8} {'─'*12} {'─'*45}")
        for i, g in enumerate(top_pg, 1):
            title = g.get("title", "")[:75]
            print(f"  {i:<4} {g.get('paper_count', 0):<8} {g.get('persistence_score', 0):.3f}        {title}")
        print()

    # ── Top 10 Emerging Gaps ──
    top_eg = summary.get("top_emerging_gaps", [])
    if top_eg:
        print(f"  Top {len(top_eg)} Emerging Gaps:")
        print(f"  {'#':<4} {'Papers':<8} Title")
        print(f"  {'─'*4} {'─'*8} {'─'*50}")
        for i, g in enumerate(top_eg, 1):
            title = g.get("title", "")[:75]
            print(f"  {i:<4} {g.get('paper_count', 0):<8} {title}")
        print()

    # ── Top 10 Emerging Hypotheses ──
    top_eh = summary.get("top_emerging_hypotheses", [])
    if top_eh:
        print(f"  Top {len(top_eh)} Emerging Hypotheses:")
        print(f"  {'#':<4} Title")
        print(f"  {'─'*4} {'─'*55}")
        for i, h in enumerate(top_eh, 1):
            title = h.get("title", "")[:80]
            print(f"  {i:<4} {title}")
        print()

    # ── Top 10 Rising Opportunities ──
    top_ro = summary.get("top_rising_opportunities", [])
    if top_ro:
        print(f"  Top {len(top_ro)} Rising Opportunities:")
        print(f"  {'#':<4} {'Score':<8} Title")
        print(f"  {'─'*4} {'─'*8} {'─'*55}")
        for i, o in enumerate(top_ro, 1):
            title = o.get("title", "")[:80]
            print(f"  {i:<4} {o.get('score', 0):.3f}   {title}")
        print()

    out = Path("05_Knowledge/research_evolution")
    print(f"  Output:  {out / 'research_evolution.json'}")
    print(f"  Summary: {out / 'research_evolution_summary.json'}")
    print()


if __name__ == "__main__":
    sys.exit(main())
