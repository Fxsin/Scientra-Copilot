#!/usr/bin/env python
"""P6.2 Run Demo Queries. Usage:
    python Scripts/run_demo_queries.py --use-cross-asset --use-dataset --verbose
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> int:
    p = argparse.ArgumentParser(description="Run Demo Queries (P6.2)")
    p.add_argument("--use-cross-asset", action="store_true", default=True); p.add_argument("--use-dataset", action="store_true", default=True); p.add_argument("--use-agent", action="store_true")
    p.add_argument("--json", action="store_true"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    from scientra.demo import DemoQueryRunner
    runner = DemoQueryRunner()
    r = runner.run(use_cross_asset=args.use_cross_asset, use_dataset=args.use_dataset, use_agent=args.use_agent)

    if args.json: print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for qr in r["results"]: print(f"  {qr['query']}: hits={qr.get('hits', qr.get('agent_answer', 'N/A')[:60])}")
        if r["warnings"]:
            for w in r["warnings"]: print(f"  ⚠ {w}")
    print(f"Output: {r['output_dir']}")
    return 0

if __name__ == "__main__": sys.exit(main())
