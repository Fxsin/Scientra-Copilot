"""Archive legacy layout directories to 10_System/legacy_archive/.

Moves old dirs, never deletes. 00_Inbox preserved (v3 entry point).
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

LEGACY_DIRS = [
    "00_Supplementary", "01_PDF", "02_Metadata", "03_Evidence",
    "03_Summary", "04_VectorDB", "05_Index", "06_PDF_DataAssets",
]
# Preserve 00_Inbox but move loose files
INBOX_PRESERVE = ["article_bundles", "single_papers", "loose_supplementary"]


def _sha256_dir(d: Path) -> str:
    if not d.is_dir(): return ""
    parts = sorted(f"{f.relative_to(d)}:{hashlib.sha256(f.read_bytes()).hexdigest()}"
                   for f in d.rglob("*") if f.is_file())
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description="Archive legacy storage layout")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--mode", default="move-to-archive",
                   choices=["move-to-archive", "copy-to-archive"])
    p.add_argument("--verify", action="store_true")
    p.add_argument("--delete-archive", action="store_true")
    p.add_argument("--confirm-delete", action="store_true")
    args = p.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    ts_short = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_root = root / "10_System" / "legacy_archive" / f"storage_v1_legacy_{ts_short}"
    report_dir = root / "10_System" / "migrations"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Plan
    items = []
    for d in LEGACY_DIRS:
        src = root / d
        if not src.exists():
            items.append({"dir": d, "status": "missing", "size": 0})
            continue
        size = sum(f.stat().st_size for f in src.rglob("*") if f.is_file())
        items.append({"dir": d, "status": "present", "size": size})

    # 00_Inbox loose files
    inbox = root / "00_Inbox"
    loose = []
    if inbox.exists():
        for entry in inbox.iterdir():
            if entry.name in INBOX_PRESERVE:
                continue
            if entry.is_file() or (entry.is_dir() and entry.name not in INBOX_PRESERVE):
                loose.append(str(entry.relative_to(root)))
    if loose:
        items.append({"dir": "00_Inbox/loose_files", "status": "loose",
                      "files": loose, "size": 0})

    if args.plan:
        print("=== Legacy Archive Plan ===")
        for it in items:
            print(f"  {it['dir']}: {it['status']}, size={it.get('size', 0):,} bytes")
        plan = {"generated_at": ts, "items": items, "archive_target": str(archive_root.relative_to(root))}
        (report_dir / "legacy_archive_plan.json").write_text(json.dumps(plan, indent=2))
        print(f"\nPlan saved. Target: {archive_root.relative_to(root)}")
        return 0

    if args.dry_run:
        print("=== Dry Run ===")
        total = sum(it.get("size", 0) for it in items)
        print(f"Would archive {len([i for i in items if i['status']=='present'])} dirs, {total:,} bytes")
        if loose:
            print(f"Would move {len(loose)} loose files from 00_Inbox")
        print(f"Destination: {archive_root.relative_to(root)}")
        print("No files touched.")
        return 0

    if args.execute:
        mode = args.mode
        print(f"=== Execute Archive (mode={mode}) ===")
        archive_root.mkdir(parents=True, exist_ok=True)
        manifest = {"generated_at": ts, "mode": mode, "archive_root": str(archive_root.relative_to(root)), "entries": []}

        for it in items:
            d = it["dir"]
            if d == "00_Inbox/loose_files":
                # Move loose files to archive
                loose_archive = archive_root / "00_Inbox_legacy_files"
                loose_archive.mkdir(parents=True, exist_ok=True)
                for f_rel in it.get("files", []):
                    src = root / f_rel
                    dst = loose_archive / src.name
                    if mode == "move-to-archive":
                        shutil.move(str(src), str(dst))
                    else:
                        if src.is_dir():
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
                manifest["entries"].append({"dir": d, "action": mode, "files": len(it.get("files", []))})
                print(f"  {d}: {len(it.get('files', []))} loose files {mode}d")
                continue

            if it["status"] != "present":
                continue
            src = root / d
            dst = archive_root / d
            try:
                if mode == "move-to-archive":
                    shutil.move(str(src), str(dst))
                else:
                    shutil.copytree(src, dst)
                manifest["entries"].append({"dir": d, "action": mode, "status": "ok"})
                print(f"  {d}: {mode}d to archive")
            except Exception as e:
                manifest["entries"].append({"dir": d, "action": mode, "status": "failed", "error": str(e)[:200]})
                print(f"  {d}: FAILED — {e}")

        (report_dir / "legacy_archive_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
        md = [f"# Legacy Archive Report", "", f"Generated: {ts}", f"Mode: {mode}",
              f"Target: {archive_root.relative_to(root)}", ""]
        for e in manifest["entries"]:
            md.append(f"- {e['dir']}: {e.get('action','?')} — {e.get('status','?')}")
        (report_dir / "legacy_archive_report.md").write_text("\n".join(md))
        print(f"\nArchive complete. Reports in 10_System/migrations/")
        return 0

    if args.verify:
        print("=== Verify Archive ===")
        manifests = list(report_dir.glob("legacy_archive_manifest*.json"))
        if not manifests:
            print("No manifest found. Run --execute first.")
            return 1
        m = json.loads(manifests[-1].read_text(encoding="utf-8"))
        ok = 0; missing = 0
        for e in m.get("entries", []):
            for d_name in LEGACY_DIRS + ["00_Inbox/loose_files"]:
                if e["dir"] == d_name and "00_Inbox" not in d_name:
                    if (root / d_name).exists():
                        print(f"  {d_name}: STILL PRESENT (may need re-archive)")
                        missing += 1
                    else:
                        print(f"  {d_name}: archived OK")
                        ok += 1
        print(f"\nVerified: {ok} archived, {missing} still present")
        md = [f"# Archive Verification", "", f"Archived OK: {ok}", f"Still present: {missing}"]
        (report_dir / "legacy_archive_verify_report.md").write_text("\n".join(md))
        return 0

    if args.delete_archive:
        if not args.confirm_delete:
            print("ERROR: --confirm-delete required for --delete-archive")
            return 1
        archives = sorted(root.rglob("10_System/legacy_archive/storage_v1_legacy_*"))
        for a in archives:
            if a.is_dir():
                print(f"Would delete: {a.relative_to(root)}")
        print("\nDeletion blocked in this phase. Manual confirmation required.")
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
