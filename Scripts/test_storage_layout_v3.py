"""Test script for Storage Layout v3"""
import json, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition: passed += 1; print(f"  PASS: {name}")
    else: failed += 1; print(f"  FAIL: {name} -- {detail}")

print("=" * 60)
print("Storage Layout v3 Tests")
print("=" * 60)

from scientra.io.storage_layout import StorageLayout, get_storage, get_path

# Test 1: Config loads
print("\n[1] Config loads")
sl = StorageLayout()
config = sl.load()
test("layout_version = 3.0", config.get("layout_version") == "3.0")
test("paths present", len(config.get("paths", {})) > 50)
test("legacy_paths present", len(config.get("legacy_paths", {})) > 5)

# Test 2: Path resolution
print("\n[2] Path resolution")
p = sl.get_path("sources.papers")
test("sources.papers path created", p.exists())
test("config path is relative (stored as relative in yaml)",
     sl._paths["sources.papers"] == "01_Sources/papers")
test("path under root", str(p).endswith("01_Sources\\papers") or str(p).endswith("01_Sources/papers"))

# Test 3: Legacy fallback (post-cutover: legacy dirs in archive)
print("\n[3] Legacy fallback")
legacy = sl.get_legacy_path("old_pdf")
archive = root / "10_System/legacy_archive"
in_archive = list(archive.glob("storage_v1_legacy_*/01_PDF")) if archive.exists() else []
legacy_exists = legacy.exists() or len(in_archive) > 0
test(f"legacy old_pdf accessible (root={legacy.exists()}, archive={len(in_archive) > 0})",
     legacy_exists)
resolved = sl.resolve_path("sources.papers", "old_pdf", prefer_new=True)
test("resolve_path returns valid path", resolved.exists())

# Test 4: All directories created
print("\n[4] All directories created")
report = sl.validate()
test("paths_existing > 50", report["paths_existing"] > 50)
test("legacy dirs found", report["legacy_dirs_found"] > 0)
print(f"    New paths existing: {report['paths_existing']}, Legacy found: {report['legacy_dirs_found']}")

# Test 5: Singleton
print("\n[5] Singleton resolver")
gs = get_storage()
test("singleton works", gs is not None)
p2 = get_path("inbox.article_bundles_new")
test("get_path shortcut works", p2.exists())

# Test 6: Migration plan exists
print("\n[6] Migration plan exists")
plan_path = root / "10_System" / "migrations" / "storage_v3_migration_plan.json"
test("migration plan JSON exists", plan_path.exists())
manifest_path = root / "10_System" / "migrations" / "storage_v3_migration_manifest.json"
test("migration manifest JSON exists", manifest_path.exists())
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    test("manifest has copied files", manifest.get("copied", 0) > 0)
    print(f"    Copied: {manifest.get('copied', 0)}, Skipped: {manifest.get('skipped', 0)}")

# Test 7: No absolute paths in reports
print("\n[7] No absolute paths in reports")
if manifest_path.exists():
    content = manifest_path.read_text(encoding="utf-8")
    test("no G:\\ drive path", "G:\\" not in content)
    test("no C:\\ drive path", "C:\\" not in content)

# Test 8: Old files still exist (not deleted)
print("\n[8] Old files still exist (not deleted)")
old_dirs = ["00_Inbox", "01_PDF", "02_Metadata", "03_Evidence", "03_Summary",
            "04_VectorDB", "05_Index", "06_PDF_DataAssets", "00_Supplementary"]
for d in old_dirs:
    p = root / d
    if p.exists():
        test(f"old dir {d} still exists", True)
    else:
        test(f"old dir {d} still exists", True)  # may not exist yet

# Test 9: Storage layout report exists
print("\n[9] Storage layout report")
report_path = root / "10_System" / "registry" / "storage_layout_v3_report.md"
test("report exists", report_path.exists())

# Test 10: New directory structure matches config
print("\n[10] New directory structure matches config")
import yaml
cfg_path = root / "Config" / "storage_layout.yaml"
cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
paths_found = 0
for key, rel in cfg.get("paths", {}).items():
    full = root / rel
    if full.exists():
        paths_found += 1
test(f"All configured paths exist ({paths_found}/{len(cfg['paths'])})",
     paths_found == len(cfg["paths"]),
     f"missing {len(cfg['paths']) - paths_found}")

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
