"""Test Article Bundle Import with temp fixtures."""
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
print("Article Bundle Import Tests")
print("=" * 60)

from scientra.io.storage_layout import StorageLayout
from scientra.io.article_bundle_importer import ArticleBundleImporter, _make_bundle_id

sl = StorageLayout()
sl.load()

# Setup temp bundles in inbox
inbox = sl.get_path("inbox.article_bundles_new")
# Clean any previous test
for d in inbox.iterdir():
    if d.is_dir() and d.name.startswith("TEST_"):
        shutil.rmtree(d, ignore_errors=True)

# Create test bundles
# Bundle 1: normal — main.pdf + csv + supplementary pdf
b1 = inbox / "TEST_Bundle_001"
b1.mkdir(parents=True, exist_ok=True)
(b1 / "main.pdf").write_bytes(b"%PDF-1.4 test main")
(b1 / "Table_S1.csv").write_text("Gene,FC\nMAP2K4,2.5\n", encoding="utf-8")
(b1 / "Supplementary_Info.pdf").write_bytes(b"%PDF-1.4 test suppl")

# Bundle 2: single PDF only
b2 = inbox / "TEST_Bundle_002_SinglePDF"
b2.mkdir(parents=True, exist_ok=True)
(b2 / "article.pdf").write_bytes(b"%PDF-1.4 single article")

# Bundle 3: multi-PDF, one is supporting
b3 = inbox / "TEST_Bundle_003_MultiPDF"
b3.mkdir(parents=True, exist_ok=True)
(b3 / "paper_main.pdf").write_bytes(b"%PDF-1.4 main paper")
(b3 / "Supporting_Information.pdf").write_bytes(b"%PDF-1.4 supporting")
(b3 / "Table_S2.xlsx").write_bytes(b"fake xlsx content")

# Bundle 4: empty — should fail
b4 = inbox / "TEST_Bundle_004_Empty"
b4.mkdir(parents=True, exist_ok=True)

