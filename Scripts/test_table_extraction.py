"""Test script for Phase 2A: Table Caption + Reference Extraction"""
import json, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition: passed += 1; print(f"  PASS: {name}")
    else: failed += 1; print(f"  FAIL: {name} — {detail}")

print("=" * 60)
print("Phase 2A: Table Caption + Reference Extraction Tests")
print("=" * 60)

TABLE_DIR = root / "06_PDF_DataAssets" / "03_tables"
VALID_TABLE_TYPES = {
    "toxicity_or_bioassay", "expression_or_production", "binding_or_affinity",
    "omics_data", "gene_or_protein_list", "primer_or_plasmid",
    "strain_or_sample", "statistics_or_model", "phenotype_summary",
    "sequence_or_domain", "supplementary_index", "unknown"
}
VALID_STRUCTURE_STATUSES = {
    "caption_only", "structure_pending", "simple_structure_extracted", "complex_structure_skipped"
}

# Find a paper with tables
tbl_dirs = sorted([d for d in TABLE_DIR.iterdir() if d.is_dir() and (d / "tables.json").exists()]) if TABLE_DIR.exists() else []

print(f"\n[1] Table extraction coverage: {len(tbl_dirs)} papers with tables.json")
test("at least 1 paper", len(tbl_dirs) >= 1)
if not tbl_dirs:
    print("  No tables found — skipping detailed checks")
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

# Test first paper
pid = tbl_dirs[0].name
tables = json.loads((TABLE_DIR / pid / "tables.json").read_text(encoding="utf-8"))
print(f"\n[2] Paper: {pid[:50]}... — {len(tables)} tables")

for i, t in enumerate(tables[:5]):
    print(f"\n  Table {i+1}:")
    print(f"    label: {t.get('table_label','?')}")
    print(f"    number: {t.get('table_number','?')}")
    print(f"    type: {t.get('table_type','?')}")
    print(f"    caption_len: {len(t.get('caption',''))}")
    print(f"    refs: {len(t.get('reference_sentences',[]))}")
    print(f"    evidence_ids: {len(t.get('linked_evidence_ids',[]))}")
    print(f"    confidence: {t.get('confidence','?')}")
    print(f"    structure_status: {t.get('structure_status','?')}")

    test(f"  table_label present", bool(t.get("table_label")))
    test(f"  source_text or caption present", bool(t.get("source_text","").strip() or t.get("caption","").strip()))
    test(f"  confidence valid", t.get("confidence") in ("high","medium","low","unknown"))
    test(f"  table_type valid", t.get("table_type","unknown") in VALID_TABLE_TYPES,
         f"got: {t.get('table_type')}")
    test(f"  reference_sentences is list", isinstance(t.get("reference_sentences"), list))
    test(f"  structure_status valid (Phase 2B)", t.get("structure_status","caption_only") in VALID_STRUCTURE_STATUSES,
         f"got: {t.get('structure_status')}")

# Test 3: Overall stats
total_tables = 0
with_caption = 0
with_refs = 0
type_dist = {}
caption_quality_dist = {}
caption_source_dist = {}
total_result_links = 0
total_claim_links = 0

for d in tbl_dirs:
    try:
        tables = json.loads((d / "tables.json").read_text(encoding="utf-8"))
        total_tables += len(tables)
        for t in tables:
            if t.get("caption","").strip(): with_caption += 1
            if t.get("reference_sentences"): with_refs += 1
            tt = t.get("table_type","unknown")
            type_dist[tt] = type_dist.get(tt,0) + 1
            cq = t.get("caption_quality","none")
            caption_quality_dist[cq] = caption_quality_dist.get(cq,0) + 1
            cs = t.get("caption_source","unknown")
            caption_source_dist[cs] = caption_source_dist.get(cs,0) + 1
            total_result_links += len(t.get("linked_result_assets", []))
            total_claim_links += len(t.get("linked_claim_assets", []))
    except: pass

print(f"\n[3] Full library stats:")
print(f"    Total papers: {len(tbl_dirs)}")
print(f"    Total tables: {total_tables}")
print(f"    With captions: {with_caption} ({with_caption/max(total_tables,1)*100:.0f}%)")
print(f"    With references: {with_refs} ({with_refs/max(total_tables,1)*100:.0f}%)")
print(f"    Table types: {type_dist}")
print(f"    Caption quality: {caption_quality_dist}")
print(f"    Caption source: {caption_source_dist}")
print(f"    Result links: {total_result_links}")
print(f"    Claim links: {total_claim_links}")

test("total_tables > 0", total_tables > 0)
test("some have captions", with_caption > 0)

# Test 4: tables.json structure
print(f"\n[4] tables.json structure validation")
first_tbl = tables[0]
test("has asset_id", "asset_id" in first_tbl)
test("has paper_id", "paper_id" in first_tbl)
test("has asset_type 'table'", first_tbl.get("asset_type") == "table")
test("has table_id", "table_id" in first_tbl)
test("has created_at", "created_at" in first_tbl)
test("has extraction_method", "extraction_method" in first_tbl)

# Test 4b: Phase 2B structure fields
print(f"\n[4b] Phase 2B structure fields")
test("has structure_status", "structure_status" in first_tbl)
test("has structured_columns", "structured_columns" in first_tbl)
test("has structured_rows", "structured_rows" in first_tbl)
test("has structure_confidence", "structure_confidence" in first_tbl)
test("has structure_extraction_method", "structure_extraction_method" in first_tbl)
test("has structure_notes", "structure_notes" in first_tbl)
# Validate structure_status
valid_statuses = {"caption_only", "structure_pending", "simple_structure_extracted", "complex_structure_skipped"}
test("structure_status valid", first_tbl.get("structure_status") in valid_statuses,
     f"got: {first_tbl.get('structure_status')}")
# If simple_structure_extracted, validate columns/rows
if first_tbl.get("structure_status") == "simple_structure_extracted":
    test("simple has columns >= 2", len(first_tbl.get("structured_columns", [])) >= 2)
    test("simple has rows >= 1", len(first_tbl.get("structured_rows", [])) >= 1)

# Test 5: Verify no crash on paper with no tables
print(f"\n[5] No-crash: paper with no tables")
from scientra.pdf_data_assets.table_asset_builder import TableAssetBuilder
builder = TableAssetBuilder(root)
result = builder.build("nonexistent_paper_id_12345")
test("returns empty list", result == [], f"got: {len(result) if result else 0}")

# Test 6: structure_status (Phase 2B)
print(f"\n[6] structure_status Phase 2B (caption_only / structure_pending / complex_structure_skipped / simple_structure_extracted)")
STATUSES_2B = {"caption_only", "structure_pending", "simple_structure_extracted", "complex_structure_skipped"}
all_valid_2b = all(
    t.get("structure_status", "caption_only") in STATUSES_2B
    for d in tbl_dirs
    for t in json.loads((d / "tables.json").read_text(encoding="utf-8"))
) if tbl_dirs else True
test("all structure_status values valid for Phase 2B", all_valid_2b)
# Count distribution
ss_count = {}
for d in tbl_dirs:
    for t in json.loads((d / "tables.json").read_text(encoding="utf-8")):
        ss = t.get("structure_status", "caption_only")
        ss_count[ss] = ss_count.get(ss, 0) + 1
print(f"    Distribution: {ss_count}")

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
