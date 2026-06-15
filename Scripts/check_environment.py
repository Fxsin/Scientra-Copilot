#!/usr/bin/env python3
"""P6.6.1 Environment Check. Usage:
    python Scripts/check_environment.py
    python Scripts/check_environment.py --json
    python Scripts/check_environment.py --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="P6.6.1 Environment Check")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.add_argument("--verbose", action="store_true", help="Show all details")
    p.add_argument("--root", type=Path, default=None, help="Project root path")
    args = p.parse_args()

    from scientra.environment.diagnostics import run_diagnostics
    from scientra.environment.repair import generate_repair_suggestions

    diag = run_diagnostics(args.root)
    repair = generate_repair_suggestions(args.root)

    if args.json:
        output = {**diag, "repair_suggestions": repair}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if diag["failed"] > 0:
            return 1
        return 0

    # Text output
    score = diag["health_score"]
    status = diag["status"]
    icon = "🟢" if status == "healthy" else ("🟡" if status == "degraded" else "🔴")

    print(f"\n{'='*55}")
    print(f"  Scientra Copilot — Environment Check")
    print(f"  {icon} Health Score: {score}/100 ({status.upper()})")
    print(f"{'='*55}")
    print(f"\n  ✅ {diag['passed']} passed  ⚠️  {diag['warnings']} warnings  ❌ {diag['failed']} failed  ℹ️  {diag['info']} info\n")

    for c in diag["checks"]:
        icon_map = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "INFO": "ℹ️ "}
        icon_c = icon_map.get(c["status"], "❓")
        print(f"  {icon_c} {c['name']}: {c.get('detail', '')[:100]}")
        if args.verbose and c.get("fix"):
            print(f"     Fix: {c['fix']}")

    if repair:
        print(f"\n  {'─'*50}")
        print(f"  Repair Suggestions ({len(repair)} issues):")
        for s in repair:
            sev = "🔴" if s["severity"] == "FAIL" else "🟡"
            print(f"  {sev} {s['problem']}: {s['fix'][:120]}")

    print(f"\n  Full report: python Scripts/health_report.py\n")

    return 1 if diag["failed"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
