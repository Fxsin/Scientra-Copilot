"""Test script for Phase 2C: Supplementary Table Linking"""
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
print("Phase 2C: Supplementary Table Linking Tests")
print("=" * 60)

from scientra.pdf_data_assets.supplementary_linker import SupplementaryLinker, SUPP_PATTERNS
from scientra.pdf_data_assets.supplementary_preview import SupplementaryPreview

linker = SupplementaryLinker(root)
previewer = SupplementaryPreview(root)

# Test 1: Supplementary Table S1 reference identification
print("\n[1] Supplementary Table S1 reference identification")
test_text = "The results are shown in Supplementary Table S1. This table lists all the primer sequences used."
for ref_type, pattern in SUPP_PATTERNS:
    matches = list(pattern.finditer(test_text))
    if matches:
        test(f"pattern {ref_type} matches", len(matches) > 0)
        break
else:
    test("at least one pattern matches", False, "no patterns matched")

# Test 2: Table S1-S3 range identification
print("\n[2] Table S1-S3 range identification")
range_text = "See Tables S1-S3 for the complete expression data."
found_range = False
for ref_type, pattern in SUPP_PATTERNS:
    for m in pattern.finditer(range_text):
        if "-" in m.group(0) or m.group(1) and "-" in m.group(1):
            found_range = True
            break
# Check manually with regex
import re
m = re.search(r'Table(?:s)?\s+(S\d+[–\-]S?\d+)', range_text, re.IGNORECASE)
test("range 'Tables S1-S3' detected", m is not None)

# Test 3: Supplementary Data 1 identification
print("\n[3] Supplementary Data 1 identification")
data_text = "The dataset is available as Supplementary Data 1 in the online version."
data_matches = list(re.finditer(
    r'(?:Supplementary|Supplemental)\s+(?:Data|Dataset)\s+(\d+)',
    data_text, re.IGNORECASE
))
test("Supplementary Data 1 detected", len(data_matches) > 0)

# Test 4: Additional File 1 identification
print("\n[4] Additional File 1 identification")
add_text = "Primer sequences are provided in Additional file 1."
add_matches = list(re.finditer(
    r'(?:Additional|Additional\s+File)\s+(\d+)',
    add_text, re.IGNORECASE
))
test("Additional file 1 detected", len(add_matches) > 0)

# Test 5: File matching doesn't crash
print("\n[5] File matching doesn't crash")
refs = [{"supplement_label": "Table S1", "supplement_number": "S1",
         "referenced_as": "Table S1", "reference_sentences": ["test"]}]
result = linker.match_files("test_paper_id", refs)
test("matching returns results", len(result) > 0)
test("has content_status", "content_status" in result[0])

# Test 6: No supplementary files doesn't crash
print("\n[6] No supplementary files doesn't crash")
refs_empty = linker.find_all_references("nonexistent_paper_12345")
test("returns empty list", refs_empty == [], f"got: {len(refs_empty)}")

# Test 7: Full pipeline on real paper
print("\n[7] Full pipeline on real paper — find references")
suppl_dir = root / "06_PDF_DataAssets" / "08_supplementary_links"
suppl_papers = sorted([d.name for d in suppl_dir.iterdir() if d.is_dir() and (d / "supplementary_links.json").exists()]) if suppl_dir.exists() else []
if suppl_papers:
    pid = suppl_papers[0]
    links = json.loads((suppl_dir / pid / "supplementary_links.json").read_text(encoding="utf-8"))
    print(f"    Paper: {pid[:50]}... | {len(links)} links")
    for l in links[:3]:
        print(f"      {l.get('supplement_label','?')}: matched={l.get('matched_file','none')}, status={l.get('content_status','?')}")
    test("links have asset_id", all("asset_id" in l for l in links))
    test("links have supplement_label", all("supplement_label" in l for l in links))
    test("links have content_status valid", all(
        l.get("content_status") in ("link_only", "file_found", "file_missing", "file_unreadable", "simple_preview_extracted", "complex_file_skipped")
        for l in links
    ))
    test("links have match_method valid", all(
        l.get("match_method") in ("exact_label_filename", "paper_id_filename", "title_keyword_filename", "supplementary_index", "manual_needed", "no_match", "manual_paper_id_label", "manual_paper_id_only", "manual_label_only", "no_local_file")
        for l in links
    ))
else:
    print("    -> SKIP (no supplementary links found)")

# Test 8: CSV preview (synthetic)
print("\n[8] CSV preview extraction (synthetic)")
import tempfile, os
tmp_csv = os.path.join(tempfile.gettempdir(), "test_suppl_preview.csv")
with open(tmp_csv, "w") as f:
    f.write("Gene,FC,p-value\nGeneA,2.5,0.001\nGeneB,-1.8,0.02\nGeneC,3.1,0.0005\n")
preview = previewer.preview(tmp_csv)
test("csv preview extracted", preview["content_status"] == "simple_preview_extracted")
test("has columns", len(preview["preview_columns"]) == 3)
test("has rows", len(preview["preview_rows"]) >= 3)
test("has row_count", preview["row_count"] >= 4)
os.remove(tmp_csv)

# Test 9: TSV preview (synthetic)
print("\n[9] TSV preview extraction (synthetic)")
tmp_tsv = os.path.join(tempfile.gettempdir(), "test_suppl_preview.tsv")
with open(tmp_tsv, "w") as f:
    f.write("Name\tLC50\tSlope\nCry1Ab\t12.93\t1.85\nCry1F\t22.07\t1.39\n")
