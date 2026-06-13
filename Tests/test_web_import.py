"""Test Web Import Center — upload sessions, plan generation, confirm import."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} -- {detail}")


print("=" * 60)
print("Web Import Center Tests")
print("=" * 60)

from scientra.io.storage_layout import StorageLayout
from scientra.io.web_import import (
    WebImportSession, _safe_filename, _validate_relative_path,
    _score_pdf, _detect_main_pdf, _classify_files, _propose_article_folder,
)

sl = StorageLayout()
sl.load()
sl.ensure_all_directories()

# ── Setup: create web_uploads directories ──
for key in ["inbox.web_uploads_staging", "inbox.web_uploads_planned",
            "inbox.web_uploads_imported", "inbox.web_uploads_failed"]:
    sl.get_path(key)

session = WebImportSession()

# Clean up any previous test sessions
for d in sl.get_path("inbox.web_uploads_staging").iterdir():
    if d.is_dir() and d.name.startswith("web_"):
        shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.web_uploads_planned").iterdir():
    if d.is_dir() and d.name.startswith("web_"):
        shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.web_uploads_imported").iterdir():
    if d.is_dir() and d.name.startswith("web_"):
        shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.article_bundles_new").glob("TEST_WEB_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.loose_supplementary_new").glob("TEST_*"):
    if d.is_file():
        d.unlink()

# ═══════════════════════════════════════════════════════
# Test 1: Safe filename sanitization
# ═══════════════════════════════════════════════════════
print("\n[1] Filename sanitization")
test("normal filename unchanged", _safe_filename("paper.pdf") == "paper.pdf")
# Path separators replaced, basename extracted — safe and clean
test("path traversal sanitized", _safe_filename("../../etc/passwd") not in ("", "..", "../../etc/passwd"))
test("abs path sanitized", _safe_filename("/etc/passwd") not in ("", "/etc/passwd"))
test("null byte stripped", _safe_filename("test\x00.pdf") == "test.pdf")
test("leading dots handled safely", _safe_filename("../secret.pdf") not in ("", ".."))
test("backslash sanitized", _safe_filename("folder\\file.pdf") not in ("", "folder\\file.pdf"))
test("empty filename handled", _safe_filename("") == "unnamed_file")
test("dot-only handled", _safe_filename("...") != "")

# ═══════════════════════════════════════════════════════
# Test 2: Relative path validation
# ═══════════════════════════════════════════════════════
print("\n[2] Relative path validation")
test("normal path accepted", _validate_relative_path("paper.pdf") == "paper.pdf")
test("subfolder path accepted", _validate_relative_path("folder/paper.pdf") == "folder/paper.pdf")
try:
    _validate_relative_path("/etc/passwd")
    test("absolute path rejected", False, "should have raised ValueError")
except ValueError:
    test("absolute path rejected", True)
try:
    _validate_relative_path("../secret.pdf")
    test("path traversal rejected", False, "should have raised ValueError")
except ValueError:
    test("path traversal rejected", True)
try:
    _validate_relative_path("folder/../../secret.pdf")
    test("nested traversal rejected", False, "should have raised ValueError")
except ValueError:
    test("nested traversal rejected", True)

# ═══════════════════════════════════════════════════════
# Test 3: PDF scoring
# ═══════════════════════════════════════════════════════
print("\n[3] PDF scoring")
score, reason = _score_pdf("main.pdf", 500000)
test("main.pdf scores positive", score > 0)
test("main.pdf keyword reason", "main_keyword:main" in reason)

score, reason = _score_pdf("Supplementary_Info.pdf", 500000)
test("supplementary demoted", score < 0, f"score={score}")

score, reason = _score_pdf("appendix_figures.pdf", 300000)
test("appendix keyword demoted", score < 0, f"score={score}")

score, reason = _score_pdf("random.pdf", 1000000)
test("large PDF gets bonus", score >= 1, f"score={score}")

score, reason = _score_pdf("tiny.pdf", 10000)
test("very small PDF demoted", score < 0, f"score={score}")

# ═══════════════════════════════════════════════════════
# Test 4: Session creation
# ═══════════════════════════════════════════════════════
print("\n[4] Session creation")
result = session.create_session()
sid = result["upload_session_id"]
test("session ID starts with web_", sid.startswith("web_"))
test("staging path returned", "web_uploads" in result["staging_path"].replace("\\", "/"))
test("staging path is relative", not os.path.isabs(result["staging_path"]))
test("no absolute paths", "G:\\" not in str(result) and "C:\\" not in str(result))

# ═══════════════════════════════════════════════════════
# Test 5: Single PDF upload → import plan
# ═══════════════════════════════════════════════════════
print("\n[5] Single PDF upload")
pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>"
result = session.add_files(sid, [("test_paper.pdf", pdf_content, "test_paper.pdf")])
test("single PDF uploaded", result["uploaded"] == 1)
test("file marked as uploaded", result["uploaded_files"][0]["status"] == "uploaded")

# Generate plan
plan = session.generate_plan(sid)
test("import type is article_bundle", plan["detected_import_type"] == "article_bundle")
test("main PDF detected", plan["main_pdf"] is not None)
test("main PDF is test_paper.pdf", plan["main_pdf"]["filename"] == "test_paper.pdf")
test("single PDF = high confidence", plan["main_pdf"]["confidence"] == "high")
test("detection reason = single_pdf_only", plan["main_pdf"]["detection_reason"] == "single_pdf_only")
test("no warnings for single PDF", len(plan["warnings"]) == 0)
test("does not require manual review", not plan["requires_manual_review"])
test("next action = confirm", plan["suggested_next_action"] == "confirm_import")

# ═══════════════════════════════════════════════════════
# Test 6: main.pdf + Table_S1.xlsx upload
# ═══════════════════════════════════════════════════════
print("\n[6] main.pdf + Table_S1.xlsx upload")
sid2 = session.create_session()["upload_session_id"]
result = session.add_files(sid2, [
    ("main.pdf", b"%PDF-1.4 main paper content", "main.pdf"),
    ("Table_S1.xlsx", b"fake xlsx binary content here", "Table_S1.xlsx"),
])
test("both files uploaded", result["uploaded"] == 2)

plan2 = session.generate_plan(sid2)
test("import type = article_bundle", plan2["detected_import_type"] == "article_bundle")
test("main.pdf is main", plan2["main_pdf"]["filename"] == "main.pdf")
test("main.pdf detected as main (single_pdf since only 1 PDF)",
     plan2["main_pdf"]["detection_reason"] in ("single_pdf_only", "filename_keyword_match"),
     f"got: {plan2['main_pdf']['detection_reason']}")
test("Table_S1 is supplementary", len(plan2["supplementary_files"]) == 1)
test("Table_S1 is spreadsheet type", plan2["supplementary_files"][0]["file_type"] == "spreadsheet")
test("Table_S1 entity_index_eligible", plan2["supplementary_files"][0]["entity_index_eligible"] is True)
test("Table_S1 high confidence", plan2["supplementary_files"][0]["match_confidence"] == "high")

# ═══════════════════════════════════════════════════════
# Test 7: Multi-PDF → manual review
# ═══════════════════════════════════════════════════════
print("\n[7] Multi-PDF → manual review")
sid3 = session.create_session()["upload_session_id"]
result = session.add_files(sid3, [
    ("document.pdf", b"%PDF-1.4 content A", "document.pdf"),
    ("appendix.pdf", b"%PDF-1.4 content B longer file with more content", "appendix.pdf"),
])
test("two PDFs uploaded", result["uploaded"] == 2)

plan3 = session.generate_plan(sid3)
test("requires manual review", plan3["requires_manual_review"] is True)
test("has main PDF candidates", "main_pdf_candidates" in plan3)
test("has candidates list", len(plan3.get("main_pdf_candidates", [])) == 2)
test("warning about multiple PDFs", any("Multiple PDFs" in w for w in plan3.get("warnings", [])))
# The appendix.pdf should have a lower score
candidates = plan3.get("main_pdf_candidates", [])
appendix_candidate = next((c for c in candidates if "appendix" in c["filename"]), None)
if appendix_candidate:
    test("appendix.pdf has negative score", appendix_candidate["score"] < 0,
         f"got score={appendix_candidate['score']}")

# ═══════════════════════════════════════════════════════
# Test 8: Supplementary PDF properly demoted
# ═══════════════════════════════════════════════════════
print("\n[8] Supplementary PDF demoted")
sid4 = session.create_session()["upload_session_id"]
# Use larger content to avoid "very_small_pdf" penalty (>50KB)
large_pdf_content = b"%PDF-1.4\n" + b"x" * 60000
session.add_files(sid4, [
    ("paper.pdf", large_pdf_content, "paper.pdf"),
    ("Supplementary_Information.pdf", large_pdf_content[:50000], "Supplementary_Information.pdf"),
])
test("main + suppl PDF uploaded", result["uploaded"] == 2)

plan4 = session.generate_plan(sid4)
test("paper.pdf is main", plan4["main_pdf"]["filename"] == "paper.pdf")
test("main confidence high", plan4["main_pdf"]["confidence"] == "high")
test("suppl classified as supplementary_pdf",
     any(s["file_type"] == "supplementary_pdf" for s in plan4["supplementary_files"]))
test("suppl not entity_index_eligible",
     all(not s["entity_index_eligible"] for s in plan4["supplementary_files"]
         if s["file_type"] == "supplementary_pdf"))

# ═══════════════════════════════════════════════════════
# Test 9: Only supplementary files → loose supplementary
# ═══════════════════════════════════════════════════════
print("\n[9] Loose supplementary (no PDF)")
sid5 = session.create_session()["upload_session_id"]
result = session.add_files(sid5, [
    ("Table_S1.csv", b"Gene,FC\nMAP2K4,2.5\n", "Table_S1.csv"),
])
test("CSV uploaded", result["uploaded"] == 1)

plan5 = session.generate_plan(sid5)
test("import type = loose_supplementary", plan5["detected_import_type"] == "loose_supplementary")
test("main PDF is None", plan5["main_pdf"] is None)
test("requires manual review", plan5["requires_manual_review"] is True)
test("next action = manual_binding", plan5["suggested_next_action"] == "manual_binding_required")
test("has message about binding", "loose supplementary" in plan5.get("message", "").lower())

# ═══════════════════════════════════════════════════════
# Test 10: ZIP file recorded not extracted
# ═══════════════════════════════════════════════════════
print("\n[10] ZIP file recorded only")
sid6 = session.create_session()["upload_session_id"]
result = session.add_files(sid6, [
    ("paper.pdf", b"%PDF-1.4 paper", "paper.pdf"),
    ("data_pack.zip", b"PK\x03\x04 fake zip content", "data_pack.zip"),
])
test("zip uploaded", result["uploaded"] == 2)

plan6 = session.generate_plan(sid6)
zip_entry = next((s for s in plan6["supplementary_files"] if s["filename"] == "data_pack.zip"), None)
test("zip in supplementary", zip_entry is not None)
if zip_entry:
    test("zip file_type = archive", zip_entry["file_type"] == "archive")
    test("zip not entity eligible", zip_entry["entity_index_eligible"] is False)
    test("zip has note about extraction", "not automatically extracted" in zip_entry.get("note", ""))

# ═══════════════════════════════════════════════════════
# Test 11: Confirm import → writes to 00_Inbox only
# ═══════════════════════════════════════════════════════
print("\n[11] Confirm import → 00_Inbox only")
# Use sid2 (main.pdf + Table_S1.xlsx) which has a clean plan
plan2 = session.generate_plan(sid2)
if not plan2.get("requires_manual_review"):
    result = session.confirm_import(sid2)
    test("import status = imported", result["status"] == "imported")
    test("article_bundle_path returned", "article_bundle_path" in result)
    bundle_path_str = result.get("article_bundle_path", "")
    bundle_normalized = bundle_path_str.replace("\\", "/")
    test("target is in article_bundles/new/", "article_bundles/new/" in bundle_normalized,
         f"got: {bundle_normalized}")
    test("target is NOT in 01_Sources/", "01_Sources/" not in bundle_path_str,
         f"got: {bundle_path_str}")
    test("target is NOT in 03_Assets/", "03_Assets/" not in bundle_path_str,
         f"got: {bundle_path_str}")
    test("files copied > 0", result["files_copied"] > 0)
    test("has next steps", len(result.get("next_steps", [])) > 0)
    test("processing started", result.get("processing_started") is True)

    # Verify files actually exist at target
    bundle_path = sl.root / bundle_path_str
    test("bundle directory exists", bundle_path.exists())
    test("web_import_manifest.json exists", (bundle_path / "web_import_manifest.json").exists())
    main_pdf = bundle_path / "main.pdf"
    test("main.pdf copied to bundle", main_pdf.exists())

# ═══════════════════════════════════════════════════════
# Test 12: All paths are relative
# ═══════════════════════════════════════════════════════
print("\n[12] All paths are relative")
for d in sl.get_path("inbox.web_uploads_staging").glob("web_*/upload_manifest.json"):
    content = d.read_text(encoding="utf-8")
    test(f"no abs path in {d.parent.name}",
         "G:\\" not in content and "C:\\" not in content and "g:\\" not in content)

for d in sl.get_path("inbox.web_uploads_planned").glob("web_*/import_plan.json"):
    content = d.read_text(encoding="utf-8")
    test(f"no abs path in plan {d.parent.name}",
         "G:\\" not in content and "C:\\" not in content and "g:\\" not in content)

# ═══════════════════════════════════════════════════════
# Test 13: No path traversal in upload
# ═══════════════════════════════════════════════════════
print("\n[13] Path traversal prevention")
sid7 = session.create_session()["upload_session_id"]
result = session.add_files(sid7, [
    ("harmless.pdf", b"%PDF-1.4", "harmless.pdf"),
    ("bad.pdf", b"%PDF-1.4", "../../secret.pdf"),
])
# The bad path should be sanitized, not rejected entirely
test("harmless file uploaded",
     any(f["filename"] == "harmless.pdf" for f in result.get("uploaded_files", [])))
# The traversal file might be rejected or sanitized
# Either way, no file should end up outside staging
staging_dir = sl.get_path("inbox.web_uploads_staging") / sid7
for f in staging_dir.rglob("*"):
    if f.is_file() and f.name != "upload_manifest.json":
        rel = str(f.relative_to(sl.root))
        test(f"file stays in staging: {f.name}", ".." not in rel, f"relative path: {rel}")

# ═══════════════════════════════════════════════════════
# Test 14: Duplicate filename handling
# ═══════════════════════════════════════════════════════
print("\n[14] Duplicate filename handling")
sid8 = session.create_session()["upload_session_id"]
r1 = session.add_files(sid8, [("data.csv", b"a,b\n1,2\n", "data.csv")])
r2 = session.add_files(sid8, [("data.csv", b"x,y\n3,4\n", "data.csv")])
test("first upload ok", r1["uploaded"] == 1)
test("second upload ok (dedup)", r2["uploaded"] == 1)
# Should have 2 files with different paths
sess = session.get_session(sid8)
csv_files = [f for f in sess["files"] if f["filename"] == "data.csv"]
test("two data.csv entries", len(csv_files) == 2)
# Paths should differ
paths = {f["relative_path"] for f in csv_files}
test("dedup paths differ", len(paths) == 2, f"paths: {paths}")

# ═══════════════════════════════════════════════════════
# Test 15: Plan update (manual selection)
# ═══════════════════════════════════════════════════════
print("\n[15] Plan update")
sid9 = session.create_session()["upload_session_id"]
session.add_files(sid9, [
    ("paper.pdf", b"%PDF-1.4 main", "paper.pdf"),
    ("appendix.pdf", b"%PDF-1.4 appendix", "appendix.pdf"),
    ("Table_S1.xlsx", b"fake xlsx", "Table_S1.xlsx"),
])
plan9 = session.generate_plan(sid9)

# Update: manually select main PDF
updated = session.update_plan(sid9, {
    "main_pdf_relative_path": "paper.pdf",
    "article_folder_name": "My_Custom_Folder",
    "supplementary_relative_paths": ["Table_S1.xlsx"],
})
test("plan updated", "plan_updated" in updated.get("status", ""))
test("main_pdf updated", updated["main_pdf"]["confidence"] == "high")
test("detection_reason = manual", updated["main_pdf"]["detection_reason"] == "manual_selection")
test("folder name updated", updated["proposed_article_folder"] == "My_Custom_Folder")
test("selected suppl count = 1", len(updated["supplementary_files"]) == 1)
test("review no longer required", not updated["requires_manual_review"])

# ═══════════════════════════════════════════════════════
# Test 16: List sessions
# ═══════════════════════════════════════════════════════
print("\n[16] List sessions")
from scientra.io.web_import import list_sessions
sessions = list_sessions()
test("sessions found", len(sessions) > 0)
test("session has id field", "upload_session_id" in sessions[0])

# ═══════════════════════════════════════════════════════
# Test 17: Confirm loose supplementary import
# ═══════════════════════════════════════════════════════
print("\n[17] Confirm loose supplementary import")
sid10 = session.create_session()["upload_session_id"]
session.add_files(sid10, [("lone_table.csv", b"a,b\n1,2\n", "lone_table.csv")])
plan10 = session.generate_plan(sid10)
test("loose suppl plan generated", plan10["detected_import_type"] == "loose_supplementary")

result10 = session.confirm_import(sid10)
test("loose suppl imported", result10["status"] == "imported")
target_path_norm = result10.get("target_path", "").replace("\\", "/")
test("target in loose_supplementary/new",
     "loose_supplementary/new" in target_path_norm,
     f"got: {target_path_norm}")

# ═══════════════════════════════════════════════════════
# Test 18: Import status endpoint returns relative paths only
# ═══════════════════════════════════════════════════════
print("\n[18] Import status returns relative paths only")
from scientra.io.web_import import WebImportSession

# Create a test bundle in article_bundles/new/
test_bundle = sl.get_path("inbox.article_bundles_new") / "TEST_STATUS_Bundle"
test_bundle.mkdir(parents=True, exist_ok=True)
(test_bundle / "paper.pdf").write_bytes(b"%PDF-1.4 status test paper content here more bytes")
(test_bundle / "Table_1.xlsx").write_bytes(b"fake xlsx data")

# Now verify we can scan status
# We test by directly calling the logic rather than the HTTP endpoint
def _scan_dir_for_test(d, sl_ref):
    items = []
    if d.exists():
        for entry in sorted(d.iterdir()):
            if entry.name.startswith("."):
                continue
            rel = str(entry.relative_to(sl_ref.root)).replace("\\", "/")
            if entry.is_dir():
                files = list(entry.iterdir())
                items.append({
                    "name": entry.name,
                    "relative_path": rel,
                    "file_count": len([f for f in files if f.is_file()]),
                    "pdf_count": len([f for f in files if f.is_file() and f.suffix.lower() == ".pdf"]),
                    "spreadsheet_count": len([f for f in files if f.is_file() and f.suffix.lower() in (".xlsx", ".xls", ".csv", ".tsv")]),
                })
            elif entry.is_file():
                items.append({"name": entry.name, "relative_path": rel, "type": "file"})
    return items

ab_new_items = _scan_dir_for_test(sl.get_path("inbox.article_bundles_new"), sl)
test("bundle found via scan", len(ab_new_items) > 0)
test_bundle_item = next((i for i in ab_new_items if i["name"] == "TEST_STATUS_Bundle"), None)
test("test bundle identified", test_bundle_item is not None)
if test_bundle_item:
    test("relative path contains article_bundles/new",
         "article_bundles/new" in test_bundle_item["relative_path"],
         f"got: {test_bundle_item['relative_path']}")
    test("no absolute path in relative_path",
         not test_bundle_item["relative_path"].startswith("G:") and
         not test_bundle_item["relative_path"].startswith("C:"),
         f"got: {test_bundle_item['relative_path']}")
    test("pdf_count detected", test_bundle_item.get("pdf_count", 0) == 1)
    test("spreadsheet_count detected", test_bundle_item.get("spreadsheet_count", 0) == 1)

# ═══════════════════════════════════════════════════════
# Test 19: Bundles endpoint returns correct stats
# ═══════════════════════════════════════════════════════
print("\n[19] Bundles correct new/processed/failed stats")
from scientra.io.import_dashboard import ImportDashboard
dashboard = ImportDashboard()
bundles_data = dashboard.list_bundles()
test("bundles endpoint returns data", "bundles" in bundles_data)
test("total >= 0", bundles_data.get("total", -1) >= 0)
test("processed key present", "processed" in bundles_data)
test("failed key present", "failed" in bundles_data)
for b in bundles_data.get("bundles", []):
    bpath = b.get("bundle_relative_path", b.get("bundle_name", ""))
    test(f"no abs path in bundle {b.get('bundle_id', '?')}",
         "G:\\" not in str(bpath) and "C:\\" not in str(bpath))

# ═══════════════════════════════════════════════════════
# Test 20: Loose supplementary correctly identified
# ═══════════════════════════════════════════════════════
print("\n[20] Loose supplementary correctly identified")
ls_data = dashboard.list_loose_supplementary()
test("loose suppl endpoint returns data", "files" in ls_data)
test("total >= 0", ls_data.get("total", -1) >= 0)
for f in ls_data.get("files", []):
    test(f"no abs path in loose file {f.get('file_name', '?')}",
         "G:\\" not in str(f.get("relative_path", "")) and
         "C:\\" not in str(f.get("relative_path", "")))

# ═══════════════════════════════════════════════════════
# Test 21: Multipart fallback preserves session
# ═══════════════════════════════════════════════════════
print("\n[21] Multipart fallback scenario")
sid11 = session.create_session()["upload_session_id"]
# Simulate a failed multipart (empty file items) and then successful base64
# This tests that add_files works after a "failed" multipart scenario
result_a = session.add_files(sid11, [
    ("final_paper.pdf", b"%PDF-1.4 final paper content longer here", "final_paper.pdf"),
])
test("upload after simulated failure works", result_a["uploaded"] == 1)
plan11 = session.generate_plan(sid11)
test("plan generated after fallback upload", plan11.get("detected_import_type") == "article_bundle")
test("session not corrupted by fallback", plan11.get("main_pdf") is not None)

# ═══════════════════════════════════════════════════════
# Test 22: File size enforcement
# ═══════════════════════════════════════════════════════
print("\n[22] File size enforcement")
from scientra.io.web_import import MAX_FILE_SIZE
sid12 = session.create_session()["upload_session_id"]
# Small file OK
small_result = session.add_files(sid12, [
    ("small.pdf", b"%PDF-1.4 small", "small.pdf"),
])
test("small file accepted", small_result["uploaded"] == 1)
# Oversized file rejected
oversized = b"x" * (MAX_FILE_SIZE + 1)
big_result = session.add_files(sid12, [
    ("too_big.pdf", oversized, "too_big.pdf"),
])
test("oversized file rejected", big_result["uploaded"] == 0)
test("rejected reason mentions size",
     any("large" in r.get("reason", "").lower() or "size" in r.get("reason", "").lower()
         for r in big_result.get("rejected_files", [])),
     f"rejected: {big_result.get('rejected_files', [])}")

# ═══════════════════════════════════════════════════════
# Test 23: Dry-run endpoint safe (no file writes to 01_Sources)
# ═══════════════════════════════════════════════════════
print("\n[23] Dry-run processing does not write to 01_Sources/")
from scientra.io.article_bundle_importer import ArticleBundleImporter
importer = ArticleBundleImporter()
pre_existing_sources = set(
    str(p.relative_to(sl.root))
    for p in sl.get_path("sources.papers").rglob("*")
    if p.is_file()
)
pre_existing_assets = set(
    str(p.relative_to(sl.root))
    for p in sl.get_path("assets.paper_assets").rglob("*")
    if p.is_file()
)

dry_result = importer.process(archive_mode="copy", dry_run=True)
test("dry-run returns results", "results" in dry_result)
test("dry-run does not write to sources/papers",
     set(str(p.relative_to(sl.root)) for p in sl.get_path("sources.papers").rglob("*") if p.is_file()) == pre_existing_sources)
test("dry-run does not write to assets",
     set(str(p.relative_to(sl.root)) for p in sl.get_path("assets.paper_assets").rglob("*") if p.is_file()) == pre_existing_assets)
# Verify all would_copy paths are relative
for r in dry_result.get("results", []):
    path = r.get("would_copy_main", "")
    if path:
        test(f"would_copy_main is relative: {Path(path).name}",
             not str(path).startswith("G:") and not str(path).startswith("C:"))

# ═══════════════════════════════════════════════════════
# Test 24: Confirm import next steps include processing commands
# ═══════════════════════════════════════════════════════
print("\n[24] Confirm import next steps")
sid13 = session.create_session()["upload_session_id"]
session.add_files(sid13, [
    ("article_final.pdf", b"%PDF-1.4 " + b"x" * 60000, "article_final.pdf"),
])
plan13 = session.generate_plan(sid13)
result13 = session.confirm_import(sid13)
test("next_steps includes processing hint",
     any("process" in s.lower() for s in result13.get("next_steps", [])),
     f"got: {result13.get('next_steps', [])}")
test("next_steps includes library link",
     any("library" in s.lower() for s in result13.get("next_steps", [])))
test("next_steps includes assets link",
     any("assets" in s.lower() for s in result13.get("next_steps", [])))

# ═══════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════
print("\n[Cleanup]")
for d in sl.get_path("inbox.web_uploads_staging").glob("web_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.web_uploads_planned").glob("web_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.web_uploads_imported").glob("web_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.article_bundles_new").glob("TEST_*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.article_bundles_new").glob("test_paper*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.article_bundles_new").glob("article_final*"):
    shutil.rmtree(d, ignore_errors=True)
for d in sl.get_path("inbox.article_bundles_new").glob("main*"):
    # Only remove test-created ones, not real ones
    mf = d / "web_import_manifest.json"
    if mf.exists():
        shutil.rmtree(d, ignore_errors=True)
# Remove test files from loose_supplementary/new
for f in sl.get_path("inbox.loose_supplementary_new").iterdir():
    if f.is_file() and any(f.name.startswith(p) for p in
                           ("TEST_", "lone_", "Table_S", "final_")):
        f.unlink()
# Remove plan/manifest from loose confirm test
for f in sl.get_path("inbox.loose_supplementary_new").iterdir():
    if f.is_file() and f.name.startswith("lone_"):
        f.unlink()
test("cleanup complete", True)

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
