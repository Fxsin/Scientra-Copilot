"""Phase 2.3 validation — Gap Extraction + Hypothesis Generation on 2 papers."""
import sys, json, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# API key from environment or Config/llm_config.yaml (gitignored)

from scientra.ai.llm_gateway import reload_config, get_config, save_config, LLMConfig
reload_config()

original = get_config()
cfg = LLMConfig(
    enabled=original.enabled, provider=original.provider, model=original.model,
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
paper_dirs = sorted(
    d.name for d in evidence_dir.iterdir()
    if d.is_dir() and (d / "evidence_chunks.json").exists()
)
test_papers = paper_dirs[:2]
print(f"Testing on {len(test_papers)} papers: {[p[:50]+'...' for p in test_papers]}")

# === GAP EXTRACTION ===
print("\n" + "=" * 60)
print("GAP EXTRACTION")
print("=" * 60)

from scientra.ai.gap_extraction import extract_research_gaps

gap_count = 0
for pid in test_papers:
    print(f'\n--- {pid[:70]}... ---')
    result = extract_research_gaps(paper_id=pid, max_gaps=6)
    status = result.get("status", "unknown")
    print(f"  Status: {status}")
    if result.get("gaps"):
        g_list = result["gaps"]
        print(f"  Gaps found: {len(g_list)}")
        for g in g_list[:3]:
            gtype = g.get("gap_type", "?")
            stmt = g.get("gap_statement", "")[:130]
            print(f"    [{gtype}] {stmt}")
            why = g.get("why_it_matters", "")
            if why:
                print(f"      Why: {why[:130]}")
            conf = g.get("confidence", 0)
            print(f"      Confidence: {conf}")
        gap_count += 1
    if result.get("usage"):
        u = result["usage"]
        print(f"  Tokens: {u['total_tokens']}, Cost: ${u['cost_estimate']:.6f}")

# === HYPOTHESIS GENERATION ===
print("\n" + "=" * 60)
print("HYPOTHESIS GENERATION")
print("=" * 60)

from scientra.ai.hypothesis_generation import generate_hypotheses

hyp_count = 0
for pid in test_papers:
    print(f'\n--- {pid[:70]}... ---')
    result = generate_hypotheses(paper_id=pid, max_hypotheses=6)
    status = result.get("status", "unknown")
    print(f"  Status: {status}")
    if result.get("hypotheses"):
        h_list = result["hypotheses"]
        print(f"  Hypotheses: {len(h_list)}")
        for h in h_list[:2]:
            risk = h.get("risk_level", "?")
            stmt = h.get("hypothesis_statement", "")[:150]
            print(f"    [{risk} risk] {stmt}")
            exp = h.get("suggested_experiment", "")
            if exp:
                print(f"      Experiment: {exp[:130]}")
            conf = h.get("confidence", 0)
            print(f"      Confidence: {conf}")
        hyp_count += 1
    if result.get("usage"):
        u = result["usage"]
        print(f"  Tokens: {u['total_tokens']}, Cost: ${u['cost_estimate']:.6f}")

# === OUTPUT FILES ===
print("\n" + "=" * 60)
print("OUTPUT FILES")
print("=" * 60)
for d in ["gaps", "hypotheses"]:
    p = Path(f"03_Assets/ai/{d}")
    files = list(p.glob("*.json")) if p.exists() else []
    print(f"  {d}: {len(files)} files")
    if files:
        for f in files[:2]:
            print(f"    {f.name}")

# === USAGE ===
print("\n" + "=" * 60)
print("AI USAGE SUMMARY")
print("=" * 60)
from scientra.ai.cost_tracker import get_usage_summary
s = get_usage_summary(days=1)
print(f"  Today calls: {s['total_calls']}")
print(f"  Success: {s['total_success']}, Failed: {s['total_failure']}")
print(f"  Total cost: ${s['total_cost']:.6f}")
print(f"  By task: {json.dumps(s['by_task'], indent=2)}")

# === SAMPLE OUTPUTS ===
print("\n" + "=" * 60)
print("SAMPLE GAP OUTPUT")
print("=" * 60)
gaps_dir = Path("03_Assets/ai/gaps")
if gaps_dir.exists():
    for f in sorted(gaps_dir.glob("*.json"))[:1]:
        data = json.loads(f.read_text(encoding="utf-8"))
        for g in (data.get("gaps", []) or [])[:1]:
            print(json.dumps(g, ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("SAMPLE HYPOTHESIS OUTPUT")
print("=" * 60)
hyp_dir = Path("03_Assets/ai/hypotheses")
if hyp_dir.exists():
    for f in sorted(hyp_dir.glob("*.json"))[:1]:
        data = json.loads(f.read_text(encoding="utf-8"))
        for h in (data.get("hypotheses", []) or [])[:1]:
            print(json.dumps(h, ensure_ascii=False, indent=2))

# === SUMMARY ===
print("\n" + "=" * 60)
print("VALIDATION SUMMARY")
print("=" * 60)
print(f"  Gap extraction: {gap_count}/{len(test_papers)}")
print(f"  Hypothesis generation: {hyp_count}/{len(test_papers)}")

# Restore
save_config(original)
reload_config()
print("\nConfig restored to original state.")
