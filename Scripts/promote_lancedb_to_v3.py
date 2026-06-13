"""Promote LanceDB from legacy archive to v3 index directory.

Commands:
  python Scripts/promote_lancedb_to_v3.py --inspect
  python Scripts/promote_lancedb_to_v3.py --dry-run
  python Scripts/promote_lancedb_to_v3.py --execute
  python Scripts/promote_lancedb_to_v3.py --verify
"""
import hashlib, json, shutil, sys, time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

ARCHIVE_GLOB = "10_System/legacy_archive/storage_v1_legacy_*/04_VectorDB/lancedb"
V3_PATH = "06_Index/vector/lancedb"
LEGACY_PATH = "04_VectorDB/lancedb"
BACKUP_DIR = "10_System/backups"
REPORT_DIR = "10_System/migrations"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _inspect_lancedb(path: Path) -> dict:
    """Inspect a LanceDB directory."""
    info = {"path": str(path.relative_to(root)), "exists": path.exists(),
            "readable": False, "tables": {}, "size_bytes": 0, "file_count": 0,
            "error": None}
    if not path.exists():
        return info
    try:
        import lancedb
        db = lancedb.connect(str(path))
        tbls = db.table_names()
        for t in tbls:
            try:
                tbl = db.open_table(t)
                df = tbl.to_pandas()
                info["tables"][t] = len(df)
            except Exception as e:
                info["tables"][t] = f"error: {e}"
        info["readable"] = True
    except Exception as e:
        info["error"] = str(e)[:200]
    files = list(path.rglob("*"))
    info["file_count"] = len([f for f in files if f.is_file()])
    info["size_bytes"] = sum(f.stat().st_size for f in files if f.is_file())
    return info


def inspect():
    """Inspect all LanceDB candidates."""
    print("=== LanceDB V3 Promotion — Inspect ===\n")
    candidates = []

    # Archive
    for d in sorted(root.glob(ARCHIVE_GLOB)):
        info = _inspect_lancedb(d)
        info["label"] = "archive"
        candidates.append(info)

    # V3
    v3 = root / V3_PATH
    info3 = _inspect_lancedb(v3)
    info3["label"] = "v3_new"
    candidates.append(info3)

    # Legacy
    legacy = root / LEGACY_PATH
    infoL = _inspect_lancedb(legacy)
    infoL["label"] = "legacy_root"
    candidates.append(infoL)

    for c in candidates:
        print(f"[{c['label']}] {c['path']}")
        print(f"  Exists: {c['exists']}, Readable: {c['readable']}, Files: {c['file_count']}, Size: {c['size_bytes']:,} bytes")
        if c["error"]:
            print(f"  Error: {c['error']}")
        for t, rc in c["tables"].items():
            print(f"  Table: {t} = {rc} rows")
        print()

    # Select best source
    best = None
    for c in candidates:
        if c["readable"] and c["tables"]:
            total_rows = sum(v for v in c["tables"].values() if isinstance(v, int))
            if best is None or total_rows > best[1]:
                best = (c, total_rows)
    if best:
        print(f"Best source: [{best[0]['label']}] {best[0]['path']} ({best[1]} total rows)")
    else:
        print("No readable LanceDB found!")

    return candidates, best


