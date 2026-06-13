"""Root cleanup — move dev files to docs/, launchers to Scripts/."""

import hashlib, json, shutil, sys
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

MOVES = [
    ("findings.md", "docs/development/findings.md"),
    ("progress.md", "docs/development/progress.md"),
    ("task_plan.md", "docs/development/task_plan.md"),
    ("Scientra_Copilot_使用手册.docx", "docs/manual/Scientra_Copilot_使用手册.docx"),
    ("Scientra_Copilot_使用手册_updated.docx", "docs/manual/Scientra_Copilot_使用手册_updated.docx"),
    ("start_scientra.bat", "Scripts/launchers/start_scientra.bat"),
    ("start_scientra.ps1", "Scripts/launchers/start_scientra.ps1"),
]

PROTECTED = ["README.md", "LICENSE", "workflow.py", "requirements.txt", "pyproject.toml"]


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    import argparse
    p = argparse.ArgumentParser(description="Clean up root directory files")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    rec_dir = root / "10_System" / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)

    if args.plan or args.dry_run:
        print("=== Root Cleanup Plan ===\n")
        for src_rel, dst_rel in MOVES:
            src = root / src_rel
            dst = root / dst_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            exists = src.exists()
            conflict = dst.exists()
            print(f"  {src_rel:50s} -> {dst_rel:50s} "
                  f"[{'exists' if exists else 'MISSING'}]"
                  f"{' CONFLICT' if conflict else ''}")
        plan = {"generated_at": ts, "moves": MOVES}
        (rec_dir / "root_cleanup_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        print(f"\nPlan saved to 10_System/records/")

    if args.dry_run:
        print("\n=== Dry Run — no files touched ===")

    if args.execute:
        print("=== Execute Cleanup ===\n")
        manifest = []
        for src_rel, dst_rel in MOVES:
            src = root / src_rel
            if not src.exists():
                print(f"  SKIP: {src_rel} (not found)")
                continue
            dst = root / dst_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                # Add timestamp suffix
                ts_sfx = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                dst = dst.with_stem(f"{dst.stem}_{ts_sfx}")
                dst_rel = str(dst.relative_to(root))
            shutil.move(str(src), str(dst))
            sha = _sha256_file(dst)
            entry = {
                "old_relative_path": src_rel,
                "new_relative_path": str(dst.relative_to(root)),
                "sha256": sha,
                "size_bytes": dst.stat().st_size,
                "moved_at": ts,
            }
            manifest.append(entry)
            print(f"  MOVED: {src_rel} -> {dst.relative_to(root)}")

        (rec_dir / "cleanup_manifest.json").write_text(
            json.dumps({"moved_at": ts, "files": manifest}, indent=2, ensure_ascii=False))
        (rec_dir / "root_cleanup_report.md").write_text(
            f"# Root Cleanup Report\n\nGenerated: {ts}\n\n"
            + "\n".join(f"- {e['old_relative_path']} -> {e['new_relative_path']}"
                        for e in manifest))
        print(f"\nManifest saved to 10_System/records/")

    if args.verify:
        print("=== Verify Cleanup ===\n")
        root_files = get_root_files()
        remaining = [f for f in MOVES if (root / f[0]).exists()]
        if remaining:
            print(f"WARNING: {len(remaining)} files still in root:")
            for r in remaining:
                print(f"  - {r[0]}")
        else:
            print("All moved files absent from root.")
        print(f"\nREADME.md in root: {(root / 'README.md').exists()}")
        print(f"workflow.py in root: {(root / 'workflow.py').exists()}")
        print(f"Protected files OK: {all((root / pf).exists() for pf in PROTECTED if (root / pf).exists() or pf not in ['LICENSE'])}")


def get_root_files():
    from pathlib import Path
    return [f.name for f in Path(".").iterdir() if f.is_file()]

if __name__ == "__main__":
    main()
