#!/usr/bin/env python3
"""P6.6.1 Repair Suggestions. Usage:
    python Scripts/repair_environment.py
    python Scripts/repair_environment.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="P6.6.1 Repair Suggestions")
    p.add_argument("--json", action="store_true")
    p.add_argument("--root", type=Path, default=None)
    args = p.parse_args()

    from scientra.environment.repair import generate_repair_report

    report = generate_repair_report(args.root)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"\n{'='*55}")
    print(f"  Scientra Copilot — Repair Suggestions")
    print(f"  {report['critical']} critical, {report['warnings']} warnings")
    print(f"{'='*55}\n")

    if not report["suggestions"]:
        print("  ✅ No issues found! Your environment is ready.\n")
        return 0

    for s in report["suggestions"]:
        sev = "🔴 CRITICAL" if s["severity"] == "FAIL" else "🟡 WARNING"
        print(f"  {sev}: {s['problem']}")
        print(f"    Cause: {s.get('cause', 'Unknown')}")
        print(f"    Fix:   {s.get('fix', 'No fix available')}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
