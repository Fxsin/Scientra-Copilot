"""Test script for Phase 1: Figure + Caption Extraction"""
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
print("Phase 1: Figure + Caption Extraction Tests")
print("=" * 60)

FIG_DIR = root / "06_PDF_DataAssets" / "02_figures"
VALID_TYPES = {"gel_or_blot","microscopy","bioassay_curve","dose_response","binding_assay",
               "phylogeny","structure_model","heatmap","bar_chart","line_chart",
               "sequence_alignment","domain_structure","workflow_model","table_like","unknown"}

# Find a paper with figures
fig_dirs = sorted([d for d in FIG_DIR.iterdir() if d.is_dir() and (d / "figures.json").exists()]) if FIG_DIR.exists() else []

print(f"\n[1] Figure extraction coverage: {len(fig_dirs)} papers with figures.json")
test("at least 1 paper", len(fig_dirs) >= 1)
if not fig_dirs:
    print("  No figures found — skipping detailed checks")
    sys.exit(1)

# Test first paper
pid = fig_dirs[0].name
figs = json.loads((FIG_DIR / pid / "figures.json").read_text(encoding="utf-8"))
print(f"\n[2] Paper: {pid[:50]}... — {len(figs)} figures")

for i, f in enumerate(figs[:5]):
    print(f"\n  Figure {i+1}:")
    print(f"    label: {f.get('figure_label','?')}")
    print(f"    number: {f.get('figure_number','?')}")
    print(f"    type: {f.get('figure_type','?')}")
    print(f"    caption_len: {len(f.get('caption',''))}")
    print(f"    refs: {len(f.get('reference_sentences',[]))}")
    print(f"    evidence_ids: {len(f.get('linked_evidence_ids',[]))}")
    print(f"    confidence: {f.get('confidence','?')}")

    test(f"  figure_label present", bool(f.get("figure_label")))
    test(f"  source_text present", bool(f.get("source_text","").strip()))
    test(f"  confidence valid", f.get("confidence") in ("high","medium","low","unknown"))
    test(f"  figure_type valid", f.get("figure_type","unknown") in VALID_TYPES,
         f"got: {f.get('figure_type')}")
    test(f"  reference_sentences is list", isinstance(f.get("reference_sentences"), list))

# Test 3: Overall stats
total_figs = 0
with_caption = 0
with_refs = 0
type_dist = {}
for d in fig_dirs:
    try:
        figs = json.loads((d / "figures.json").read_text(encoding="utf-8"))
        total_figs += len(figs)
        for f in figs:
            if f.get("caption","").strip(): with_caption += 1
            if f.get("reference_sentences"): with_refs += 1
            ft = f.get("figure_type","unknown")
            type_dist[ft] = type_dist.get(ft,0) + 1
    except: pass

print(f"\n[3] Full library stats:")
print(f"    Total papers: {len(fig_dirs)}")
print(f"    Total figures: {total_figs}")
print(f"    With captions: {with_caption} ({with_caption/max(total_figs,1)*100:.0f}%)")
print(f"    With references: {with_refs} ({with_refs/max(total_figs,1)*100:.0f}%)")
print(f"    Figure types: {type_dist}")

test("total_figures > 0", total_figs > 0)
test("some have references", with_refs > 0)

print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
