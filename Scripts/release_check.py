#!/usr/bin/env python
"""P6.4 Release Check. Usage:
    python Scripts/release_check.py --all --verbose
    python Scripts/release_check.py --secrets --large-files --fail-on-p0
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> int:
    p = argparse.ArgumentParser(description="Release Check (P6.4)")
    p.add_argument("--all", action="store_true"); p.add_argument("--secrets", action="store_true"); p.add_argument("--large-files", action="store_true"); p.add_argument("--gitignore", action="store_true")
    p.add_argument("--storage-safety", action="store_true"); p.add_argument("--path-hardcode", action="store_true"); p.add_argument("--tests", action="store_true")
    p.add_argument("--max-file-mb", type=int, default=20); p.add_argument("--json", action="store_true"); p.add_argument("--verbose", action="store_true"); p.add_argument("--fail-on-p0", action="store_true")
    args = p.parse_args()
    do_all = args.all

    from scientra.release import ReleaseCheckRunner
    runner = ReleaseCheckRunner(max_file_mb=args.max_file_mb)
    report = runner.run(
        check_secrets=do_all or args.secrets, check_large=do_all or args.large_files,
        check_gitignore=do_all or args.gitignore, check_storage=do_all or args.storage_safety,
        check_paths=do_all or args.path_hardcode, check_tests=do_all or args.tests,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"\nRelease Check — P6.4")
        print(f"  P0: {len(report.get('P0', []))}  P1: {len(report.get('P1', []))}  P2: {len(report.get('P2', []))}  P3: {len(report.get('P3', []))}")
        print(f"  Passed: {'✅' if report['passed'] else '❌'}")
        if args.verbose:
            for level in ["P0", "P1", "P2"]:
                for item in report.get(level, [])[:5]:
                    print(f"  [{level}] {item['title']}: {item.get('detail', '')[:80]}")
        print(f"  Report: 10_System/release/release_check_report.md\n")

    if args.fail_on_p0 and len(report.get("P0", [])) > 0:
        return 1
    return 0

if __name__ == "__main__": sys.exit(main())
