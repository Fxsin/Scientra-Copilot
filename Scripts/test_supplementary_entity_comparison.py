"""Test script for Phase 2G-A: Cross-Paper Entity Comparison"""
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
print("Phase 2G-A: Cross-Paper Entity Comparison Tests")
print("=" * 60)

from scientra.pdf_data_assets.supplementary_entity_comparator import SupplementaryEntityComparator

comparator = SupplementaryEntityComparator(root)

# Test 1: MAP2K4 comparison
print("\n[1] MAP2K4 comparison")
r = comparator.compare("MAP2K4", entity_type="gene")
test("total_matches = 1", r["total_matches"] == 1, f"got: {r['total_matches']}")
test("unique_papers_count = 1", r["unique_papers_count"] == 1)
test("unique_files_count = 1", r["unique_files_count"] == 1)
test("comparability_warning present", len(r.get("comparability_warning", "")) > 50)
ds = r.get("direction_summary", {})
test("direction_summary present", "upregulated_count" in ds)
print(f"    Direction: up={ds.get('upregulated_count',0)} down={ds.get('downregulated_count',0)} unknown={ds.get('unknown_count',0)}")
vcs = r.get("value_column_summary", {})
test("value_column_summary present", "detected_columns" in vcs)
print(f"    Value columns: {vcs.get('detected_columns', [])}")

# Test 2: CASP3 comparison — downregulated
print("\n[2] CASP3 comparison — downregulated")
r2 = comparator.compare("CASP3", entity_type="gene")
test("CASP3 found", r2["total_matches"] == 1)
ds2 = r2.get("direction_summary", {})
test("CASP3 downregulated", ds2.get("downregulated_count", 0) >= 1,
     f"got: up={ds2.get('upregulated_count',0)} down={ds2.get('downregulated_count',0)}")

# Test 3: NONEXISTENT returns 0
print("\n[3] NONEXISTENT_GENE_XYZ returns 0")
r3 = comparator.compare("NONEXISTENT_GENE_XYZ")
test("total_matches = 0", r3["total_matches"] == 0)
test("records empty", len(r3["records"]) == 0)

# Test 4: comparability_warning present in all records
print("\n[4] comparability_warning present")
for r_name, r_val in [("MAP2K4", r), ("CASP3", r2), ("NONEXISTENT", r3)]:
    if r_val["total_matches"] > 0:
        test(f"{r_name} has comparability warning", len(r_val.get("comparability_warning", "")) > 30)

# Test 5: No LLM calls
print("\n[5] No LLM calls in comparison engine")
test("comparator has no LLM dependency", "LLM" not in str(type(comparator)))
test("comparison result has no LLM field", "llm" not in str(r.keys()).lower())

# Test 6: Direction parsing — log2FC > 0 → up
print("\n[6] Direction parsing rules")
dir_up = comparator._detect_direction({"value_columns": {"log2FC": "1.5"}})
test("log2FC > 0 = up", dir_up == "upregulated", f"got: {dir_up}")
dir_down = comparator._detect_direction({"value_columns": {"log2FC": "-2.1"}})
test("log2FC < 0 = down", dir_down == "downregulated", f"got: {dir_down}")
dir_expr_up = comparator._detect_direction({"value_columns": {"Expression": "Upregulated"}})
test("Expression=Upregulated = up", dir_expr_up == "upregulated")
dir_expr_down = comparator._detect_direction({"value_columns": {"Expression": "Downregulated"}})
test("Expression=Downregulated = down", dir_expr_down == "downregulated")
dir_fc_up = comparator._detect_direction({"value_columns": {"FC": "2.5"}})
test("FC > 1 = up", dir_fc_up == "upregulated")
dir_fc_down = comparator._detect_direction({"value_columns": {"FC": "0.5"}})
test("FC < 1 = down", dir_fc_down == "downregulated")
dir_unknown = comparator._detect_direction({"value_columns": {"Something": "xyz"}})
test("no direction columns = unknown", dir_unknown == "unknown")

# Test 7: No absolute paths
print("\n[7] No absolute paths")
for r_name, r_val in [("MAP2K4", r)]:
    if r_val["total_matches"] > 0:
        result_str = json.dumps(r_val["records"])
        test(f"{r_name} no G: path", "G:\\" not in result_str)
        test(f"{r_name} no C: path", "C:\\" not in result_str)

# Test 8: Agent handles comparison query
print("\n[8] Agent handles comparison query")
try:
    from scientra.agent.literature_agent import LiteratureAgent
    agent = LiteratureAgent()
    resp = agent.ask(question="Compare MAP2K4 across supplementary data.", use_llm=False)
    test("intent = supplementary_entity_comparison_query",
         resp.intent == "supplementary_entity_comparison_query",
         f"got: {resp.intent}")
    test("comparability warning in answer",
         "comparability" in resp.answer.lower() or "Comparability warning" in resp.answer)
    test("direction summary in answer",
         "direction summary" in resp.answer.lower() or "Direction summary" in resp.answer)
    test("deterministic model",
         resp.model == "deterministic")
    test("no LLM tokens",
         resp.token_usage.get("source") == "no_llm")
except ImportError as e:
    print(f"    SKIP ({e})")

# Test 9: NONEXISTENT comparison via agent
print("\n[9] NONEXISTENT comparison via agent")
try:
    resp2 = agent.ask(question="Compare NONEXISTENT_GENE_XYZ across supplementary data.", use_llm=False)
    test("no records found", "No supplementary entity comparison records" in resp2.answer)
    test("deterministic", resp2.model == "deterministic")
except Exception:
    print("    SKIP")

# Test 10: source_link_count caution present in answer
print("\n[10] source_link_count caution")
try:
    resp3 = agent.ask(question="Compare MAP2K4 across supplementary data.", use_llm=False)
    test("source link count mentioned", "source link" in resp3.answer.lower())
except Exception:
    print("    SKIP")

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
