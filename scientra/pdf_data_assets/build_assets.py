"""
Build Assets — Phase 0 main entry point for PDF data assetization.
Phase 0.5 — quality checking, noise filtering, sample export, quality reports.

Commands:
    python -m scientra.pdf_data_assets.build_assets --paper-id P0001
    python -m scientra.pdf_data_assets.build_assets --all
    python -m scientra.pdf_data_assets.build_assets --force
    python -m scientra.pdf_data_assets.build_assets --status
    python -m scientra.pdf_data_assets.build_assets --quality-check
    python -m scientra.pdf_data_assets.build_assets --quality-check --paper-id P0001
    python -m scientra.pdf_data_assets.build_assets --export-samples
    python -m scientra.pdf_data_assets.build_assets --quality-report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger("pdf_data_assets")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


def _get_project_root() -> Path:
    """Resolve project root from this file's location."""
    return Path(__file__).resolve().parent.parent.parent


def _load_config(root: Path) -> dict[str, Any]:
    """Load pdf_data_assets.yaml config, or return safe defaults."""
    import yaml

    config_path = root / "Config" / "pdf_data_assets.yaml"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def show_status(root: Path | None = None) -> dict[str, Any]:
    """Print and return the current assetization status."""
    if root is None:
        root = _get_project_root()

    from scientra.pdf_data_assets.asset_registry import AssetRegistry
    from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter

    registry = AssetRegistry(root)
    adapter = EvidenceAdapter(root)

    available_papers = adapter.list_paper_ids()
    registered_papers = registry.list_papers()
    registry_summary = registry.status_summary()

    status = {
        "available_papers_in_03_evidence": len(available_papers),
        "registered_papers_in_06_assets": len(registered_papers),
        "registry_summary": registry_summary,
        "config_loaded": bool(_load_config(root)),
    }

    print("=== PDF Data Assets Status ===")
    print(f"Papers with evidence.json:  {len(available_papers)}")
    print(f"Papers in asset registry:   {len(registered_papers)}")
    print(f"Config loaded:              {status['config_loaded']}")
    summary = registry_summary
    print(f"Total papers (registry):    {summary.get('total_papers', 0)}")
    print(f"By status:                  {summary.get('by_status', {})}")
    print(f"Total assets:               {summary.get('total_assets', {})}")
    print()

    if not available_papers:
        print("No existing paper_id found.")
        print("Please run workflow.py first or check 02_Metadata / 03_Evidence.")
    else:
        print(f"Sample paper_ids: {available_papers[:3]}")

    return status


# ── Phase 0.5: Quality Check ──

