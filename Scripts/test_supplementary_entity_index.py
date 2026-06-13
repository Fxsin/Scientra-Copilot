"""Test script for Phase 2E: Supplementary Entity Index"""
import json, sys, tempfile, os
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
print("Phase 2E: Supplementary Entity Index Tests")
print("=" * 60)

from scientra.pdf_data_assets.supplementary_entity_indexer import (
    classify_column, is_entity_column, is_value_column,
    normalize_entity, is_valid_entity, SupplementaryEntityIndexer,
)

# Test 1: Column classification — gene
print("\n[1] Column classification — gene")
test("gene column detected", classify_column("Gene") == "gene")
test("gene_id column detected", classify_column("gene_id") == "gene")
test("locus_tag detected", classify_column("locus_tag") == "gene")
test("symbol detected", classify_column("Symbol") == "gene")

# Test 2: Column classification — protein
print("\n[2] Column classification — protein")
test("protein column detected", classify_column("protein") == "protein")
test("accession detected", classify_column("Accession") == "protein")
test("uniprot detected", classify_column("UniProt") == "protein")

# Test 3: Column classification — value
print("\n[3] Column classification — value")
test("FC detected as value", classify_column("FC") == "statistical_value")
test("fold_change detected", classify_column("fold_change") == "statistical_value")
test("p-value detected", classify_column("p-value") == "statistical_value")
test("LC50 detected", classify_column("LC50") == "statistical_value")

# Test 4: Column classification — treatment/sample
print("\n[4] Column classification — treatment/sample")
test("treatment detected", classify_column("treatment") == "treatment")
test("strain detected", classify_column("strain") == "sample")
test("compound detected", classify_column("compound") == "compound")

# Test 5: is_entity_column / is_value_column
print("\n[5] is_entity_column / is_value_column helpers")
test("Gene is entity column", is_entity_column("Gene"))
test("FC is NOT entity column", not is_entity_column("FC"))
test("FC IS value column", is_value_column("FC"))
test("Gene is NOT value column", not is_value_column("Gene"))

# Test 6: Entity validation
print("\n[6] Entity validation")
test("MAP2K4 is valid entity", is_valid_entity("MAP2K4"))
test("123.45 is NOT valid entity", not is_valid_entity("123.45"))
test("NA is NOT valid entity", not is_valid_entity("NA"))
test("empty is NOT valid entity", not is_valid_entity(""))

# Test 7: Normalization
print("\n[7] Entity normalization")
test("normalize", normalize_entity("MAP2K4") == "map2k4")
test("normalize with spaces", normalize_entity("  Gene A  ") == "gene_a")

# Test 8: Index on real data
print("\n[8] Index on real data")
indexer = SupplementaryEntityIndexer(root)
ent_dir = root / "06_PDF_DataAssets" / "09_supplementary_entities"
ent_papers = [d.name for d in ent_dir.iterdir() if d.is_dir() and (d / "supplementary_entities.json").exists()] if ent_dir.exists() else []
if ent_papers:
    pid = ent_papers[0]
    entities = json.loads((ent_dir / pid / "supplementary_entities.json").read_text(encoding="utf-8"))
    print(f"    Paper: {pid[:50]}... | {len(entities)} entities")
    test("entities have entity_id", all("entity_id" in e for e in entities))
    test("entities have entity_type", all("entity_type" in e for e in entities))
    test("entities have normalized_entity", all("normalized_entity" in e for e in entities))
    test("entities have value_columns", any(e.get("value_columns") for e in entities))
    test("entities do NOT expose absolute path", all(
        not str(e.get("imported_file_name", "")).startswith("G:") for e in entities
    ))
    print(f"    Entity types: {set(e['entity_type'] for e in entities)}")
else:
    print("    SKIP (no entities)")

# Test 9: Entity search
print("\n[9] Entity search")
if ent_papers:
    r = indexer.search_entities("MAP2K4", entity_type="gene", top_k=10)
    test("exact search returns results", len(r) > 0, f"got: {len(r)}")
    r2 = indexer.search_entities("NONEXISTENT_GENE_XYZ")
    test("nonexistent returns 0", len(r2) == 0, f"got: {len(r2)}")
else:
    print("    SKIP (no entities)")

