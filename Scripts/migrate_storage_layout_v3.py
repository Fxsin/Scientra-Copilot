"""Storage Layout v3 Migration Script.

Commands:
  python Scripts/migrate_storage_layout_v3.py --plan
  python Scripts/migrate_storage_layout_v3.py --dry-run
  python Scripts/migrate_storage_layout_v3.py --execute --mode copy
  python Scripts/migrate_storage_layout_v3.py --execute --mode move
  python Scripts/migrate_storage_layout_v3.py --verify
"""
import argparse, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))


def main():
    parser = argparse.ArgumentParser(description="Storage Layout v3 Migration")
    parser.add_argument("--plan", action="store_true", help="Generate migration plan")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration")
    parser.add_argument("--execute", action="store_true", help="Execute migration")
    parser.add_argument("--mode", default="copy", choices=["copy", "move"],
                       help="Migration mode (default: copy)")
    parser.add_argument("--verify", action="store_true", help="Verify migration")
    args = parser.parse_args()

    from scientra.io.storage_migrator import StorageMigrator
    from scientra.io.storage_layout import StorageLayout

    # Ensure directories
    layout = StorageLayout()
    layout.load()
    layout.ensure_all_directories()

    migrator = StorageMigrator()

    if args.plan:
        print("=== Migration Plan ===")
        plan = migrator.plan()
        print(f"Total mappings: {plan['total_mappings']}")
        print(f"Total files: {plan['total_files']}")
        print(f"Total size: {plan['total_size_bytes']:,} bytes")
        for item in plan["items"]:
            status = item["status"]
            print(f"  {item['source']:50s} -> {item['target']:50s} "
                  f"[{item['files']} files, {item['size']:,} bytes, {status}]")
        print(f"\nPlan saved to 10_System/migrations/")

    elif args.dry_run:
        print("=== Dry Run ===")
        plan = migrator.dry_run()
        dry = plan.get("dry_run", {})
        print(f"Would copy: {dry.get('would_copy', 0)} files")
        print(f"Would skip (conflicts): {dry.get('would_skip', 0)} files")
        if dry.get("would_skip", 0) == 0:
            print("No conflicts detected. Safe to --execute.")

    elif args.execute:
        mode = args.mode
        print(f"=== Execute Migration (mode={mode}) ===")
        result = migrator.execute(mode=mode)
        print(f"Copied: {result['copied']}")
        print(f"Skipped (identical): {result['skipped']}")
        print(f"Errors: {result['errors']}")
        if result['errors'] > 0:
            print("Some files failed. See report for details.")
        print(f"Manifest saved to 10_System/migrations/")

    elif args.verify:
        print("=== Verify Migration ===")
        result = migrator.verify()
        if "error" in result:
            print(f"Error: {result['error']}")
            return 1
        print(f"Verified: {result['verified']}")
        print(f"SHA256 mismatch: {result['mismatch']}")
        print(f"Missing: {result['missing']}")
        if result['mismatch'] == 0 and result['missing'] == 0:
            print("All verified files OK.")

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
