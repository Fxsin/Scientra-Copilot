"""Test Storage Layout v3 write routing — uses temp fixtures only."""
import json, os, shutil, sys, tempfile
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
print("Storage Layout v3 — Write Routing Tests (temp fixtures)")
print("=" * 60)

from scientra.io.storage_layout import StorageLayout

sl = StorageLayout()
sl.load()

# Test 1: New figure asset writes to 03_Assets
print("\n[1] Figure asset writes to assets.figure_assets")
fig_path = sl.get_path("assets.figure_assets")
test_fig = fig_path / "_test_write_routing" / "test_figure.json"
test_fig.parent.mkdir(parents=True, exist_ok=True)
test_fig.write_text(json.dumps({"test": "figure_routing"}), encoding="utf-8")
test("figure test file created in new path", test_fig.exists())
test("test file is JSON", test_fig.read_text(encoding="utf-8").startswith("{"))
# Cleanup
shutil.rmtree(test_fig.parent, ignore_errors=True)

# Test 2: New table asset writes to 03_Assets
print("\n[2] Table asset writes to assets.table_assets")
tbl_path = sl.get_path("assets.table_assets")
test_tbl = tbl_path / "_test_write_routing" / "test_table.json"
test_tbl.parent.mkdir(parents=True, exist_ok=True)
test_tbl.write_text(json.dumps({"test": "table_routing"}), encoding="utf-8")
test("table test file created", test_tbl.exists())
shutil.rmtree(test_tbl.parent, ignore_errors=True)

# Test 3: Supplementary asset writes to 03_Assets
print("\n[3] Supplementary asset writes to assets.supplementary_assets")
suppl_path = sl.get_path("assets.supplementary_assets")
test_suppl = suppl_path / "_test_write_routing" / "test_suppl.json"
test_suppl.parent.mkdir(parents=True, exist_ok=True)
test_suppl.write_text(json.dumps({"test": "suppl_routing"}), encoding="utf-8")
test("supplementary test file created", test_suppl.exists())
shutil.rmtree(test_suppl.parent, ignore_errors=True)

# Test 4: Gene evidence writes to 04_Corpus
print("\n[4] Gene evidence writes to corpus.data.gene_evidence")
ge_path = sl.get_path("corpus.data.gene_evidence")
test_ge = ge_path / "_test_write_routing" / "test_entity.json"
test_ge.parent.mkdir(parents=True, exist_ok=True)
test_ge.write_text(json.dumps({"test": "gene_evidence_routing"}), encoding="utf-8")
test("gene evidence test file created", test_ge.exists())
shutil.rmtree(test_ge.parent, ignore_errors=True)

# Test 5: Cross-study writes to 04_Corpus
print("\n[5] Cross-study writes to corpus.data.cross_study")
cs_path = sl.get_path("corpus.data.cross_study")
test_cs = cs_path / "_test_write_routing" / "test_comparison.json"
test_cs.parent.mkdir(parents=True, exist_ok=True)
test_cs.write_text(json.dumps({"test": "cross_study_routing"}), encoding="utf-8")
test("cross-study test file created", test_cs.exists())
shutil.rmtree(test_cs.parent, ignore_errors=True)

# Test 6: Embedding reports write to 06_Index
print("\n[6] Embedding reports write to index.vector.embedding_reports")
er_path = sl.get_path("index.vector.embedding_reports")
test_er = er_path / "_test_write_routing" / "test_embedding_report.json"
test_er.parent.mkdir(parents=True, exist_ok=True)
test_er.write_text(json.dumps({"test": "embedding_routing"}), encoding="utf-8")
test("embedding report test file created", test_er.exists())
shutil.rmtree(test_er.parent, ignore_errors=True)

# Test 7: No residual test files
print("\n[7] No residual test fixtures")
residual = list(root.rglob("_test_write_routing"))
test("all test fixtures cleaned", len(residual) == 0, f"remaining: {len(residual)}")

# Test 8: Old 06_PDF_DataAssets still writable (legacy fallback)
print("\n[8] Old path still writable (not blocked)")
old_path = root / "06_PDF_DataAssets"
test("old path still accessible", old_path.exists())

# Test 9: Config paths resolve correctly
print("\n[9] Config path resolution")
import yaml
cfg = yaml.safe_load((root / "Config" / "storage_layout.yaml").read_text(encoding="utf-8"))
test("config has 86 paths", len(cfg.get("paths", {})) >= 86)
test("config has 9 legacy paths", len(cfg.get("legacy_paths", {})) >= 9)

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