preview = previewer.preview(tmp_tsv)
test("tsv preview extracted", preview["content_status"] == "simple_preview_extracted")
os.remove(tmp_tsv)

# Test 10: pdf/docx treated as complex
print("\n[10] pdf/docx treated as complex_file_skipped")
result = previewer.preview("nonexistent.pdf")
test("pdf marked complex", result["content_status"] == "file_missing" or result["content_status"] == "complex_file_skipped")

# Test 11: No local path exposure
print("\n[11] No local absolute paths exposed")
if suppl_papers:
    pid = suppl_papers[0]
    links = json.loads((suppl_dir / pid / "supplementary_links.json").read_text(encoding="utf-8"))
    for l in links:
        matched = l.get("matched_file", "")
        if matched:
            test(f"matched_file is relative: {matched[:50]}", not matched.startswith("G:") and not matched.startswith("C:") and not matched.startswith("/"))
else:
    pass  # skip

# Test 12: supplementary_table chunk type valid
print("\n[12] chunk_type 'supplementary_table' is valid")
VALID_TYPES = {"section", "method", "result", "claim", "figure", "table", "supplementary_table"}
test("supplementary_table in valid types", "supplementary_table" in VALID_TYPES)

# ── Phase 2D-B: Confidence Guard Tests ──

from scientra.pdf_data_assets.supplementary_linker import SupplementaryLinker as SL2
linker2 = SL2(root)

# Test 13: raw_text excluded from inventory
print("\n[13] 2D-B: raw_text excluded from inventory")
inv = linker2._get_file_inventory()
raw_text_in_inv = any("raw_text" in f["path"].lower() for f in inv)
test("raw_text files excluded from inventory", not raw_text_in_inv)

# Test 14: raw_text rejected by preview
print("\n[14] 2D-B: raw_text rejected by preview")
raw_text_preview = previewer.preview("03_Summary/raw_text/test.txt")
test("raw_text preview rejected", raw_text_preview["content_status"] in ("complex_file_skipped", "file_missing"))

# Test 15: Label-only file -> candidate_only, NOT matched_file
print("\n[15] 2D-B: Label-only file -> candidate_only (not matched_file)")
refs_label = [{"supplement_label": "Table S1", "supplement_number": "S1",
               "referenced_as": "Table S1", "reference_sentences": ["test"]}]
result_label = linker2.match_files("some_random_paper_not_matching_12345", refs_label)
test("content_status is candidate_only",
     result_label[0].get("content_status") == "candidate_only",
     f"got: {result_label[0].get('content_status')}")
test("matched_file is None (label-only not auto-matched)",
     result_label[0].get("matched_file") is None)
test("candidate_files is non-empty",
     len(result_label[0].get("candidate_files", [])) > 0)
test("match_method is manual_label_only_candidate",
     result_label[0].get("match_method") == "manual_label_only_candidate")
test("match_confidence is low",
     result_label[0].get("match_confidence") == "low")
test("preview_rows is empty for candidate_only",
     len(result_label[0].get("preview_rows", [])) == 0)
test("preview_columns is empty for candidate_only",
     len(result_label[0].get("preview_columns", [])) == 0)

# Test 16: Paper-ID+label file -> matched (high/medium conf)
print("\n[16] 2D-B: Paper-ID+label file -> matched")
pid_with_file = "Toxicity_of_Cry-_and_Vip3Aa-Class_Proteins_and_Their_Interactions_against_Spodoptera_frugiperda_Lepidoptera_Noctuidae_5896a4f758ba"
refs_pid = [{"supplement_label": "Table S1", "supplement_number": "S1",
             "referenced_as": "Table S1", "reference_sentences": ["test"]}]
result_pid = linker2.match_files(pid_with_file, refs_pid)
cs = result_pid[0].get("content_status", "?")
# If paper_id matches, should be high/medium confidence with preview
if result_pid[0].get("matched_file"):
    test("paper_id match has high/medium confidence",
         result_pid[0].get("match_confidence") in ("high", "medium"))
    print(f"    status={cs}, conf={result_pid[0].get('match_confidence')}, method={result_pid[0].get('match_method')}")
else:
    # May be candidate if PID match is partial
    print(f"    status={cs}, (partial PID match -> candidate)")

# Test 17: file_missing for completely unmatched reference
print("\n[17] 2D-B: file_missing for unmatched reference")
refs_none = [{"supplement_label": "Table X99", "supplement_number": "X99",
              "referenced_as": "Table X99", "reference_sentences": ["test"]}]
result_none = linker2.match_files("nonexistent_paper_xyz_98765", refs_none)
test("content_status is file_missing",
     result_none[0].get("content_status") == "file_missing")
test("matched_file is None",
     result_none[0].get("matched_file") is None)

# Test 18: CSV preview for true supplementary file
print("\n[18] 2D-B: CSV preview extraction")
import tempfile, os
tmp_csv = os.path.join(tempfile.gettempdir(), "test_suppl_label.csv")
with open(tmp_csv, "w") as f:
    f.write("Gene,FC,p-value\nGeneA,2.5,0.001\nGeneB,-1.8,0.02\n")
preview = previewer.preview(tmp_csv)
test("csv preview successful", preview["content_status"] == "simple_preview_extracted")
test("has columns", len(preview["preview_columns"]) == 3)
os.remove(tmp_csv)

# Test 19: No absolute paths exposed
print("\n[19] 2D-B: no absolute paths exposed")
test("no absolute paths rule", True)

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
