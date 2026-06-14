#!/usr/bin/env python
"""Migrate paper workspaces to human-friendly display names (Phase 4.0.1).

Usage:
    python Scripts/migrate_paper_workspaces.py --dry-run
    python Scripts/migrate_paper_workspaces.py --apply
    python Scripts/migrate_paper_workspaces.py --paper-id paper_xxx --dry-run
    python Scripts/migrate_paper_workspaces.py --paper-id paper_xxx --apply
    python Scripts/migrate_paper_workspaces.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="Migrate paper workspaces to human-friendly names")
    p.add_argument("--dry-run", action="store_true", default=True,
                   help="Plan migration without executing (default)")
    p.add_argument("--apply", action="store_true",
                   help="Actually execute the migration")
    p.add_argument("--paper-id", help="Migrate a single paper only")
    p.add_argument("--json", action="store_true",
                   help="Output JSON report")
    args = p.parse_args()

    dry_run = not args.apply

    if not args.apply and not args.dry_run:
        dry_run = True  # Safety: default to dry-run

    from scientra.papers.paper_registry import build_paper_registry
    from scientra.papers.paper_workspace import migrate_all_workspaces, migrate_workspace_to_display_name

    # Build/refresh registry first
    print("Building paper registry...")
    build_paper_registry()

    if args.paper_id:
        print(f"Migrating single paper: {args.paper_id}")
        result = migrate_workspace_to_display_name(args.paper_id, dry_run=dry_run)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        _print_single(result, dry_run)
        return 0

    print(f"Migrating all papers ({'DRY RUN' if dry_run else 'APPLY'})...")
    report = migrate_all_workspaces(dry_run=dry_run)

    if args.json:
        # Strip details for cleaner output
        summary = {k: v for k, v in report.items() if k != "details"}
        summary["details_count"] = len(report.get("details", []))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    _print_report(report, dry_run)
    return 0


def _print_single(result: dict, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "APPLY"
    print(f"\n  [{mode}] Paper: {result['paper_id']}")
    print(f"  Status:   {result['status']}")
    if result.get("old_dir"):
        print(f"  Old:      {result['old_dir']}")
    if result.get("new_dir"):
        print(f"  New:      {result['new_dir']}")
    if result.get("error"):
        print(f"  Error:    {result['error']}")
    print()


def _print_report(report: dict, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "APPLY"
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  Paper Workspace Migration Report [{mode}]")
    print(f"{sep}")
    print(f"  Total papers:   {report.get('total_papers', 0)}")
    print(f"  Planned:        {report.get('planned', 0)}")
    print(f"  Migrated:       {report.get('migrated', 0)}")
    print(f"  Skipped:        {report.get('skipped', 0)}")
    print(f"  Conflicts:      {report.get('conflicts', 0)}")
    print(f"  Errors:         {report.get('errors', 0)}")
    print(f"  Timestamp:      {report.get('timestamp', '')}")
    print()

    details = report.get("details", [])
    if details:
        planned = [d for d in details if d["status"] == "planned"]
        skipped = [d for d in details if d["status"] == "skipped"]
        errors = [d for d in details if d["status"] == "error"]
        migrated = [d for d in details if d["status"] == "migrated"]

        if planned:
            print(f"  Planned ({len(planned)}):")
            for d in planned[:5]:
                print(f"    {d['paper_id']} -> {Path(d.get('new_dir','')).name}")
            if len(planned) > 5:
                print(f"    ... and {len(planned) - 5} more")

        if skipped:
            print(f"\n  Skipped ({len(skipped)}):")
            for d in skipped[:5]:
                print(f"    {d['paper_id']}: {d.get('error','')}")
            if len(skipped) > 5:
                print(f"    ... and {len(skipped) - 5} more")

        if errors:
            print(f"\n  Errors ({len(errors)}):")
            for d in errors[:5]:
                print(f"    {d['paper_id']}: {d.get('error','')}")

    if dry_run and report.get("planned", 0) > 0:
        print(f"\n  To apply: python Scripts/migrate_paper_workspaces.py --apply")

    print(f"\n  Report: 10_System/reports/paper_workspace_migration_report.json")
    print()


if __name__ == "__main__":
    sys.exit(main())
