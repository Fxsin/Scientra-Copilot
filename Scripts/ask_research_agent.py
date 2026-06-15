#!/usr/bin/env python
"""P5.4 Research Agent CLI. Usage:
    python Scripts/ask_research_agent.py --query "MAP2K4 expression" --mode evidence_only
    python Scripts/ask_research_agent.py --query "research plan for Vip3Aa receptor" --mode auto --json
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="Graph-Augmented Research Agent (P5.4)")
    p.add_argument("--query", required=True); p.add_argument("--paper-id", default="")
    p.add_argument("--mode", default="evidence_only", choices=["evidence_only", "llm_synthesis", "auto"])
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--no-graph", action="store_true"); p.add_argument("--no-cross-asset", action="store_true"); p.add_argument("--no-dataset", action="store_true")
    p.add_argument("--return-trace", action="store_true"); p.add_argument("--json", action="store_true"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    from scientra.agents.research_agent import ResearchAgentRunner, make_request

    runner = ResearchAgentRunner()
    req = make_request(query=args.query, paper_id=args.paper_id, mode=args.mode,
                       use_graph=not args.no_graph, use_cross_asset=not args.no_cross_asset,
                       use_dataset=not args.no_dataset, top_k=args.top_k, return_trace=args.return_trace)
    resp = runner.ask(req)

    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    else:
        print(f"\nQuery: {args.query}\nIntent: {resp['resolved_intent']}\nMode: {resp['mode']}")
        print(f"Answer: {resp['answer']}")
        print(f"Refs: {len(resp['evidence_references'])}  Chains: {len(resp['evidence_chains'])}  Confidence: {resp['confidence']:.2f}")
        if resp.get("research_plan"):
            rp = resp["research_plan"]
            print(f"\n--- Research Plan ---\nQuestion: {rp['research_question']}")
            print(f"Gaps: {', '.join(rp['key_gaps'][:3])}")
            print(f"Hypotheses: {', '.join(rp['testable_hypotheses'][:3])}")
            print(f"Experiments: {', '.join(rp['suggested_experiments'][:3])}")
        if resp.get("warnings"):
            print(f"\nWarnings:")
            for w in resp["warnings"][:5]: print(f"  ⚠ {w}")
        if resp.get("used_tools"):
            print(f"\nTools: {', '.join(t['name'] for t in resp['used_tools'])}")
        if resp.get("trace_id"):
            print(f"Trace: {resp['trace_id']}")
        print()
    return 0


if __name__ == "__main__": sys.exit(main())
