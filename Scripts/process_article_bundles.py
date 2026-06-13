"""Article Bundle Import CLI."""
import argparse, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))


def main():
    parser = argparse.ArgumentParser(description="Article Bundle Import (Storage v3)")
    parser.add_argument("--scan", action="store_true", help="Scan inbox for bundles")
    parser.add_argument("--process", action="store_true", help="Process bundles")
    parser.add_argument("--archive-mode", default="copy",
                       choices=["copy", "move", "none"], help="Archive mode (default: copy)")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no file ops")
    parser.add_argument("--force", action="store_true", help="Force reprocess")
    args = parser.parse_args()

    from scientra.io.article_bundle_importer import ArticleBundleImporter
    from scientra.io.storage_layout import StorageLayout

    sl = StorageLayout()
    sl.load()
    sl.ensure_all_directories()

    importer = ArticleBundleImporter()

    if args.scan:
        print("=== Scan Article Bundles ===")
        records = importer.scan()
        print(f"Found {len(records)} bundles:")
        for r in records:
            status = r.processing_status
            main = Path(r.detected_main_pdf).name if r.detected_main_pdf else "NONE"
            tab = len(r.tabular_supplementary_files)
            print(f"  [{status}] {r.bundle_name} | main={main} | tabular={tab} | suppl_pdf={len(r.supplementary_pdfs)}")
        print(f"\nRegistry saved to 10_System/registry/")

    elif args.process:
        mode = "copy" if args.dry_run else args.archive_mode
        print(f"=== Process Article Bundles (mode={mode}, dry_run={args.dry_run}) ===")
        result = importer.process(archive_mode=mode, dry_run=args.dry_run)
        print(f"Total: {result['total_bundles']}")
        print(f"Processed: {result['processed']}")
        print(f"Failed: {result['failed']}")
        for r in result.get("results", []):
            if args.dry_run:
                print(f"  [PLAN] {r['bundle_name']} -> main={r.get('would_copy_main','?')}")
            else:
                print(f"  [{r['status']}] {r['bundle_name']} | suppl={r.get('suppl_copied',0)}")
        print(f"\nRegistry: 10_System/registry/article_bundle_registry.json")

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
