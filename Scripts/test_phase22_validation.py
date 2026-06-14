"""Phase 2.2 validation script — runs Summary V2 + Evidence Enrichment on 2 papers."""
import sys, json, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure correct API key from config file (ignoring env var if wrong)
from scientra.ai.llm_gateway import reload_config, get_config, save_config, LLMConfig
reload_config()
cfg = get_config()

# If env var has wrong key, override by unsetting it temporarily
env_key = os.environ.pop("DEEPSEEK_API_KEY", None)
if env_key and env_key != cfg.api_key:
    print(f"Note: Env DEEPSEEK_API_KEY overridden by config key")
    os.environ["DEEPSEEK_API_KEY"] = cfg.api_key

evidence_dir = Path("03_Evidence")
paper_dirs = sorted(
    d.name for d in evidence_dir.iterdir()
    if d.is_dir() and (d / "evidence_chunks.json").exists()
)
test_papers = paper_dirs[:2]
print(f"Testing on {len(test_papers)} papers: {[p[:50]+'...' for p in test_papers]}")

# Ensure evidence_enrichment is enabled
original = get_config()
if not original.is_task_enabled("evidence_enrichment"):
    print("Enabling evidence_enrichment task for test...")
    new_cfg = LLMConfig(
        enabled=original.enabled,
        provider=original.provider,
        model=original.model,
        api_key=original.api_key,
        base_url=original.base_url,
        temperature=original.temperature,
        max_tokens=original.max_tokens,
        enabled_tasks={**original.enabled_tasks, "evidence_enrichment": True},
    )
    save_config(new_cfg)
    reload_config()

# === Summary V2 ===
print("\n" + "=" * 60)
print("SUMMARY V2")
print("=" * 60)

from scientra.ai.summary_v2 import generate_summary_v2

sv2_count = 0
for pid in test_papers:
    print(f'\n--- {pid[:70]}... ---')
    chunks_path = evidence_dir / pid / "evidence_chunks.json"
    chunks_data = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks = chunks_data.get("chunks", [])[:15]

    text = ""
    sections_path = evidence_dir / pid / "sections.json"
    if sections_path.exists():
        sections = json.loads(sections_path.read_text(encoding="utf-8"))
        sections_dict = sections.get("sections", {})
        if isinstance(sections_dict, dict):
            text = "\n\n".join(str(v) for v in sections_dict.values())[:24000]

    if not text:
        import yaml
        meta_yaml = Path(f"02_Metadata/yaml/{pid}.metadata.yaml")
        if meta_yaml.exists():
            meta = yaml.safe_load(meta_yaml.read_text(encoding="utf-8")) or {}
            text = meta.get("abstract", "") or ""

    result = generate_summary_v2(paper_id=pid, text=text, evidence_chunks=chunks)
    status = result.get("status", "unknown")
    print(f"  Status: {status}")
    if result.get("core_finding"):
        print(f"  Core finding: {result['core_finding'][:200]}")
    print(f"  Confidence: {result.get('confidence')}")
    print(f"  Methods: {len(result.get('method_summary', []))}")
    print(f"  Key evidence: {len(result.get('key_evidence', []))}")
    print(f"  Main claims: {len(result.get('main_claims', []))}")
    print(f"  Warnings: {result.get('warnings')}")
    if result.get("usage"):
        u = result["usage"]
        print(f"  Model: {result.get('model')}, Provider: {result.get('provider')}")
        print(f"  Tokens: {u['total_tokens']}, Cost: ${u['cost_estimate']:.6f}")
    if status == "generated":
        sv2_count += 1

# === Evidence Enrichment ===
print("\n" + "=" * 60)
print("EVIDENCE ENRICHMENT")
print("=" * 60)

from scientra.ai.evidence_enrichment import enrich_evidence_chunks

ee_count = 0
for pid in test_papers:
    print(f'\n--- {pid[:70]}... ---')
    result = enrich_evidence_chunks(paper_id=pid, batch_size=8, max_chunks=16)
    status = result.get("status", "unknown")
    print(f"  Status: {status}")
    print(f"  Total chunks: {result.get('total_chunks')}")
    print(f"  Eligible: {result.get('eligible_chunks')}")
    print(f"  Enriched: {result.get('enriched_chunks')}")
    print(f"  Batches: {result.get('batch_count')}, Failed: {result.get('failed_batches')}")
    if result.get("usage"):
        u = result["usage"]
        print(f"  Tokens: {u['total_tokens']}, Cost: ${u['cost_estimate']:.6f}")
    if result.get("chunks") and len(result["chunks"]) > 0:
        # Show first enriched chunk that has actual content
        for c in result["chunks"]:
            if c.get("ai_claim"):
                print(f"  Sample enriched chunk:")
                print(f"    chunk_id: {c.get('chunk_id')}")
                print(f"    claim: {c.get('ai_claim', '')[:150]}")
                print(f"    finding: {c.get('ai_finding', '')[:150]}")
                print(f"    evidence_strength: {c.get('evidence_strength')}")
                print(f"    methods: {c.get('method_mentioned', [])}")
                print(f"    entities: {c.get('entity_mentioned', [])}")
                print(f"    confidence: {c.get('confidence')}")
                break
    if status == "enriched":
        ee_count += 1

# === AI Usage Log ===
print("\n" + "=" * 60)
print("AI USAGE LOG")
print("=" * 60)

from scientra.ai.cost_tracker import get_usage_summary, USAGE_LOG_DIR
summary = get_usage_summary(days=1)
print(f"  Today's calls: {summary['total_calls']}")
print(f"  Success: {summary['total_success']}, Failed: {summary['total_failure']}")
print(f"  Total cost: ${summary['total_cost']:.6f}")
print(f"  By provider: {summary['by_provider']}")
print(f"  By task: {summary['by_task']}")
print(f"  Log dir: {USAGE_LOG_DIR}")

# === Output files check ===
print("\n" + "=" * 60)
print("OUTPUT FILES")
print("=" * 60)

sv2_dir = Path("03_Assets/ai/summary_v2")
ee_dir = Path("03_Assets/ai/evidence_enrichment")
print(f"  Summary V2 files: {len(list(sv2_dir.glob('*.json'))) if sv2_dir.exists() else 0}")
print(f"  Evidence enrichment files: {len(list(ee_dir.glob('*.json'))) if ee_dir.exists() else 0}")

# === Summary ===
print("\n" + "=" * 60)
print("VALIDATION SUMMARY")
print("=" * 60)
print(f"  Summary V2 generated: {sv2_count}/{len(test_papers)}")
print(f"  Evidence enrichment generated: {ee_count}/{len(test_papers)}")
print()

# Restore original config
save_config(original)
reload_config()
print("Config restored to original state.")
