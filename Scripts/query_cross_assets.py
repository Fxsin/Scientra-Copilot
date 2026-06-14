#!/usr/bin/env python
"""Cross-Asset Query (P5.2) — Storage Layout v3.

Usage:
    python Scripts/query_cross_assets.py --query "MAP2K4 expression" --top-k 20
    python Scripts/query_cross_assets.py --query "LC50 bioassay" --asset-types evidence,table,figure --json
    python Scripts/query_cross_assets.py --query "Vip3Aa receptor" --use-graph --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="Cross-Asset Query (P5.2)")
    p.add_argument("--query", required=True)
    p.add_argument("--paper-id", default="")
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--asset-types", default="evidence,figure,table,supplementary,graph,gap,hypothesis")
    p.add_argument("--use-vector", action="store_true", default=True)
    p.add_argument("--no-vector", action="store_true")
    p.add_argument("--use-graph", action="store_true", default=True)
    p.add_argument("--no-graph", action="store_true")
    p.add_argument("--evidence-only", action="store_true", default=True)
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    from scientra.cross_asset_query import CrossAssetQueryEngine, make_query

    engine = CrossAssetQueryEngine()
    q = make_query(
        query=args.query, paper_id=args.paper_id,
        asset_types=[t.strip() for t in args.asset_types.split(",")],
        top_k=args.top_k,
        use_vector=not args.no_vector,
        use_graph=not args.no_graph,
    )
    result = engine.query(q)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\nQuery: {args.query}")
        print(f"Intent: {result['resolved_intent']}")
        print(f"Answer: {result['answer']}")
        print(f"\nHits: {result['stats']['total_hits']} (kw={result['stats']['keyword_hits']} vec={result['stats']['vector_hits']} graph={result['stats']['graph_hits']})")
        if result.get("grouped_hits"):
            print("\nGrouped Results:")
            for atype, hits in result["grouped_hits"].items():
                print(f"  [{atype}] {len(hits)} hit(s)")
                for h in hits[:3]:
                    print(f"    - {h.get('title', '')[:80]} (score: {h.get('score', 0):.3f})")
        if result.get("warnings"):
            print("\nWarnings:")
            for w in result["warnings"][:5]:
                print(f"  ⚠ {w}")
        if result.get("support_chains"):
            print(f"\nSupport Chains: {len(result['support_chains'])}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
