"""Test Storage Layout v3 read routing with legacy fallback."""
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
print("Storage Layout v3 — Read Routing Tests")
print("=" * 60)

from scientra.io.storage_layout import StorageLayout

sl = StorageLayout()
sl.load()

# Test 1: Figure assets read routing
print("\n[1] Figure assets read routing")
figures = sl.resolve_path("assets.figure_assets", "old_pdf_data_assets")
if not (figures / "02_figures").exists():
    # Check if new path has data, otherwise verify legacy
    legacy_figures = root / "06_PDF_DataAssets" / "02_figures"
    test("legacy figure assets accessible", legacy_figures.exists(),
         f"legacy path: {legacy_figures}")
    fig_dirs = list(legacy_figures.iterdir()) if legacy_figures.exists() else []
    test("legacy has figure data", len(fig_dirs) > 0, f"found {len(fig_dirs)} papers")
else:
    test("new figure assets path accessible", True)
print(f"    Resolved: {figures}")

# Test 2: Table assets read routing
print("\n[2] Table assets read routing")
tables = sl.resolve_path("assets.table_assets", "old_pdf_data_assets")
legacy_tables = root / "06_PDF_DataAssets" / "03_tables"
tbl_dirs = list(legacy_tables.iterdir()) if legacy_tables.exists() else []
test("table assets data accessible", len(tbl_dirs) > 0, f"found {len(tbl_dirs)} papers")
print(f"    Papers with tables: {len(tbl_dirs)}")

# Test 3: Supplementary assets read routing
print("\n[3] Supplementary assets read routing")
suppl = sl.resolve_path("assets.supplementary_assets", "old_pdf_data_assets")
legacy_suppl = root / "06_PDF_DataAssets" / "08_supplementary_links"
test("supplementary links accessible", legacy_suppl.exists())
suppl_papers = list(legacy_suppl.iterdir()) if legacy_suppl.exists() else []
test("has supplementary link data", len(suppl_papers) > 0)
print(f"    Papers with supplementary links: {len(suppl_papers)}")

# Test 4: Gene evidence read routing
print("\n[4] Gene evidence read routing")
gene_ev = sl.resolve_path("corpus.data.gene_evidence", "old_pdf_data_assets")
legacy_entities = root / "06_PDF_DataAssets" / "09_supplementary_entities"
if legacy_entities.exists():
    ent_dirs = list(legacy_entities.iterdir())
    test("gene evidence accessible", len(ent_dirs) > 0, f"found {len(ent_dirs)} papers")
else:
    test("gene evidence path exists (may be empty)", sl.get_path("corpus.data.gene_evidence").exists())

# Test 5: Cross-study read routing
print("\n[5] Cross-study read routing")
cross = sl.resolve_path("corpus.data.cross_study", "old_pdf_data_assets")
legacy_comp = root / "06_PDF_DataAssets" / "10_entity_comparisons"
test("cross-study path accessible", legacy_comp.exists() or sl.get_path("corpus.data.cross_study").exists())

# Test 6: Vector index read routing
print("\n[6] Vector index (LanceDB) read routing")
vect = sl.resolve_path("index.vector.lancedb", "old_vector_db")
legacy_vect = root / "04_VectorDB"
test("vector DB path accessible", vect.exists() or legacy_vect.exists())
# Try actual LanceDB read
import lancedb
try:
    db_path = vect / "lancedb" if (vect / "lancedb").exists() else legacy_vect / "lancedb"
    if db_path.exists():
        db = lancedb.connect(str(db_path))
        tables = db.table_names()
        test(f"LanceDB has tables: {len(tables)}", len(tables) > 0, f"tables: {tables}")
    else:
        test("LanceDB dir not found at resolved path", False, f"checked: {db_path}")
except Exception as e:
    test("LanceDB read error", False, str(e)[:100])

# Test 7: API /query/assets still works
print("\n[7] API /query/assets still works")
try:
    from scientra.sdk import query_assets
    r = query_assets("protein expression", top_k=3)
    test("query_assets returns results", r["count"] > 0, f"count={r['count']}")
except Exception as e:
    test("query_assets failed", False, str(e)[:100])

# Test 8: API /query/supplementary-entities still works
print("\n[8] API /query/supplementary-entities still works")
try:
    from scientra.sdk import query_supplementary_entities
    r = query_supplementary_entities("MAP2K4", entity_type="gene")
    test("entity query returns results", r["total"] > 0, f"total={r['total']}")
except Exception as e:
    test("entity query failed", False, str(e)[:100])

# Test 9: API /query/supplementary-entity-comparison still works
print("\n[9] API entity comparison still works")
try:
    from scientra.sdk import query_supplementary_entity_comparison
    r = query_supplementary_entity_comparison("MAP2K4")
    test("comparison returns results", r["total_matches"] > 0, f"matches={r['total_matches']}")
except Exception as e:
    test("comparison failed", False, str(e)[:100])

# Test 10: /v1/agent/ask still works
print("\n[10] /v1/agent/ask still works")
try:
    from scientra.agent.literature_agent import LiteratureAgent
    agent = LiteratureAgent()
    r = agent.ask(question="Is MAP2K4 present in supplementary tables?", use_llm=False)
    test("agent returns answer", len(r.answer) > 50)
    test("agent intent correct", r.intent == "supplementary_entity_query",
         f"got: {r.intent}")
except Exception as e:
    test("agent failed", False, str(e)[:100])

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
