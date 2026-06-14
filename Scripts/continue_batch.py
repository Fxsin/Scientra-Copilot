"""Continue batch processing — pick up where it left off."""
import sys, json, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# API key must be set via environment: export DEEPSEEK_API_KEY="sk-..."
# Or configured in Config/llm_config.yaml (gitignored)

from scientra.ai.llm_gateway import reload_config, get_config, save_config, LLMConfig
reload_config()
original = get_config()

cfg = LLMConfig(
    enabled=True, provider=original.provider, model=original.model,
    api_key=original.api_key, base_url=original.base_url,
    temperature=original.temperature, max_tokens=original.max_tokens,
    enabled_tasks={
        "summary": True, "evidence_enrichment": True,
        "gap_extraction": True, "hypothesis_generation": True,
        "figure_interpretation": False, "table_interpretation": False,
        "supplementary_interpretation": False, "agent_chat": True,
    },
)
save_config(cfg)
reload_config()

evidence_dir = Path("03_Evidence")
all_papers = sorted(
    d.name for d in evidence_dir.iterdir()
    if d.is_dir() and (d / "evidence_chunks.json").exists()
)

# ── Step 1: Complete Summary V2 ──
print("=" * 60)
print("STEP 1: Complete Summary V2")
print("=" * 60)

sv2_dir = Path("03_Assets/ai/summary_v2")
sv2_done = set(f.stem for f in sv2_dir.glob("*.json")) if sv2_dir.exists() else set()
missing = [p for p in all_papers if p not in sv2_done]
print(f"Remaining: {len(missing)}")

if missing:
    from scientra.ai.summary_v2 import generate_summary_v2
    good, fail = 0, 0
    for i, pid in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] {pid[:60]}...", end=" ", flush=True)
        try:
            chunks_path = evidence_dir / pid / "evidence_chunks.json"
            chunks = []
            if chunks_path.exists():
                chunks = json.loads(chunks_path.read_text(encoding="utf-8")).get("chunks", [])[:15]
            text = ""
            sections_path = evidence_dir / pid / "sections.json"
            if sections_path.exists():
                sections = json.loads(sections_path.read_text(encoding="utf-8"))
                sd = sections.get("sections", {})
                if isinstance(sd, dict):
                    text = "\n\n".join(str(v) for v in sd.values())[:24000]
            result = generate_summary_v2(paper_id=pid, text=text, evidence_chunks=chunks)
            if result.get("status") == "generated":
                good += 1
                print("OK")
            else:
                fail += 1
                w = result.get("warnings", ["?"])
                print(f"FAIL: {w[0][:60]}" if w else "FAIL")
        except Exception as e:
            fail += 1
            print(f"ERROR: {e}")
    print(f"Summary V2: {good} ok, {fail} failed")

# ── Step 2: Evidence Enrichment ──
print("\n" + "=" * 60)
print("STEP 2: Evidence Enrichment")
print("=" * 60)

ee_dir = Path("03_Assets/ai/evidence_enrichment")
ee_done = set(f.stem for f in ee_dir.glob("*.json")) if ee_dir.exists() else set()
ee_missing = [p for p in all_papers if p not in ee_done]
print(f"Remaining: {len(ee_missing)}")

if ee_missing:
    from scientra.ai.evidence_enrichment import enrich_evidence_chunks
    good, fail = 0, 0
    for i, pid in enumerate(ee_missing, 1):
        print(f"[{i}/{len(ee_missing)}] {pid[:60]}...", end=" ", flush=True)
        try:
            result = enrich_evidence_chunks(paper_id=pid, batch_size=8, max_chunks=20)
            if result.get("status") == "enriched":
                good += 1
                print(f"OK ({result.get('enriched_chunks', 0)} chunks)")
            else:
                fail += 1
                print(f"FAIL: {result.get('error', result.get('reason', '?'))[:60]}")
        except Exception as e:
            fail += 1
            print(f"ERROR: {e}")
    print(f"Evidence Enrichment: {good} ok, {fail} failed")

# ── Step 3: Gap Extraction ──
print("\n" + "=" * 60)
print("STEP 3: Gap Extraction")
print("=" * 60)

gaps_dir = Path("03_Assets/ai/gaps")
gaps_done = set(f.stem for f in gaps_dir.glob("*.json")) if gaps_dir.exists() else set()
gaps_missing = [p for p in all_papers if p not in gaps_done]
print(f"Remaining: {len(gaps_missing)}")

if gaps_missing:
    from scientra.ai.gap_extraction import extract_research_gaps
    good, fail = 0, 0
    for i, pid in enumerate(gaps_missing, 1):
        print(f"[{i}/{len(gaps_missing)}] {pid[:60]}...", end=" ", flush=True)
        try:
            result = extract_research_gaps(paper_id=pid, max_gaps=6)
            if result.get("status") == "generated":
                good += 1
                g = len(result.get("gaps", []))
                print(f"OK ({g} gaps)")
            else:
                fail += 1
                print(f"FAIL: {result.get('warnings', ['?'])[0][:60]}")
        except Exception as e:
            fail += 1
            print(f"ERROR: {e}")
    print(f"Gap Extraction: {good} ok, {fail} failed")

# ── Step 4: Hypothesis Generation ──
print("\n" + "=" * 60)
print("STEP 4: Hypothesis Generation")
print("=" * 60)

hyp_dir = Path("03_Assets/ai/hypotheses")
hyp_done = set(f.stem for f in hyp_dir.glob("*.json")) if hyp_dir.exists() else set()
hyp_missing = [p for p in all_papers if p not in hyp_done]
print(f"Remaining: {len(hyp_missing)}")

if hyp_missing:
    from scientra.ai.hypothesis_generation import generate_hypotheses
    good, fail = 0, 0
    for i, pid in enumerate(hyp_missing, 1):
        print(f"[{i}/{len(hyp_missing)}] {pid[:60]}...", end=" ", flush=True)
        try:
            result = generate_hypotheses(paper_id=pid, max_hypotheses=6)
            if result.get("status") == "generated":
                good += 1
                h = len(result.get("hypotheses", []))
                print(f"OK ({h} hypotheses)")
            else:
                fail += 1
                s = result.get("status", "?")
                w = result.get("warnings", ["?"])
                print(f"FAIL({s}): {w[0][:60]}")
        except Exception as e:
            fail += 1
            print(f"ERROR: {e}")
    print(f"Hypothesis Generation: {good} ok, {fail} failed")

# ── Final counts ──
print("\n" + "=" * 60)
print("FINAL COUNTS")
print("=" * 60)
for d in ["summary_v2", "evidence_enrichment", "gaps", "hypotheses"]:
    p = Path(f"03_Assets/ai/{d}")
    count = len(list(p.glob("*.json"))) if p.exists() else 0
    print(f"  {d}: {count} / {len(all_papers)}")

# Usage
from scientra.ai.cost_tracker import get_usage_summary
u = get_usage_summary(days=1)
print(f"\n  AI calls today: {u['total_calls']}")
print(f"  Total cost: ${u['total_cost']:.4f}")

save_config(original)
reload_config()
print("\nDone. Config restored.")
