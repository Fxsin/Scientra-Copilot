#!/usr/bin/env python
"""P6.0 E2E Validation. Usage:
    python Scripts/run_e2e_validation.py --all --verbose
    python Scripts/run_e2e_validation.py --check-storage --check-db-paths --json
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> int:
    p = argparse.ArgumentParser(description="E2E Validation (P6.0)")
    p.add_argument("--all", action="store_true"); p.add_argument("--paper-id", default="")
    p.add_argument("--skip-agent", action="store_true"); p.add_argument("--skip-query", action="store_true")
    p.add_argument("--check-storage", action="store_true"); p.add_argument("--check-db-paths", action="store_true")
    p.add_argument("--json", action="store_true"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    from scientra.validation.e2e import E2EValidationRunner
    runner = E2EValidationRunner()
    result = runner.run(skip_agent=args.skip_agent, skip_query=args.skip_query,
                        check_storage=args.check_storage or args.all,
                        check_db=args.check_db_paths or args.all)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\nE2E Validation — P6.0")
        print(f"Papers: {result['papers']} (complete: {result['papers_complete']})")
        print(f"Storage v3: {'✅' if result['storage_v3'] else '❌'}  DB_v2 clean: {'✅' if result['db_v2_clean'] else '❌'}")
        print(f"Modules: {'✅' if result['modules_ok'] else '❌'}")
        print(f"Query: {result['query_passed']} passed  Agent: {result['agent_passed']} passed")
        print(f"P0: {result['p0_count']}  P1: {result['p1_count']}")
        print(f"Output: {result['output_dir']}\n")
    return 0

if __name__ == "__main__": sys.exit(main())