def run_quality_check(
    paper_id: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Run all quality checkers for one paper or all papers."""
    if root is None:
        root = _get_project_root()

    from scientra.pdf_data_assets.quality.asset_quality_checker import AssetQualityChecker
    from scientra.pdf_data_assets.quality.entity_noise_filter import EntityNoiseFilter
    from scientra.pdf_data_assets.quality.chunk_quality_checker import ChunkQualityChecker
    from scientra.pdf_data_assets.quality.claim_quality_checker import ClaimQualityChecker

    quality_checker = AssetQualityChecker(root)
    entity_filter = EntityNoiseFilter(root)
    chunk_checker = ChunkQualityChecker(root)
    claim_checker = ClaimQualityChecker(root)

    if paper_id:
        # Single paper
        print(f"\n=== Quality Check: {paper_id} ===\n")

        print("[1/4] Asset completeness check...")
        comp = quality_checker.check_paper(paper_id)
        print(f"      Overall score: {comp.get('overall_score', 0)} / 100 ({comp.get('overall_status', 'unknown')})")
        for issue in comp.get("issues", []):
            print(f"      - {issue}")

        print("[2/4] Entity noise filtering...")
        ent = entity_filter.filter_paper(paper_id)
        print(f"      Original: {ent.get('original_count', 0)} -> Kept: {ent.get('kept_count', 0)} "
              f"(filtered: {ent.get('filtered_count', 0)})")
        stats = ent.get("filter_stats", {})
        for k, v in stats.items():
            if v > 0:
                print(f"        {k}: {v}")

        print("[3/4] Chunk quality check...")
        chk = chunk_checker.check_paper(paper_id)
        print(f"      Total: {chk.get('total', 0)} | Vector-ready: {chk.get('vector_ready', 0)} "
              f"({chk.get('vector_ready_pct', 0)}%) | Avg score: {chk.get('average_quality_score', 0)}")

        print("[4/4] Claim quality check...")
        clm = claim_checker.check_paper(paper_id)
        print(f"      Total claims: {clm.get('total_claims', 0)} | "
              f"Needs AI: {clm.get('needs_ai_interpretation', 0)} "
              f"({clm.get('needs_ai_pct', 0)}%) | "
              f"Has evidence: {clm.get('has_evidence_pct', 0)}%")

        # Save quality status
        quality_checker.save_quality_status()

        print(f"\n[OK] Quality check complete for {paper_id}")

        return {
            "paper_id": paper_id,
            "completeness": comp,
            "entity_filter": {k: v for k, v in ent.items() if k != "entities"},
            "chunk_quality": {k: v for k, v in chk.items() if k != "chunks"},
            "claim_quality": clm,
        }

    else:
        # All papers in registry
        from scientra.pdf_data_assets.asset_registry import AssetRegistry
        registry = AssetRegistry(root)
        entries = registry.all_entries()
        success_entries = [e for e in entries if e.build_status.value == "success"]

        if not success_entries:
            print("No successfully built papers in registry. Run --all first.")
            return {"error": "no_successful_papers"}

        print(f"\n=== Quality Check: {len(success_entries)} papers ===\n")

        results: dict[str, Any] = {"papers": {}, "summary": {}}
        total_entities_before = 0
        total_entities_after = 0
        total_chunks = 0
        total_vr = 0
        total_claims = 0
        total_needs_ai = 0

        for entry in success_entries:
            pid = entry.paper_id
            print(f"  Checking {pid[:60]}...")

            # Entity filter
            ent = entity_filter.filter_paper(pid)
            total_entities_before += ent.get("original_count", 0)
            total_entities_after += ent.get("kept_count", 0)

            # Chunk quality
            chk = chunk_checker.check_paper(pid)
            total_chunks += chk.get("total", 0)
            total_vr += chk.get("vector_ready", 0)

            # Claim quality
            clm = claim_checker.check_paper(pid)
            total_claims += clm.get("total_claims", 0)
            total_needs_ai += clm.get("needs_ai_interpretation", 0)

            comp = quality_checker.check_paper(pid)
            results["papers"][pid] = {
                "completeness_score": comp.get("overall_score", 0),
                "entities_before": ent.get("original_count", 0),
                "entities_after": ent.get("kept_count", 0),
                "chunks_total": chk.get("total", 0),
                "chunks_vector_ready_pct": chk.get("vector_ready_pct", 0),
                "claims_total": clm.get("total_claims", 0),
                "claims_needs_ai_pct": clm.get("needs_ai_pct", 0),
            }

        # Save aggregate quality status
        quality_checker.save_quality_status()

        results["summary"] = {
            "papers_checked": len(success_entries),
            "entities_before": total_entities_before,
            "entities_after": total_entities_after,
            "entities_filtered": total_entities_before - total_entities_after,
            "entities_noise_pct": round(
                (total_entities_before - total_entities_after) / max(total_entities_before, 1) * 100, 1
            ),
            "chunks_total": total_chunks,
            "chunks_vector_ready_pct": round(total_vr / max(total_chunks, 1) * 100, 1),
            "claims_total": total_claims,
            "claims_needs_ai_pct": round(total_needs_ai / max(total_claims, 1) * 100, 1),
        }

        print(f"\n=== Quality Check Summary ===")
        s = results["summary"]
        print(f"Papers checked:           {s['papers_checked']}")
        print(f"Entities: {s['entities_before']} -> {s['entities_after']} ({s['entities_noise_pct']}% noise)")
        print(f"Chunks vector-ready:     {s['chunks_vector_ready_pct']}%")
        print(f"Claims needs-AI:         {s['claims_needs_ai_pct']}%")

        return results


# ── Phase 0.5: Sample Export ──

def export_samples(
    paper_id: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Export human-review samples for one paper or all papers."""
    if root is None:
        root = _get_project_root()

    from scientra.pdf_data_assets.quality.sample_exporter import SampleExporter

    exporter = SampleExporter(root)

    if paper_id:
        print(f"\n=== Exporting samples for {paper_id} ===\n")
        result = exporter.export_paper(paper_id)
        print(f"  JSON: {result.get('json_path', 'N/A')}")
        print(f"  MD:   {result.get('md_path', 'N/A')}")
        counts = result.get("sample_counts", {})
        for k, v in counts.items():
            print(f"  {k}: {v} samples")
        return result
    else:
        print(f"\n=== Exporting samples for all papers ===\n")
        result = exporter.export_all()
        count = len(result.get("papers", {}))
        print(f"  Exported samples for {count} papers")
        print(f"  Output: 06_PDF_DataAssets/00_registry/samples/")
        return result


# ── Phase 0.5: Quality Report ──

def run_quality_report(root: Path | None = None) -> dict[str, Any]:
    """Generate the full-library quality report."""
    if root is None:
        root = _get_project_root()

    from scientra.pdf_data_assets.quality.quality_report_builder import QualityReportBuilder

    print(f"\n=== Building Quality Report ===\n")
    builder = QualityReportBuilder(root)
    report = builder.build()

    if "error" in report:
        print(f"Error: {report['error']}")
        return report

    print(f"  Report: {report.get('md_path', 'N/A')}")
    print(f"  Papers: {report.get('total_papers_in_registry', 0)} ({report.get('successful_papers', 0)} successful)")

    ent = report.get("entity_noise", {})
    print(f"  Entity noise: {ent.get('avg_noise_pct', 0):.1f}%")

    cq = report.get("chunk_quality", {})
    print(f"  Chunk vector-ready: {cq.get('avg_vector_ready_pct', 0):.1f}%")

    clq = report.get("claim_quality", {})
    print(f"  Claims needs-AI: {clq.get('avg_needs_ai_pct', 0):.1f}%")

    risks = report.get("quality_risks", [])
    if risks:
        print(f"\n  Quality risks ({len(risks)}):")
        for r in risks:
            print(f"    - {r}")

    print(f"\n[OK] Quality report generated")
    return report


# ── Phase 0: Build Assets ──

def build_paper(
    paper_id: str,
    root: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Build all assets for a single paper."""
    if root is None:
        root = _get_project_root()

    from scientra.pdf_data_assets.asset_registry import AssetRegistry, RegistryEntry
    from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter
    from scientra.pdf_data_assets.section_aligner import SectionAligner
    from scientra.pdf_data_assets.method_asset_builder import MethodAssetBuilder
    from scientra.pdf_data_assets.result_asset_builder import ResultAssetBuilder
    from scientra.pdf_data_assets.entity_asset_builder import EntityAssetBuilder
    from scientra.pdf_data_assets.claim_evidence_builder import ClaimEvidenceBuilder
    from scientra.pdf_data_assets.agent_chunk_builder import AgentChunkBuilder
    from scientra.pdf_data_assets.schemas import BuildStatus

    adapter = EvidenceAdapter(root)
    registry = AssetRegistry(root)

    # Validate paper exists
    if not adapter.has_evidence(paper_id):
        msg = f"No existing paper_id found for '{paper_id}'. Please run workflow.py first or check 02_Metadata / 03_Evidence."
        print(msg)
        logger.warning(msg)
        return {"paper_id": paper_id, "status": "skipped_no_evidence", "error": msg}

    print(f"\n=== Building assets for {paper_id} ===\n")

    config = _load_config(root)
    features = config.get("features", {})

    result: dict[str, Any] = {
        "paper_id": paper_id,
        "status": "success",
        "assets": {},
        "errors": [],
    }

    try:
        # Section alignment
        print("[1/6] Aligning sections...")
        section_aligner = SectionAligner(root)
        section_assets = section_aligner.build(paper_id, force=force)
        result["assets"]["sections"] = len(section_assets)
        print(f"      {len(section_assets)} section assets")

        # Method assets
        print("[2/6] Building method assets...")
        method_builder = MethodAssetBuilder(root)
        method_assets = method_builder.build(paper_id, force=force)
        result["assets"]["methods"] = len(method_assets)
        print(f"      {len(method_assets)} method assets")

        # Result assets
        print("[3/6] Building result assets...")
        result_builder = ResultAssetBuilder(root)
        result_assets = result_builder.build(paper_id, force=force)
        result["assets"]["results"] = len(result_assets)
        print(f"      {len(result_assets)} result assets")

        # Entity assets
        print("[4/6] Building entity assets...")
        entity_builder = EntityAssetBuilder(root)
        entity_assets = entity_builder.build(paper_id, force=force)
        result["assets"]["entities"] = len(entity_assets)
        print(f"      {len(entity_assets)} entity assets")

        # Claim-evidence links
        print("[5/6] Building claim-evidence links...")
        claim_builder = ClaimEvidenceBuilder(root)
        claim_data = claim_builder.build(paper_id, force=force)
        result["assets"]["claims"] = claim_data.get("claim_count", 0)
        result["assets"]["evidence_links"] = claim_data.get("evidence_link_count", 0)
        print(f"      {result['assets']['claims']} claims, {result['assets']['evidence_links']} evidence links")

        # Agent chunks
        generate_chunks = features.get("generate_agent_chunks", True)
        if generate_chunks:
            print("[6/6] Building agent chunks...")
            chunk_builder = AgentChunkBuilder(root)
            chunks = chunk_builder.build(paper_id, force=force)
            result["assets"]["agent_chunks"] = len(chunks)
            print(f"      {len(chunks)} agent chunks")
        else:
            print("[6/6] Agent chunks disabled in config")
            result["assets"]["agent_chunks"] = 0

        # Register
        entry = RegistryEntry(
            paper_id=paper_id,
            metadata_path=f"02_Metadata/yaml/{paper_id}.metadata.yaml",
            evidence_path=f"03_Evidence/{paper_id}/evidence.json",
            summary_path=f"03_Summary/paper_*/summary.md",
            section_assets=result["assets"].get("sections", 0),
            method_assets=result["assets"].get("methods", 0),
            result_assets=result["assets"].get("results", 0),
            entity_assets=result["assets"].get("entities", 0),
            claim_assets=result["assets"].get("claims", 0),
            agent_chunks=result["assets"].get("agent_chunks", 0),
            figure_assets=0,
            table_assets=0,
            supplementary_links=0,
            build_status=BuildStatus.success,
            error_message=None,
        )
        registry.upsert_entry(entry)
        registry.update_totals()

        print(f"\n[OK] Assetization complete for {paper_id}")
        print(f"  Sections: {entry.section_assets} | Methods: {entry.method_assets} | "
              f"Results: {entry.result_assets} | Entities: {entry.entity_assets} | "
              f"Claims: {entry.claim_assets} | Chunks: {entry.agent_chunks}")

    except Exception as exc:
        logger.error(f"Failed to build assets for {paper_id}: {exc}")
        result["status"] = "failed"
        result["errors"].append(str(exc))

        # Register failure
        entry = RegistryEntry(
            paper_id=paper_id,
            build_status=BuildStatus.failed,
            error_message=str(exc),
        )
        registry.upsert_entry(entry)

    return result


def build_all(root: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Build assets for all papers with evidence.json."""
    if root is None:
        root = _get_project_root()

    from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter

    adapter = EvidenceAdapter(root)
    paper_ids = adapter.list_paper_ids()

    if not paper_ids:
        print("No existing paper_id found. Please run workflow.py first or check 02_Metadata / 03_Evidence.")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "results": []}

    print(f"Building assets for {len(paper_ids)} papers...\n")

    summary = {"total": len(paper_ids), "success": 0, "failed": 0, "skipped": 0, "results": []}

    for pid in paper_ids:
        r = build_paper(pid, root=root, force=force)
        summary["results"].append(r)
        if r["status"] == "success":
            summary["success"] += 1
        elif r["status"] == "skipped_no_evidence":
            summary["skipped"] += 1
        else:
            summary["failed"] += 1

    print(f"\n=== Build Complete ===")
    print(f"Total: {summary['total']} | Success: {summary['success']} | "
          f"Failed: {summary['failed']} | Skipped: {summary['skipped']}")

    return summary


# ── Phase 1: Figure Extraction ──

def run_figure_extraction(
    paper_id: str, root: Path | None = None, force: bool = False
) -> dict[str, Any]:
    if root is None:
        root = _get_project_root()
    from scientra.pdf_data_assets.figure_asset_builder import FigureAssetBuilder
    from scientra.pdf_data_assets.agent_chunk_builder import AgentChunkBuilder
    from scientra.pdf_data_assets.asset_registry import AssetRegistry, RegistryEntry
    from scientra.pdf_data_assets.schemas import BuildStatus

    builder = FigureAssetBuilder(root)
    chunk_builder = AgentChunkBuilder(root)
    registry = AssetRegistry(root)

    print(f"\n=== Figure Extraction: {paper_id} ===\n")
    try:
        figures = builder.build(paper_id, force=force)
        print(f"  Figures extracted: {len(figures)}")

        # Regenerate chunks to include figure chunks
        chunks = chunk_builder.build(paper_id, force=True)
        print(f"  Chunks regenerated: {len(chunks)} (now includes figure chunks)")

        entry = registry.get_entry(paper_id)
        if entry:
            entry.figure_assets = len(figures)
            registry.upsert_entry(entry)
            registry.update_totals()

        print(f"\n[OK] Figure extraction complete for {paper_id}")
        return {"paper_id": paper_id, "status": "success", "figures": len(figures), "chunks": len(chunks)}
    except Exception as e:
        logger.error(f"Figure extraction failed for {paper_id}: {e}")
        return {"paper_id": paper_id, "status": "failed", "error": str(e)}


def run_figure_extraction_all(root: Path | None = None, force: bool = False) -> dict[str, Any]:
    if root is None:
        root = _get_project_root()
    from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter

    adapter = EvidenceAdapter(root)
    paper_ids = adapter.list_paper_ids()
    results = []
    total_figures = 0
    for pid in paper_ids:
        r = run_figure_extraction(pid, root=root, force=force)
        results.append(r)
        if r["status"] == "success":
            total_figures += r.get("figures", 0)

    print(f"\n=== Figure Extraction Complete ===")
    print(f"Papers: {len(paper_ids)} | Total figures: {total_figures}")
    return {"total": len(paper_ids), "total_figures": total_figures, "results": results}


# ── Phase 1B: Figure Interpretation ──

def run_figure_interpretation(paper_id: str, root: Path | None = None, force: bool = False) -> dict[str, Any]:
    if root is None: root = _get_project_root()
    from scientra.pdf_data_assets.figure_interpreter import FigureInterpreter
    interpreter = FigureInterpreter(root)
    print(f"\n=== Figure Interpretation: {paper_id} ===\n")
    if not interpreter.llm_available:
        print("  ANTHROPIC_API_KEY not set — all figures will be pending")
    result = interpreter.interpret_paper(paper_id, force=force)
    stats = result.get("stats", {})
    print(f"  Total: {stats.get('total',0)} | Interpreted: {stats.get('interpreted',0)} | "
          f"Skipped: {stats.get('skipped',0)} | Pending: {stats.get('pending',0)}")
    print(f"\n[OK] Figure interpretation complete for {paper_id}")
    return result

def run_figure_interpretation_all(root: Path | None = None, force: bool = False) -> dict[str, Any]:
    if root is None: root = _get_project_root()
    from scientra.pdf_data_assets.figure_interpreter import FigureInterpreter
    interpreter = FigureInterpreter(root)
    print(f"\n=== Figure Interpretation: ALL ===\n")
    print(f"  LLM available: {interpreter.llm_available}")
    result = interpreter.interpret_all(force=force)
    stats = result.get("stats", {})
    print(f"\n=== Complete ===\nPapers: {result.get('papers',0)} | "
          f"Total figs: {stats.get('total',0)} | Interpreted: {stats.get('interpreted',0)} | "
          f"Skipped: {stats.get('skipped',0)} | Pending: {stats.get('pending',0)}")
    return result

# ── CLI ──

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scientra PDF Data Assets — Phase 0 + 0.5 Assetization & Quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Phase 0: Build
  python -m scientra.pdf_data_assets.build_assets --paper-id "Bacillus_thuringiensis_toxins_an_overview_be8f9a28904d"
  python -m scientra.pdf_data_assets.build_assets --all
  python -m scientra.pdf_data_assets.build_assets --all --force
  python -m scientra.pdf_data_assets.build_assets --status

  # Phase 0.5: Quality
  python -m scientra.pdf_data_assets.build_assets --quality-check --paper-id "Bacillus_thuringiensis..."
  python -m scientra.pdf_data_assets.build_assets --quality-check
  python -m scientra.pdf_data_assets.build_assets --export-samples
  python -m scientra.pdf_data_assets.build_assets --export-samples --paper-id "Bacillus_thuringiensis..."
  python -m scientra.pdf_data_assets.build_assets --quality-report
        """,
    )
    parser.add_argument("--paper-id", type=str, help="Target a specific paper_id")
    parser.add_argument("--all", action="store_true", help="Build assets for all papers with evidence")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if outputs exist")
    parser.add_argument("--status", action="store_true", help="Show assetization status")

    # Phase 0.5
    parser.add_argument("--quality-check", action="store_true",
                        help="Run quality checks (completeness, entity filter, chunk & claim quality)")
    parser.add_argument("--export-samples", action="store_true",
                        help="Export human-review sample files")
    parser.add_argument("--quality-report", action="store_true",
                        help="Generate full-library quality report")

    # Phase 1
    parser.add_argument("--figures", action="store_true",
                        help="Build figure assets (Phase 1: Figure + Caption Extraction)")
    parser.add_argument("--interpret-figures", action="store_true",
                        help="AI interpretation of figures from captions (Phase 1B)")

    args = parser.parse_args()
    root = _get_project_root()

    # Phase 1B: Figure interpretation
    if args.interpret_figures:
        if args.paper_id:
            run_figure_interpretation(args.paper_id, root=root, force=args.force)
        elif args.all:
            run_figure_interpretation_all(root=root, force=args.force)
        else:
            print("Use --interpret-figures with --paper-id or --all")
        return 0

    # Phase 1: Figure extraction
    if args.figures:
        if args.paper_id:
            run_figure_extraction(args.paper_id, root=root, force=args.force)
        elif args.all:
            run_figure_extraction_all(root=root, force=args.force)
        else:
            print("Use --figures with --paper-id or --all")
        return 0

    # Phase 0.5 commands (can run standalone or on top of existing builds)
    if args.quality_report:
        run_quality_report(root=root)
        return 0

    if args.export_samples:
        export_samples(paper_id=args.paper_id, root=root)
        return 0

    if args.quality_check:
        run_quality_check(paper_id=args.paper_id, root=root)
        return 0

    # Phase 0 commands
    if args.status:
        show_status()
        return 0

    if args.all:
        build_all(root=root, force=args.force)
        return 0

    if args.paper_id:
        result = build_paper(args.paper_id, root=root, force=args.force)
        return 0 if result["status"] == "success" else 1

    # Default: show status
    show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
