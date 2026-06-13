"""
Storage Migrator v3 — plan, dry-run, copy, and verify migration.

Phase: Always copy-only by default. Never deletes source files.
SHA256 dedup; conflicts get suffix rename. No absolute paths in reports.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_dir(path: Path) -> str:
    """Compute aggregate SHA256 of directory contents (sorted by name)."""
    if not path.is_dir():
        return _sha256_file(path) if path.is_file() else ""
    parts = []
    for f in sorted(path.rglob("*")):
        if f.is_file():
            parts.append(f"{f.relative_to(path)}:{_sha256_file(f)}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


class StorageMigrator:
    """Plans and executes storage migration from old to new paths."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).resolve() if root else Path(__file__).resolve().parent.parent.parent
        self.report_dir = self.root / "10_System" / "migrations"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def load_migration_map(self) -> list[dict[str, str]]:
        """Load migration mappings from config."""
        import yaml
        map_path = self.root / "Config" / "storage_migration_map.yaml"
        if not map_path.exists():
            return []
        try:
            with open(map_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config.get("mappings", [])
        except Exception:
            return []

    def plan(self) -> dict[str, Any]:
        """Generate migration plan. No files touched."""
        mappings = self.load_migration_map()
        items: list[dict[str, Any]] = []
        total_files = 0
        total_size = 0

        for m in mappings:
            source = self.root / m["source"]
            target_dir = self.root / m["target"]
            if not source.exists():
                items.append({**m, "status": "source_missing", "files": 0, "size": 0})
                continue

            files = []
            if source.is_dir():
                for f in source.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(source)
                        target_file = target_dir / rel
                        files.append({
                            "source": str(f.relative_to(self.root)),
                            "target": str(target_file.relative_to(self.root)),
                            "size": f.stat().st_size,
                        })
            elif source.is_file():
                files.append({
                    "source": str(source.relative_to(self.root)),
                    "target": str((target_dir / source.name).relative_to(self.root)),
                    "size": source.stat().st_size,
                })

            items.append({
                **m,
                "status": "planned",
                "files": len(files),
                "size": sum(f["size"] for f in files),
                "file_list": files[:100],  # Cap for readability
            })
            total_files += len(files)
            total_size += sum(f["size"] for f in files)

        plan = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_mappings": len(mappings),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "items": items,
        }

        # Save plan
        plan_path = self.report_dir / "storage_v3_migration_plan.json"
        tmp = plan_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(plan_path)

        # Write human-readable plan
        md_path = self.report_dir / "storage_v3_migration_plan.md"
        lines = [
            "# Storage Migration v3 — Plan", "",
            f"Generated: {plan['generated_at']}",
            f"Total mappings: {plan['total_mappings']}",
            f"Total files: {plan['total_files']}",
            f"Total size: {plan['total_size_bytes']:,} bytes",
            "", "## Per-Mapping Summary", "",
        ]
        for item in items:
            lines.append(f"- `{item['source']}` → `{item['target']}`: "
                        f"{item['files']} files ({item['size']:,} bytes) [{item['status']}]")
        lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")

        return plan

    def dry_run(self) -> dict[str, Any]:
        """Simulate migration, reporting what would happen."""
        plan = self.plan()
        conflicts = 0
        new_files = 0
        for item in plan["items"]:
            for f in item.get("file_list", []):
                target = self.root / f["target"]
                if target.exists():
                    conflicts += 1
                else:
                    new_files += 1
        plan["dry_run"] = {"conflicts": conflicts, "new_files": new_files,
                           "would_copy": new_files, "would_skip": conflicts}
        return plan

    def execute(self, mode: str = "copy") -> dict[str, Any]:
        """Execute migration. mode='copy' (default) preserves source files."""
        plan = self.plan()
        manifest: list[dict[str, Any]] = []
        timestamp = datetime.now(timezone.utc).isoformat()
        copied = 0
        skipped = 0
        errors = 0

        for item in plan["items"]:
            for f in item.get("file_list", []):
                source = self.root / f["source"]
                target = self.root / f["target"]
                entry = {
                    "source": f["source"], "target": f["target"],
                    "size": f["size"], "action": mode, "status": "pending",
                    "error_message": None, "migrated_at": timestamp,
                }

                if not source.exists():
                    entry["status"] = "source_missing"
                    entry["error_message"] = "Source file not found"
                    errors += 1
                    manifest.append(entry)
                    continue

                # Compute hashes
                try:
                    source_sha = _sha256_file(source)
                    entry["sha256"] = source_sha
                except Exception:
                    source_sha = ""

                # Check conflict
                if target.exists():
                    try:
                        target_sha = _sha256_file(target)
                    except Exception:
                        target_sha = ""
                    if source_sha and target_sha and source_sha == target_sha:
                        entry["status"] = "skipped_identical"
                        skipped += 1
                        manifest.append(entry)
                        continue
                    # Conflict — rename target
                    stem = target.stem
                    suffix = target.suffix
                    counter = 1
                    while target.exists():
                        target = target.with_name(f"{stem}_v3conflict_{counter}{suffix}")
                        counter += 1
                    f["target"] = str(target.relative_to(self.root))
                    entry["target"] = f["target"]

                # Copy
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    entry["status"] = "copied"
                    entry["sha256"] = _sha256_file(target)
                    copied += 1
                except Exception as e:
                    entry["status"] = "failed"
                    entry["error_message"] = str(e)[:200]
                    errors += 1

                manifest.append(entry)

        result = {
            "generated_at": timestamp, "mode": mode,
            "total": len(manifest), "copied": copied, "skipped": skipped,
            "errors": errors, "manifest": manifest,
        }

        # Save manifest
        manifest_path = self.report_dir / "storage_v3_migration_manifest.json"
        tmp = manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(manifest_path)

        # Write report
        md_path = self.report_dir / "storage_v3_migration_report.md"
        lines = [
            "# Storage Migration v3 — Report", "",
            f"Generated: {timestamp}", f"Mode: {mode}",
            f"Total files: {result['total']}",
            f"Copied: {copied}", f"Skipped (identical): {skipped}",
            f"Errors: {errors}", "",
        ]
        md_path.write_text("\n".join(lines), encoding="utf-8")

        return result

    def verify(self) -> dict[str, Any]:
        """Verify migration: check all manifest targets exist and match SHA256."""
        manifest_path = self.report_dir / "storage_v3_migration_manifest.json"
        if not manifest_path.exists():
            return {"error": "No manifest found. Run execute first."}

        try:
            result = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"error": "Manifest unreadable."}

        manifest = result.get("manifest", [])
        verified = 0
        mismatch = 0
        missing = 0

        for entry in manifest:
            if entry["status"] not in ("copied", "skipped_identical"):
                continue
            target = self.root / entry["target"]
            if not target.exists():
                entry["verify_status"] = "missing"
                missing += 1
                continue
            try:
                current_sha = _sha256_file(target)
            except Exception:
                entry["verify_status"] = "unreadable"
                mismatch += 1
                continue
            if current_sha == entry.get("sha256", ""):
                entry["verify_status"] = "verified"
                verified += 1
            else:
                entry["verify_status"] = "sha256_mismatch"
                mismatch += 1

        verify_result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_checked": verified + mismatch + missing,
            "verified": verified, "mismatch": mismatch, "missing": missing,
            "manifest": manifest,
        }

        # Save verification report
        v_path = self.report_dir / "storage_v3_verification_report.json"
        tmp = v_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(verify_result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(v_path)

        md_path = self.report_dir / "storage_v3_verification_report.md"
        lines = [
            "# Storage Migration v3 — Verification", "",
            f"Verified: {verified}", f"SHA256 mismatch: {mismatch}",
            f"Missing: {missing}", "",
        ]
        md_path.write_text("\n".join(lines), encoding="utf-8")

        return verify_result