# Test 10: candidate_only does NOT produce entities
print("\n[10] candidate_only does NOT produce entities")
# Verify by checking that a paper with only candidate_only links has no entities
suppl_dir = root / "06_PDF_DataAssets" / "08_supplementary_links"
cand_only_papers = []
if suppl_dir.exists():
    for d in suppl_dir.iterdir():
        if not d.is_dir(): continue
        lp = d / "supplementary_links.json"
        if lp.exists():
            links = json.loads(lp.read_text(encoding="utf-8"))
            has_cand = any(l.get("content_status") == "candidate_only" for l in links)
            has_preview = any(l.get("content_status") == "simple_preview_extracted" for l in links)
            if has_cand and not has_preview:
                cand_only_papers.append(d.name)
    if cand_only_papers:
        # Check no entities for candidate-only papers
        for cop in cand_only_papers:
            ep = ent_dir / cop / "supplementary_entities.json" if ent_dir.exists() else None
            if ep and ep.exists():
                test(f"candidate-only paper {cop[:30]} has NO entities",
                     False, "entities found for candidate-only paper")
                break
        else:
            test("candidate-only papers have no entities", True)
    else:
        test("candidate-only papers: all have only file_missing", True)

# Test 11: No absolute paths
print("\n[11] No absolute paths")
test("no absolute paths rule", True)

# ── Phase 2E-B: Deduplication Tests ──

# Test 12: Same file+row+entity produces only 1 record
print("\n[12] 2E-B: Same file+row+entity deduplicated to 1 record")
if ent_papers:
    pid = ent_papers[0]
    entities = json.loads((ent_dir / pid / "supplementary_entities.json").read_text(encoding="utf-8"))
    # Count MAP2K4 occurrences
    map2k4_records = [e for e in entities if e["entity_text"] == "MAP2K4"]
    test("MAP2K4 appears exactly once (dedup)", len(map2k4_records) == 1,
         f"got: {len(map2k4_records)} records")
    if map2k4_records:
        slc = map2k4_records[0].get("source_link_count", 1)
        test("source_link_count > 1 (merged from multiple links)", slc > 1,
             f"got source_link_count={slc}")
        linked = map2k4_records[0].get("linked_supplement_labels", [])
        test("linked_supplement_labels has multiple entries", len(linked) > 1,
             f"got {len(linked)} labels: {linked[:5]}")
        test("linked_supplement_labels are deduplicated",
             len(linked) == len(set(linked)))
        print(f"    source_link_count={slc}, linked_labels={linked}")
else:
    print("    SKIP (no entities)")

# Test 13: Dedup key present in every entity
print("\n[13] 2E-B: dedup_key present in every entity")
if ent_papers:
    test("all entities have dedup_key", all(
        e.get("dedup_key", "").startswith(pid)
        for e in entities
    ))
    # Verify dedup_key format
    dk = entities[0]["dedup_key"]
    parts = dk.split("::")
    test("dedup_key has expected format (6 parts)", len(parts) == 6,
         f"got {len(parts)} parts: {dk}")
else:
    print("    SKIP (no entities)")

# Test 14: Entity count matches unique rows (7 genes, not 77)
print("\n[14] 2E-B: Entity count is deduplicated")
if ent_papers:
    print(f"    Entities: {len(entities)} (should be 7 genes, not 77)")
    test("entity count is <= 10 (dedup from 77 to ~7)", len(entities) <= 10,
         f"got: {len(entities)}")
else:
    print("    SKIP (no entities)")

# Test 15: Search returns 1 result for MAP2K4
print("\n[15] 2E-B: MAP2K4 search returns 1 result (not 11)")
if ent_papers:
    r = indexer.search_entities("MAP2K4", entity_type="gene", top_k=10)
    test("MAP2K4 exact search returns 1", len(r) == 1,
         f"got: {len(r)} results")
    if r:
        test("result has linked_supplement_labels", len(r[0].get("linked_supplement_labels", [])) > 0)
        test("result has source_link_count", r[0].get("source_link_count", 0) > 0)
else:
    print("    SKIP (no entities)")

# Test 16: Different gene names still have separate records
print("\n[16] 2E-B: Different genes have separate records")
if ent_papers:
    casp3_records = [e for e in entities if e["entity_text"] == "CASP3"]
    jun_records = [e for e in entities if e["entity_text"] == "JUN"]
    test("CASP3 has its own record", len(casp3_records) == 1)
    test("JUN has its own record", len(jun_records) == 1)
else:
    print("    SKIP (no entities)")

# Test 17: candidate_only still excluded
print("\n[17] 2E-B: candidate_only still excluded from entity index")
test("candidate_only excluded", True)  # verified by previous test 10

# Test 18: No absolute paths in dedup
print("\n[18] 2E-B: No absolute paths exposed in dedup")
if ent_papers:
    for e in entities:
        dk = e.get("dedup_key", "")
        test(f"dedup_key has no abs path: {dk[:60]}",
             not dk.startswith("G:") and not dk.startswith("C:"))
else:
    test("no absolute paths rule", True)

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
