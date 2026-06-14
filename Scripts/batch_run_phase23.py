#!/usr/bin/env python
"""Phase 2.3.2: Batch run Summary V2 + Evidence Enrichment + Gap + Hypothesis on all papers.

This script processes all 54 papers through the full AI enrichment pipeline.
Progress is tracked per-paper; failures on individual papers do not block the run.

Usage:
    python Scripts/batch_run_phase23.py              # All papers
    python Scripts/batch_run_phase23.py --limit 5    # First 5 papers (testing)
    python Scripts/batch_run_phase23.py --from-step summary_v2  # Start from specific step
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = PROJECT_ROOT / "03_Evidence"
OUTPUT_BASE = PROJECT_ROOT / "03_Assets" / "ai"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_paper_ids(limit: int = 0) -> list[str]:
    """Get all paper IDs with evidence_chunks.json."""
    if not EVIDENCE_DIR.exists():
        return []
    ids = sorted(
        d.name for d in EVIDENCE_DIR.iterdir()
        if d.is_dir() and (d / "evidence_chunks.json").exists()
    )
    return ids[:limit] if limit > 0 else ids


def load_text(paper_id: str) -> str:
    """Load paper text from sections.json or metadata."""
    sections_path = EVIDENCE_DIR / paper_id / "sections.json"
    if sections_path.exists():
        try:
            sections = json.loads(sections_path.read_text(encoding="utf-8"))
            sd = sections.get("sections", {})
            if isinstance(sd, dict):
                return "\n\n".join(str(v) for v in sd.values())[:24000]
        except Exception:
            pass

    # Fallback: abstract from metadata
    import yaml
    meta_yaml = PROJECT_ROOT / "02_Metadata" / "yaml" / f"{paper_id}.metadata.yaml"
    if meta_yaml.exists():
        try:
            meta = yaml.safe_load(meta_yaml.read_text(encoding="utf-8")) or {}
            return meta.get("abstract", "") or ""
        except Exception:
            pass
    return ""


def run_step(
    step_name: str,
    paper_ids: list[str],
    fn,
    skip_existing: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """Run a processing step across all papers.

    Returns: {generated: int, skipped: int, failed: int, errors: list}
    """
    generated = 0
    skipped = 0
    failed = 0
    errors: list[str] = []

    output_dir = OUTPUT_BASE / step_name
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(paper_ids)
    for i, pid in enumerate(paper_ids, 1):
        output_file = output_dir / f"{pid}.json"

        if skip_existing and output_file.exists():
            skipped += 1
            if total <= 5:
                print(f"  [{i}/{total}] {pid[:60]}... SKIP (exists)")
            continue

        try:
            print(f"  [{i}/{total}] {pid[:60]}... ", end="", flush=True)
            result = fn(paper_id=pid, **kwargs)
            status = result.get("status", "?")
            if status in ("generated", "enriched"):
                generated += 1
                print(f"OK ({status})")
            elif status == "skipped":
                skipped += 1
                print(f"SKIP ({result.get('reason', '')})")
            else:
                failed += 1
                err = result.get("error", result.get("warnings", ["unknown"])[0] if result.get("warnings") else "?")
                print(f"FAIL: {str(err)[:80]}")
                errors.append(f"{pid}: {str(err)[:120]}")
        except Exception as exc:
            failed += 1
            msg = f"{type(exc).__name__}: {exc}"
            print(f"ERROR: {msg[:80]}")
            errors.append(f"{pid}: {msg[:120]}")

    return {"generated": generated, "skipped": skipped, "failed": failed, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch run Phase 2.3 pipeline")
    parser.add_argument("--limit", type=int, default=0, help="Limit papers (0=all)")
    parser.add_argument("--from-step", choices=["summary_v2", "evidence_enrichment", "gap_extraction", "hypothesis_generation"],
                        default="summary_v2", help="Start from this step")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip papers that already have output")
    args = parser.parse_args()

    # Ensure API key
    # API key must be set via environment: export DEEPSEEK_API_KEY="sk-..."
    # Or configured in Config/llm_config.yaml (gitignored)

    from scientra.ai.llm_gateway import reload_config, get_config, save_config, LLMConfig
    reload_config()

    original = get_config()
    cfg = LLMConfig(
        enabled=True,
        provider=original.provider,
        model=original.model,
        api_key=original.api_key,
        base_url=original.base_url,
        temperature=original.temperature,
        max_tokens=original.max_tokens,
        enabled_tasks={
            "summary": True,
            "evidence_enrichment": True,
            "gap_extraction": True,
            "hypothesis_generation": True,
            "figure_interpretation": False,
            "table_interpretation": False,
            "supplementary_interpretation": False,
            "agent_chat": True,
        },
    )
    save_config(cfg)
    reload_config()

    paper_ids = load_paper_ids(args.limit)
    start_time = time.time()

    print(f"\n{'='*65}")
    print(f"  Phase 2.3.2 Batch Run")
    print(f"{'='*65}")
    print(f"  Papers to process: {len(paper_ids)}")
    print(f"  Starting from: {args.from_step}")
    print(f"  Skip existing: {args.skip_existing}")
    print(f"  Started at: {utc_now()}")
    print()

    report: dict[str, Any] = {
        "started_at": utc_now(),
        "paper_count": len(paper_ids),
        "steps": {},
    }

    # ── Step 1: Summary V2 ──
    if args.from_step in ("summary_v2",):
        print(f"{'─'*65}")
        print("  STEP 1: Summary V2")
        print(f"{'─'*65}")
        from scientra.ai.summary_v2 import generate_summary_v2

        def run_sv2(**kw):
            text = load_text(kw["paper_id"])
            chunks_path = EVIDENCE_DIR / kw["paper_id"] / "evidence_chunks.json"
            chunks = []
            if chunks_path.exists():
                try:
                    chunks = json.loads(chunks_path.read_text(encoding="utf-8")).get("chunks", [])[:15]
                except Exception:
                    pass
            return generate_summary_v2(text=text, evidence_chunks=chunks, **kw)

        r = run_step("summary_v2", paper_ids, run_sv2, skip_existing=args.skip_existing)
        report["steps"]["summary_v2"] = r
        print(f"  → generated={r['generated']}, skipped={r['skipped']}, failed={r['failed']}\n")

    # ── Step 2: Evidence Enrichment ──
    if args.from_step in ("summary_v2", "evidence_enrichment"):
        print(f"{'─'*65}")
        print("  STEP 2: Evidence Enrichment")
        print(f"{'─'*65}")
        from scientra.ai.evidence_enrichment import enrich_evidence_chunks

        r = run_step("evidence_enrichment", paper_ids, enrich_evidence_chunks,
                      skip_existing=args.skip_existing, batch_size=8, max_chunks=20)
        report["steps"]["evidence_enrichment"] = r
        print(f"  → generated={r['generated']}, skipped={r['skipped']}, failed={r['failed']}\n")

    # ── Step 3: Gap Extraction ──
    if args.from_step in ("summary_v2", "evidence_enrichment", "gap_extraction"):
        print(f"{'─'*65}")
        print("  STEP 3: Gap Extraction")
        print(f"{'─'*65}")
        from scientra.ai.gap_extraction import extract_research_gaps

        r = run_step("gaps", paper_ids, extract_research_gaps,
                      skip_existing=args.skip_existing, max_gaps=6)
        report["steps"]["gap_extraction"] = r
        print(f"  → generated={r['generated']}, skipped={r['skipped']}, failed={r['failed']}\n")

    # ── Step 4: Hypothesis Generation ──
    if args.from_step in ("summary_v2", "evidence_enrichment", "gap_extraction", "hypothesis_generation"):
        print(f"{'─'*65}")
        print("  STEP 4: Hypothesis Generation")
        print(f"{'─'*65}")
        from scientra.ai.hypothesis_generation import generate_hypotheses

        r = run_step("hypotheses", paper_ids, generate_hypotheses,
                      skip_existing=args.skip_existing, max_hypotheses=6)
        report["steps"]["hypothesis_generation"] = r
        print(f"  → generated={r['generated']}, skipped={r['skipped']}, failed={r['failed']}\n")

    # ── Final Report ──
    elapsed = time.time() - start_time
    report["finished_at"] = utc_now()
    report["elapsed_seconds"] = round(elapsed, 1)

    from scientra.ai.cost_tracker import get_usage_summary
    usage = get_usage_summary(days=1)
    report["usage"] = {
        "total_calls": usage["total_calls"],
        "total_cost": usage["total_cost"],
        "by_task": usage["by_task"],
    }

    print(f"{'='*65}")
    print(f"  BATCH COMPLETE")
    print(f"{'='*65}")
    for step_name, r in report["steps"].items():
        print(f"  {step_name}: generated={r['generated']}, skipped={r['skipped']}, failed={r['failed']}")
    print(f"  Elapsed: {elapsed:.0f}s ({elapsed/60:.1f}m)")
    print(f"  AI Cost: ${usage['total_cost']:.4f}")
    print(f"  AI Calls: {usage['total_calls']}")
    print()

    # Save report
    report_path = OUTPUT_BASE / "batch_run_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Restore original config
    save_config(original)
    reload_config()
    print("Config restored. Report:", report_path)

    total_failed = sum(r["failed"] for r in report["steps"].values())
    return 1 if total_failed > len(paper_ids) // 2 else 0


if __name__ == "__main__":
    sys.exit(main())
