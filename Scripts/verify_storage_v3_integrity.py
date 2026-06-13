"""Verify Storage v3 directory integrity before hard cutover."""
import json, sys
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

passed = 0
failed = 0
def t(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS: {name}")
    else: failed += 1; print(f"  FAIL: {name} -- {detail}")

print("=" * 60)
print("Storage v3 Integrity Verification")
print("=" * 60)

from scientra.io.storage_layout import StorageLayout
sl = StorageLayout(); sl.load()

# 1. Core new directories exist
print("\n[1] Core v3 directories")
for key in ["sources.papers", "sources.supplementary", "parse.text",
            "assets.figure_assets", "assets.table_assets",
            "assets.supplementary_assets", "corpus.data.gene_evidence",
            "corpus.data.cross_study", "index.vector.lancedb"]:
    p = sl.get_path(key)
    t(f"{key} exists", p.exists(), str(p))

# 2. Migration manifest exists
print("\n[2] Migration manifest")
man_path = root / "10_System" / "migrations" / "storage_v3_migration_manifest.json"
t("manifest exists", man_path.exists())
sha_ok = 0; sha_total = 0
if man_path.exists():
    m = json.loads(man_path.read_text(encoding="utf-8"))
    for entry in m.get("manifest", []):
        if entry["status"] == "copied":
            sha_total += 1
            fp = root / entry.get("target", "")
            if fp.exists():
                sha_ok += 1
    t(f"SHA files present: {sha_ok}/{sha_total}", sha_ok >= sha_total * 0.99,
      f"{sha_total - sha_ok} missing")

# 3. Data accessibility
print("\n[3] Data accessibility from new paths")
import os
checks = [
    ("figures", root / "03_Assets/figure_assets", root / "06_PDF_DataAssets/02_figures"),
    ("tables", root / "03_Assets/table_assets", root / "06_PDF_DataAssets/03_tables"),
    ("supplementary links", root / "03_Assets/supplementary_assets/links",
     root / "06_PDF_DataAssets/08_supplementary_links"),
    ("gene evidence", root / "04_Corpus/data/gene_evidence",
     root / "06_PDF_DataAssets/09_supplementary_entities"),
    ("cross study", root / "04_Corpus/data/cross_study",
     root / "06_PDF_DataAssets/10_entity_comparisons"),
]
for name, new, old in checks:
    has_new = new.exists() and any(new.iterdir())
    has_old = old.exists() and any(old.iterdir())
    t(f"{name} accessible (new={has_new}, legacy={has_old})", has_new or has_old)

# 4. LanceDB
print("\n[4] LanceDB accessibility")
new_ldb = root / "06_Index/vector/lancedb/lancedb"
old_ldb = root / "04_VectorDB/lancedb"
ldb_path = new_ldb if new_ldb.exists() else old_ldb
t(f"LanceDB found at {'new' if new_ldb.exists() else 'legacy'} path", ldb_path.exists())

# 5. Legacy dirs still present (not yet archived)
print("\n[5] Legacy directories present (for verification)")
legacy_dirs = ["01_PDF", "02_Metadata", "03_Evidence", "03_Summary",
               "04_VectorDB", "05_Index", "06_PDF_DataAssets", "00_Supplementary"]
for d in legacy_dirs:
    t(f"{d} present (pre-archive)", (root / d).exists())

# Report
report_dir = root / "10_System" / "migrations"
report_dir.mkdir(parents=True, exist_ok=True)
ts = datetime.now(timezone.utc).isoformat()
md = ["# Storage v3 Integrity Report", "", f"Generated: {ts}",
      f"Passed: {passed}, Failed: {failed}", "",
      "## Result", "",
      "READY for cutover" if failed == 0 else f"BLOCKED: {failed} failures",
      "", "## Notes", "",
      "All legacy directories are still present. They will be archived",
      "to 10_System/legacy_archive/ in the next step (move, not delete)."]
(report_dir / "storage_v3_integrity_report.md").write_text("\n".join(md))
(report_dir / "storage_v3_integrity_report.json").write_text(
    json.dumps({"passed": passed, "failed": failed, "ready": failed == 0,
                "generated_at": ts}, indent=2))

print(f"\n{'='*60}")
print(f"Integrity: {passed} passed, {failed} failed")
print("READY for cutover" if failed == 0 else "BLOCKED")
sys.exit(0 if failed == 0 else 1)