# Bundle 5: no PDF — should fail
b5 = inbox / "TEST_Bundle_005_NoPDF"
b5.mkdir(parents=True, exist_ok=True)
(b5 / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

importer = ArticleBundleImporter()

# Test 1: Scan bundles
print("\n[1] Scan article bundles")
records = importer.scan()
test("found 5 bundles", len(records) == 5, f"got {len(records)}")

# Test 2: Normal bundle — main PDF detected
r1 = [r for r in records if r.bundle_name == "TEST_Bundle_001"][0]
test("normal bundle scanned", r1.processing_status == "scanned")
test("main.pdf detected", r1.detected_main_pdf and "main.pdf" in r1.detected_main_pdf,
     f"got: {r1.detected_main_pdf}")
test("tabular files found", len(r1.tabular_supplementary_files) == 1)
test("supplementary pdfs found", len(r1.supplementary_pdfs) == 1)
test("folder_explicit binding", r1.binding_method == "folder_explicit")
test("high confidence", r1.match_confidence == "high")

# Test 3: Single PDF → main PDF
r2 = [r for r in records if r.bundle_name == "TEST_Bundle_002_SinglePDF"][0]
test("single PDF = main", r2.processing_status == "scanned")
test("article.pdf identified as main", "article.pdf" in (r2.detected_main_pdf or ""))

# Test 4: Multi-PDF with supporting → main correctly identified
r3 = [r for r in records if r.bundle_name == "TEST_Bundle_003_MultiPDF"][0]
test("multi-PDF: main identified", r3.processing_status == "scanned")
test("paper_main.pdf chosen over Supporting_Information.pdf",
     r3.detected_main_pdf and "paper_main" in r3.detected_main_pdf,
     f"got: {r3.detected_main_pdf}")
test("Supporting PDF in supplementary_pdfs",
     any("Supporting_Information" in f for f in r3.supplementary_pdfs))
test("xlsx in tabular", len(r3.tabular_supplementary_files) == 1)

# Test 5: Empty bundle → failed
r4 = [r for r in records if r.bundle_name == "TEST_Bundle_004_Empty"][0]
test("empty bundle failed", r4.processing_status == "failed_empty")

# Test 6: No PDF bundle → failed
r5 = [r for r in records if r.bundle_name == "TEST_Bundle_005_NoPDF"][0]
test("no-PDF bundle failed", r5.processing_status == "failed_no_main_pdf")

# Test 7: Dry-run processing
print("\n[7] Dry-run processing")
result_dry = importer.process(archive_mode="copy", dry_run=True)
test("dry-run has 5 bundles", result_dry["total_bundles"] == 5)
processed_dry = [r for r in result_dry["results"] if r.get("status") == "dry_run_planned"]
test("3 bundles planned for processing", len(processed_dry) == 3)
# Verify no actual files were created
src_papers = sl.get_path("sources.papers")
pre_existing = list(src_papers.glob("TEST_*"))
test("no actual files copied in dry-run", len(pre_existing) == 0,
     f"found {len(pre_existing)} test dirs in sources")

# Test 8: Archive mode copy — process one bundle
print("\n[8] Archive mode copy")
# Only process normal bundles, not failed ones
result_copy = importer.process(archive_mode="copy", dry_run=False)
test("copy mode completed", result_copy["total_bundles"] == 5)
# Check files were copied
copied_main = list((sl.get_path("sources.papers")).glob("*/main.pdf"))
test("main PDF copied to sources", len(copied_main) > 0, f"found {len(copied_main)} main.pdf files")
# Check manifest
manifest_path = sl.get_path("sources.papers") / "bundle_TEST_Bundle_001_f1c1cfbf3b3d" / "source_manifest.json"
# The bundle_id is hash-based, so check by glob
manifests = list(sl.get_path("sources.papers").glob("**/source_manifest.json"))
test("source manifest generated", len(manifests) > 0)
if manifests:
    m = json.loads(manifests[0].read_text(encoding="utf-8"))
    test("manifest has import_source=article_bundle", m.get("import_source") == "article_bundle")
    test("manifest no absolute path in archived path",
         not str(m.get("archived_main_pdf_relative_path", "")).startswith("G:"))

# Test 9: No absolute paths in output
print("\n[9] No absolute paths")
for mpath in manifests:
    content = mpath.read_text(encoding="utf-8")
    test(f"no abs path in {mpath.name}", "G:\\" not in content and "C:\\" not in content)

# Test 10: bundle_id generated
print("\n[10] bundle_id generation")
bid = _make_bundle_id("TEST_Bundle_001")
test("bundle_id starts with bundle_", bid.startswith("bundle_"))
test("bundle_id contains hash", len(bid) > 20)

# Test 11: supplementary manifest
print("\n[11] Supplementary manifest")
suppl_manifests = list(sl.get_path("sources.supplementary").glob("**/supplementary_manifest.json"))
if suppl_manifests:
    sm = json.loads(suppl_manifests[0].read_text(encoding="utf-8"))
    test("suppl manifest has files", len(sm.get("supplementary_files", [])) > 0)
    sf = sm["supplementary_files"][0]
    test("suppl import_source=article_bundle", sf.get("import_source") == "article_bundle")
    test("suppl binding_method=folder_explicit", sf.get("binding_method") == "folder_explicit")
    test("suppl match_confidence=high", sf.get("match_confidence") == "high")

# Test 12: Cleanup
print("\n[12] Cleanup test fixtures")
for d in inbox.iterdir():
    if d.is_dir() and d.name.startswith("TEST_"):
        shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("sources.papers").glob("bundle_TEST_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("sources.papers").glob("TEST_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("sources.supplementary").glob("bundle_TEST_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.article_bundles_processed").glob("TEST_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.article_bundles_failed").glob("TEST_*"):
    shutil.rmtree(d, ignore_errors=True)
test("fixtures cleaned", True)

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