def main():
    import argparse
    p = argparse.ArgumentParser(description="Promote LanceDB to v3 Index")
    p.add_argument("--inspect", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--verify", action="store_true")
    p.add_argument("--report", action="store_true")
    args = p.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    ts_short = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_dir = root / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    if args.inspect or args.dry_run:
        candidates, best = inspect()

    if args.dry_run:
        print("=== Dry Run ===")
        if best:
            src = root / best[0]["path"].lstrip(str(root) + "/")
            dst = root / V3_PATH
            print(f"Would copy from: {best[0]['path']}")
            print(f"To:             {V3_PATH}")
            print(f"Tables: {best[0]['tables']}")
            if dst.exists() and any(dst.iterdir()):
                print(f"BACKUP would be created (target non-empty)")
            print("No files touched.")
        return 0

    if args.execute:
        candidates, best = inspect()
        if not best:
            print("ERROR: No readable LanceDB source found.")
            return 1

        src = root / best[0]["path"].lstrip("/").replace("\\", "/")
        # Resolve properly
        src = root
        for part in best[0]["path"].replace("\\", "/").split("/"):
            src = src / part
        dst = root / V3_PATH

        # Backup if target has data
        backup_path = None
        if dst.exists() and any(dst.iterdir()):
            backup_path = root / BACKUP_DIR / f"lancedb_before_promote_{ts_short}"
            backup_path.mkdir(parents=True, exist_ok=True)
            print(f"Backing up existing v3 LanceDB to: {backup_path.relative_to(root)}")
            shutil.copytree(dst, backup_path / "lancedb")
            manifest = {"backup_time": ts, "source": V3_PATH,
                        "target": str(backup_path.relative_to(root)),
                        "files": len(list(dst.rglob("*")))}
            (backup_path / "backup_manifest.json").write_text(json.dumps(manifest, indent=2))

        # Copy
        print(f"Copying from: {src}")
        print(f"To:          {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(src), str(dst))
        time.sleep(1)  # Let filesystem settle

        # Verify copy
        src_info = _inspect_lancedb(src)
        dst_info = _inspect_lancedb(dst)
        ok = True
        manifest_entries = []
        for t, rc in src_info["tables"].items():
            dst_rc = dst_info["tables"].get(t, 0)
            match = isinstance(dst_rc, int) and dst_rc == rc
            manifest_entries.append({"table": t, "source_rows": rc, "target_rows": dst_rc, "match": match})
            if not match:
                print(f"  MISMATCH: {t} src={rc} dst={dst_rc}")
                ok = False
            else:
                print(f"  OK: {t} = {rc} rows")

        # Save manifest
        mf = {"promoted_at": ts, "source": str(src.relative_to(root)),
              "target": V3_PATH, "backup": str(backup_path.relative_to(root)) if backup_path else None,
              "tables": manifest_entries, "success": ok,
              "source_files": src_info["file_count"], "target_files": dst_info["file_count"]}
        (report_dir / "lancedb_v3_promotion_manifest.json").write_text(json.dumps(mf, indent=2, ensure_ascii=False))

        # Report
        lines = ["# LanceDB V3 Promotion Report", "", f"Generated: {ts}",
                 f"Source: {src.relative_to(root)}", f"Target: {V3_PATH}",
                 f"Backup: {backup_path.relative_to(root) if backup_path else 'none'}", "",
                 "## Table Verification", ""]
        for e in manifest_entries:
            lines.append(f"- {e['table']}: {e['source_rows']} rows -> {e['target_rows']} rows "
                        f"({'OK' if e['match'] else 'MISMATCH'})")
        lines.append("")
        lines.append(f"Overall: {'SUCCESS' if ok else 'FAILED'}")
        (report_dir / "lancedb_v3_promotion_report.md").write_text("\n".join(lines))

        print(f"\nPromotion {'SUCCESS' if ok else 'FAILED'}")
        print(f"Report: 10_System/migrations/")
        return 0 if ok else 1

    if args.verify:
        v3 = root / V3_PATH
        info = _inspect_lancedb(v3)
        print("=== Verify V3 LanceDB ===")
        print(f"Path: {V3_PATH}")
        print(f"Readable: {info['readable']}")
        for t, rc in info["tables"].items():
            print(f"  {t}: {rc} rows")
        ok = info["readable"] and len(info["tables"]) >= 1
        print(f"\nVerification: {'PASS' if ok else 'FAIL'}")

        lines = ["# LanceDB V3 Verify Report", "", f"Readable: {info['readable']}",
                 f"Tables: {len(info['tables'])}", ""]
        for t, rc in info["tables"].items():
            lines.append(f"- {t}: {rc} rows")
        (report_dir / "lancedb_v3_verify_report.md").write_text("\n".join(lines))
        return 0 if ok else 1

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
