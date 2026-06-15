#!/usr/bin/env python
"""P6.2 Create Demo Project. Usage:
    python Scripts/create_demo_project.py --create-only
    python Scripts/create_demo_project.py --run-pipeline --run-validation --verbose
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> int:
    p = argparse.ArgumentParser(description="Create Demo Project (P6.2)")
    p.add_argument("--create-only", action="store_true"); p.add_argument("--run-pipeline", action="store_true"); p.add_argument("--run-validation", action="store_true")
    p.add_argument("--force", action="store_true"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    from scientra.demo import DemoProjectBuilder
    builder = DemoProjectBuilder()
    r = builder.create(force=args.force)
    if args.verbose or not r.get("success"): print(r.get("message", r.get("error", "")))
    if r.get("files"): print(f"Files: {', '.join(r['files'])}")

    if args.run_validation:
        try:
            from scientra.validation.e2e import E2EValidationRunner
            vr = E2EValidationRunner().run(skip_agent=False, skip_query=False)
            if args.verbose: print(f"Validation: {vr['papers']} papers, P0={vr['p0_count']}")
        except Exception as e: print(f"Validation warning: {e}")

    print("Done. ⚠️ All demo data is synthetic.")
    return 0

if __name__ == "__main__": sys.exit(main())
