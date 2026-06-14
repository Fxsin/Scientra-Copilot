"""Run hypothesis generation for remaining papers."""
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

hyp_dir = Path("03_Assets/ai/hypotheses")
hyp_done = set(f.stem for f in hyp_dir.glob("*.json")) if hyp_dir.exists() else set()
hyp_missing = [p for p in all_papers if p not in hyp_done]
print(f"Hypothesis generation: {len(hyp_missing)} remaining\n")

from scientra.ai.hypothesis_generation import generate_hypotheses
good = 0
fail = 0
for i, pid in enumerate(hyp_missing, 1):
    print(f"[{i}/{len(hyp_missing)}] {pid[:60]}...", end=" ", flush=True)
    try:
        result = generate_hypotheses(paper_id=pid, max_hypotheses=6)
        status = result.get("status", "?")
        if status == "generated":
            good += 1
            h = len(result.get("hypotheses", []))
            print(f"OK ({h} hyps)")
        else:
            fail += 1
            w = result.get("warnings", ["?"])
            w0 = w[0][:50] if w else "?"
            print(f"SKIP/{status}: {w0}")
    except Exception as e:
        fail += 1
        print(f"ERROR: {e}")

print(f"\nHypothesis Generation: {good} ok, {fail} failed/skipped")

# Final counts
print("\nFINAL COUNTS:")
for d in ["summary_v2", "evidence_enrichment", "gaps", "hypotheses"]:
    p = Path(f"03_Assets/ai/{d}")
    count = len(list(p.glob("*.json"))) if p.exists() else 0
    print(f"  {d}: {count} / {len(all_papers)}")

save_config(original)
reload_config()
print("\nDone.")
