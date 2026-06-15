#!/usr/bin/env python3
"""P6.6.1 Health Report Generator. Usage:
    python Scripts/health_report.py
    python Scripts/health_report.py --json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="P6.6.1 Health Report Generator")
    p.add_argument("--json", action="store_true", help="Output report paths as JSON")
    p.add_argument("--root", type=Path, default=None, help="Project root path")
    args = p.parse_args()

    from scientra.environment.report_builder import build_all_health_reports
    from scientra.environment.diagnostics import run_diagnostics

    reports = build_all_health_reports(args.root)
    diag = run_diagnostics(args.root)

    if args.json:
        import json
        print(json.dumps({
            "health_score": diag["health_score"],
            "status": diag["status"],
            "reports": reports,
        }, ensure_ascii=False, indent=2))
        return 0

    score = diag["health_score"]
    status = diag["status"]
    icon = "🟢" if status == "healthy" else ("🟡" if status == "degraded" else "🔴")

    print(f"\n{'='*55}")
    print(f"  Scientra Copilot — Health Report")
    print(f"  {icon} Score: {score}/100 — {status.upper()}")
    print(f"{'='*55}")
    print(f"\n  Reports generated:")
    for name, path in reports.items():
        print(f"    {path}")
    print(f"\n  ✅ {diag['passed']} passed  ⚠️  {diag['warnings']} warnings  ❌ {diag['failed']} failed")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
