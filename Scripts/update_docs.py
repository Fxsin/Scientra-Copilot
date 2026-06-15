#!/usr/bin/env python
"""P6.3 Update Docs. Usage: python Scripts/update_docs.py --all --verbose"""

from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> int:
    p = argparse.ArgumentParser(description="Update Documentation (P6.3)")
    p.add_argument("--all", action="store_true"); p.add_argument("--cli-reference", action="store_true"); p.add_argument("--api-reference", action="store_true")
    p.add_argument("--user-workflow", action="store_true"); p.add_argument("--check-storage-paths", action="store_true"); p.add_argument("--check-consistency", action="store_true"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    do_all = args.all

    from scientra.docs_tools import CLIReferenceBuilder, APIReferenceBuilder, StorageDocChecker, DocsConsistencyChecker, UserWorkflowDocBuilder
    results = []

    if do_all or args.cli_reference:
        path = CLIReferenceBuilder().build()
        results.append(f"CLI reference: {path}")
    if do_all or args.api_reference:
        path = APIReferenceBuilder().build()
        results.append(f"API reference: {path}")
    if do_all or args.user_workflow:
        path = UserWorkflowDocBuilder().build()
        results.append(f"User workflow: {path}")
    if do_all or args.check_storage_paths:
        r = StorageDocChecker().check()
        results.append(f"Storage check: clean={r['clean']}, db_v2_hits={len(r['db_v2_hits'])}")
        if r["db_v2_hits"]:
            for h in r["db_v2_hits"]: print(f"  ⚠ DB/DB_v2 in {h}")
    if do_all or args.check_consistency:
        r = DocsConsistencyChecker().check()
        results.append(f"Consistency: docs_ok={r['all_docs_exist']}, readme_ok={r['all_readme_checks']}")
        if r["missing_docs"]:
            for d in r["missing_docs"]: print(f"  ❌ Missing: {d}")

    for r in results: print(f"  {r}")
    print("Done.")
    return 0

if __name__ == "__main__": sys.exit(main())
