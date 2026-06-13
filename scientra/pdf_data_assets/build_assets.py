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
import json
import sys
from datetime import datetime, timezone
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


# ── Phase 2A: Table Extraction ──

def run_table_extraction(
    paper_id: str, root: Path | None = None, force: bool = False
) -> dict[str, Any]:
    """Build table assets for a single paper (Phase 2A: Caption + Reference)."""
    if root is None:
        root = _get_project_root()
    from scientra.pdf_data_assets.table_asset_builder import TableAssetBuilder
    from scientra.pdf_data_assets.agent_chunk_builder import AgentChunkBuilder
    from scientra.pdf_data_assets.asset_registry import AssetRegistry, RegistryEntry
    from scientra.pdf_data_assets.schemas import BuildStatus

    builder = TableAssetBuilder(root)
    chunk_builder = AgentChunkBuilder(root)
    registry = AssetRegistry(root)

    print(f"\n=== Table Extraction: {paper_id} ===\n")
    try:
        tables = builder.build(paper_id, force=force)
        print(f"  Tables extracted: {len(tables)}")

        # Regenerate chunks to include table chunks
        chunks = chunk_builder.build(paper_id, force=True)
        print(f"  Chunks regenerated: {len(chunks)} (now includes table chunks)")

        entry = registry.get_entry(paper_id)
        if entry:
            entry.table_assets = len(tables)
            registry.upsert_entry(entry)
            registry.update_totals()
        else:
            # Create new entry if none exists
            entry = RegistryEntry(
                paper_id=paper_id,
                table_assets=len(tables),
                build_status=BuildStatus.success,
                error_message=None,
            )
            registry.upsert_entry(entry)
            registry.update_totals()

        print(f"\n[OK] Table extraction complete for {paper_id}")
        return {"paper_id": paper_id, "status": "success", "tables": len(tables), "chunks": len(chunks)}
    except Exception as e:
        logger.error(f"Table extraction failed for {paper_id}: {e}")
        # Register failure without crashing
        registry = AssetRegistry(root)
        entry = RegistryEntry(
            paper_id=paper_id,
            build_status=BuildStatus.failed,
            error_message=str(e),
        )
        registry.upsert_entry(entry)
        return {"paper_id": paper_id, "status": "failed", "error": str(e)}


def run_table_extraction_all(root: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Build table assets for all papers with evidence.json."""
    if root is None:
        root = _get_project_root()
    from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter

    adapter = EvidenceAdapter(root)
    paper_ids = adapter.list_paper_ids()
    results = []
    total_tables = 0
    total_success = 0
    total_failed = 0

    for pid in paper_ids:
        r = run_table_extraction(pid, root=root, force=force)
        results.append(r)
        if r["status"] == "success":
            total_success += 1
            total_tables += r.get("tables", 0)
        else:
            total_failed += 1

    # Generate table extraction report
    _generate_table_report(root, results, total_tables, total_success, total_failed)

    print(f"\n=== Table Extraction Complete ===")
    print(f"Papers: {len(paper_ids)} | Success: {total_success} | Failed: {total_failed}")
    print(f"Total tables: {total_tables}")
    return {"total": len(paper_ids), "total_tables": total_tables, "success": total_success,
            "failed": total_failed, "results": results}


def _generate_table_report(
    root: Path, results: list[dict[str, Any]], total_tables: int,
    total_success: int, total_failed: int
) -> None:
    """Generate table extraction report: 06_PDF_DataAssets/00_registry/table_extraction_report.md."""
    from collections import Counter

    report_path = root / "06_PDF_DataAssets" / "00_registry" / "table_extraction_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect statistics
    total_papers = len(results)
    total_with_caption = 0
    total_with_refs = 0
    caption_source_dist: Counter = Counter()
    caption_quality_dist: Counter = Counter()
    table_type_dist: Counter = Counter()
    total_linked_result = 0
    total_linked_claim = 0
    total_linked_evidence = 0
    caption_samples: list[str] = []
    no_caption_samples: list[str] = []
    failed_papers: list[str] = []
    # Phase 2B: Structure stats
    structure_status_dist: Counter = Counter()
    structure_confidence_dist: Counter = Counter()
    extraction_method_dist: Counter = Counter()
    row_counts: list[int] = []
    col_counts: list[int] = []
    simple_samples: list[str] = []
    complex_samples: list[str] = []
    caption_only_samples: list[str] = []

    for r in results:
        pid = r.get("paper_id", "unknown")
        if r.get("status") == "failed":
            failed_papers.append(f"{pid}: {r.get('error', 'unknown error')}")
            continue

        # Load tables.json to gather detailed stats
        tbl_path = root / "06_PDF_DataAssets" / "03_tables" / pid / "tables.json"
        if not tbl_path.exists():
            continue

        try:
            tables = json.loads(tbl_path.read_text(encoding="utf-8"))
            for t in tables:
                caption = t.get("caption", "")
                refs = t.get("reference_sentences", [])

                if caption.strip():
                    total_with_caption += 1
                    if len(caption_samples) < 10:
                        label = t.get("table_label", "?")
                        caption_samples.append(f"**{label}**: {caption[:300]}...")

                if refs:
                    total_with_refs += 1
                    if len(no_caption_samples) < 10 and not caption.strip():
                        label = t.get("table_label", "?")
                        no_caption_samples.append(f"**{label}**: {'; '.join(refs[:2])[:300]}")

                cs = t.get("caption_source", "unknown")
                caption_source_dist[cs] += 1

                cq = t.get("caption_quality", "none")
                caption_quality_dist[cq] += 1

                tt = t.get("table_type", "unknown")
                table_type_dist[tt] += 1

                linked_results = t.get("linked_result_assets", [])
                total_linked_result += len(linked_results)

                linked_claims = t.get("linked_claim_assets", [])
                total_linked_claim += len(linked_claims)

                linked_ev = t.get("linked_evidence_ids", [])
                total_linked_evidence += len(linked_ev)

                # Phase 2B: Structure stats
                ss = t.get("structure_status", "caption_only")
                structure_status_dist[ss] += 1

                sc = t.get("structure_confidence", "none")
                structure_confidence_dist[sc] += 1

                sem = t.get("structure_extraction_method", "unavailable")
                extraction_method_dist[sem] += 1

                s_rows = t.get("structured_rows", [])
                s_cols = t.get("structured_columns", [])
                if s_rows:
                    row_counts.append(len(s_rows))
                if s_cols:
                    col_counts.append(len(s_cols))

                label = t.get("table_label", "?")
                if ss == "simple_structure_extracted" and len(simple_samples) < 10:
                    simple_samples.append(f"**{label}**: cols={len(s_cols)}, rows={len(s_rows)}, confidence={sc}, method={sem}")
                elif ss == "complex_structure_skipped" and len(complex_samples) < 10:
                    notes = t.get("structure_notes", [])
                    complex_samples.append(f"**{label}**: {', '.join(notes[:2])[:200]}")
                elif ss == "caption_only" and len(caption_only_samples) < 10:
                    caption_only_samples.append(f"**{label}**: {caption[:150]}...")

        except Exception:
            pass

    # Build report
    caption_rate = round(total_with_caption / max(total_tables, 1) * 100, 1)

    lines = [
        "# Table Extraction Report — Phase 2A + 2B",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"- **Total papers processed**: {total_papers}",
        f"- **Papers with successful extraction**: {total_success}",
        f"- **Papers failed**: {total_failed}",
        f"- **Total table assets**: {total_tables}",
        f"- **Tables with captions**: {total_with_caption} ({caption_rate}%)",
        f"- **Tables with reference links**: {total_with_refs}",
        f"- **Linked result assets**: {total_linked_result}",
        f"- **Linked claim assets**: {total_linked_claim}",
        f"- **Linked evidence IDs**: {total_linked_evidence}",
        "",
        "## Phase 2B: Structure Extraction",
        "",
        "### Structure Status Distribution",
        "",
    ]
    for ss, cnt in structure_status_dist.most_common():
        pct = round(cnt / max(total_tables, 1) * 100, 1)
        lines.append(f"- **{ss}**: {cnt} ({pct}%)")

    lines.extend([
        "",
        "### Structure Confidence Distribution",
        "",
    ])
    for sc, cnt in structure_confidence_dist.most_common():
        lines.append(f"- **{sc}**: {cnt}")

    lines.extend([
        "",
        "### Structure Extraction Method Distribution",
        "",
    ])
    for sem, cnt in extraction_method_dist.most_common():
        lines.append(f"- **{sem}**: {cnt}")

    if row_counts:
        import statistics as _st
        lines.extend([
            "",
            "### Row Count Statistics",
            "",
            f"- Min: {min(row_counts)}",
            f"- Max: {max(row_counts)}",
            f"- Mean: {round(_st.mean(row_counts), 1)}",
            f"- Median: {round(_st.median(row_counts), 1)}",
        ])

    if col_counts:
        import statistics as _st2
        lines.extend([
            "",
            "### Column Count Statistics",
            "",
            f"- Min: {min(col_counts)}",
            f"- Max: {max(col_counts)}",
            f"- Mean: {round(_st2.mean(col_counts), 1)}",
            f"- Median: {round(_st2.median(col_counts), 1)}",
        ])

    lines.extend([
        "",
        f"### Simple Structure Samples ({len(simple_samples)})",
        "",
    ])
    if simple_samples:
        for s in simple_samples:
            lines.append(f"- {s}")
    else:
        lines.append("- (none)")

    lines.extend([
        "",
        f"### Complex Structure Skipped Samples ({len(complex_samples)})",
        "",
    ])
    if complex_samples:
        for s in complex_samples:
            lines.append(f"- {s}")
    else:
        lines.append("- (none)")

    lines.extend([
        "",
        f"### Caption-Only Samples ({len(caption_only_samples)})",
        "",
    ])
    if caption_only_samples:
        for s in caption_only_samples:
            lines.append(f"- {s}")
    else:
        lines.append("- (none)")

    lines.extend([
        "",
        "## Caption Source Distribution",
        "",
    ])
    for src, cnt in caption_source_dist.most_common():
        lines.append(f"- **{src}**: {cnt}")

    lines.extend([
        "",
        "## Caption Quality Distribution",
        "",
    ])
    for q, cnt in caption_quality_dist.most_common():
        lines.append(f"- **{q}**: {cnt}")

    lines.extend([
        "",
        "## Table Type Distribution",
        "",
    ])
    for tt, cnt in table_type_dist.most_common():
        lines.append(f"- **{tt}**: {cnt}")

    lines.extend([
        "",
        "## Table Caption Samples (10)",
        "",
    ])
    for s in caption_samples:
        lines.append(f"- {s}")

    lines.extend([
        "",
        "## No-Caption / Reference-Only Samples (10)",
        "",
    ])
    if no_caption_samples:
        for s in no_caption_samples:
            lines.append(f"- {s}")
    else:
        lines.append("- (none)")

    lines.extend([
        "",
        "## Failed Papers",
        "",
    ])
    if failed_papers:
        for fp in failed_papers:
            lines.append(f"- {fp}")
    else:
        lines.append("- (none)")

    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Report: {report_path}")


# ── Phase 2C: Supplementary Table Linking ──

def run_supplementary_linking(
    paper_id: str, root: Path | None = None, force: bool = False
) -> dict[str, Any]:
    """Build supplementary table links for a single paper."""
    if root is None:
        root = _get_project_root()
    from scientra.pdf_data_assets.supplementary_linker import SupplementaryLinker
    from scientra.pdf_data_assets.supplementary_preview import SupplementaryPreview
    from scientra.pdf_data_assets.schemas import SupplementaryTableLink
    from scientra.pdf_data_assets.agent_chunk_builder import AgentChunkBuilder
    from scientra.pdf_data_assets.asset_registry import AssetRegistry, RegistryEntry
    from scientra.pdf_data_assets.schemas import BuildStatus

    linker = SupplementaryLinker(root)
    previewer = SupplementaryPreview(root)
    chunk_builder = AgentChunkBuilder(root)
    registry = AssetRegistry(root)

    output_dir = root / "06_PDF_DataAssets" / "08_supplementary_links" / paper_id
    output_path = output_dir / "supplementary_links.json"

    print(f"\n=== Supplementary Linking: {paper_id} ===\n")

    try:
        # Find references
        refs = linker.find_all_references(paper_id)
        if not refs:
            print(f"  No supplementary references found")
            return {"paper_id": paper_id, "status": "success", "links": 0}

        # Match files
        refs = linker.match_files(paper_id, refs)

        # Build SupplementaryTableLinks
        timestamp = datetime.now(timezone.utc).isoformat()
        links: list[dict[str, Any]] = []

        for i, ref in enumerate(refs):
            # Try preview if file found
            matched_file = ref.get("matched_file")
            if matched_file and ref.get("content_status") == "file_found":
                preview = previewer.preview(matched_file)
                ref["content_status"] = preview.get("content_status", ref["content_status"])
                ref["preview_columns"] = preview.get("preview_columns", [])
                ref["preview_rows"] = preview.get("preview_rows", [])
                ref["row_count"] = preview.get("row_count", 0)
                ref["column_count"] = preview.get("column_count", 0)
                ref.setdefault("notes", []).extend(preview.get("notes", []))

            link = SupplementaryTableLink(
                asset_id=f"{paper_id}:suppl_table:{i:04d}",
                paper_id=paper_id,
                supplement_label=ref.get("supplement_label", "unknown"),
                supplement_number=ref.get("supplement_number", str(i)),
                referenced_as=ref.get("referenced_as", ""),
                reference_sentences=ref.get("reference_sentences", []),
                source_section=ref.get("source_section", "unknown"),
                source_text=ref.get("source_text", ""),
                linked_table_assets=ref.get("linked_table_assets", []),
                linked_result_assets=ref.get("linked_result_assets", []),
                linked_claim_assets=ref.get("linked_claim_assets", []),
                linked_evidence_ids=ref.get("linked_evidence_ids", []),
                candidate_files=ref.get("candidate_files", []),
                matched_file=ref.get("matched_file"),
                file_type=ref.get("file_type", "unknown"),
                match_confidence=ref.get("match_confidence", "none"),
                match_method=ref.get("match_method", "no_match"),
                content_status=ref.get("content_status", "link_only"),
                preview_columns=ref.get("preview_columns", []),
                preview_rows=ref.get("preview_rows", []),
                row_count=ref.get("row_count", 0),
                column_count=ref.get("column_count", 0),
                imported_file_id=ref.get("imported_file_id"),
                imported_file_name=ref.get("imported_file_name"),
                imported_relative_path=ref.get("imported_relative_path"),
                sheet_names=ref.get("sheet_names", []),
                preview_status=ref.get("preview_status", "none"),
                selected_sheet=ref.get("selected_sheet"),
                import_source=ref.get("import_source", "none"),
                confidence=ref.get("match_confidence", "low"),
                created_at=timestamp,
                notes=ref.get("notes", []),
            )
            links.append(link.model_dump(mode="json", exclude_none=False))

        # Write output
        output_dir.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(output_path)

        print(f"  Supplementary links: {len(links)} ({sum(1 for l in links if l.get('matched_file'))} matched)")

        # Regenerate chunks to include supplementary_table chunks
        chunks = chunk_builder.build(paper_id, force=True)
        print(f"  Chunks regenerated: {len(chunks)} (now includes supplementary_table chunks)")

        # Update registry
        entry = registry.get_entry(paper_id)
        if entry:
            entry.supplementary_links = len(links)
            registry.upsert_entry(entry)
            registry.update_totals()
        else:
            entry = RegistryEntry(
                paper_id=paper_id,
                supplementary_links=len(links),
                build_status=BuildStatus.success,
            )
            registry.upsert_entry(entry)
            registry.update_totals()

        print(f"\n[OK] Supplementary linking complete for {paper_id}")
        return {"paper_id": paper_id, "status": "success", "links": len(links),
                "matched": sum(1 for l in links if l.get("matched_file"))}
    except Exception as e:
        logger.error(f"Supplementary linking failed for {paper_id}: {e}")
        registry = AssetRegistry(root)
        entry = RegistryEntry(
            paper_id=paper_id,
            build_status=BuildStatus.failed,
            error_message=str(e),
        )
        registry.upsert_entry(entry)
        return {"paper_id": paper_id, "status": "failed", "error": str(e)}


def run_supplementary_linking_all(root: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Build supplementary links for all papers with evidence.json."""
    if root is None:
        root = _get_project_root()
    from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter

    adapter = EvidenceAdapter(root)
    paper_ids = adapter.list_paper_ids()
    results = []
    total_links = 0
    total_matched = 0
    total_success = 0
    total_failed = 0

    for pid in paper_ids:
        r = run_supplementary_linking(pid, root=root, force=force)
        results.append(r)
        if r["status"] == "success":
            total_success += 1
            total_links += r.get("links", 0)
            total_matched += r.get("matched", 0)
        else:
            total_failed += 1

    # Generate report
    _generate_supplementary_report(root, results, total_links, total_matched, total_success, total_failed)

    print(f"\n=== Supplementary Linking Complete ===")
    print(f"Papers: {len(paper_ids)} | Success: {total_success} | Failed: {total_failed}")
    print(f"Total links: {total_links} | Matched files: {total_matched}")
    return {"total": len(paper_ids), "total_links": total_links, "total_matched": total_matched,
            "success": total_success, "failed": total_failed, "results": results}


def _generate_supplementary_report(
    root: Path, results: list[dict[str, Any]], total_links: int, total_matched: int,
    total_success: int, total_failed: int
) -> None:
    """Generate supplementary linking report."""
    from collections import Counter

    report_path = root / "06_PDF_DataAssets" / "00_registry" / "supplementary_table_linking_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    content_status_dist: Counter = Counter()
    match_confidence_dist: Counter = Counter()
    file_type_dist: Counter = Counter()
    match_method_dist: Counter = Counter()
    papers_with_refs = 0
    papers_matched = 0
    total_previewed = 0
    link_samples: list[str] = []
    unmatched_refs: list[str] = []
    unmatched_files: list[str] = []
    failed_papers: list[str] = []

    for r in results:
        pid = r.get("paper_id", "unknown")
        if r.get("status") == "failed":
            failed_papers.append(f"{pid}: {r.get('error', 'unknown error')}")
            continue

        links = r.get("links", 0)
        matched = r.get("matched", 0)
        if links > 0:
            papers_with_refs += 1
        if matched > 0:
            papers_matched += 1

        # Load links to gather detailed stats
        link_path = root / "06_PDF_DataAssets" / "08_supplementary_links" / pid / "supplementary_links.json"
        if link_path.exists():
            try:
                link_data = json.loads(link_path.read_text(encoding="utf-8"))
                for l in link_data:
                    content_status_dist[l.get("content_status", "link_only")] += 1
                    match_confidence_dist[l.get("match_confidence", "none")] += 1
                    file_type_dist[l.get("file_type", "unknown")] += 1
                    match_method_dist[l.get("match_method", "no_match")] += 1
                    if l.get("content_status") == "simple_preview_extracted":
                        total_previewed += 1

                    label = l.get("supplement_label", "?")
                    if len(link_samples) < 20:
                        link_samples.append(
                            f"**{label}**: matched={l.get('matched_file','none')}, "
                            f"status={l.get('content_status','?')}, conf={l.get('match_confidence','?')}"
                        )
                    if not l.get("matched_file") and len(unmatched_refs) < 10:
                        unmatched_refs.append(
                            f"**{label}**: {l.get('referenced_as','')[:150]}"
                        )
            except Exception:
                pass

    # Build report
    lines = [
        "# Supplementary Table Linking Report — Phase 2C",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"- **Total papers processed**: {len(results)}",
        f"- **Papers with supplementary references**: {papers_with_refs}",
        f"- **Papers with matched files**: {papers_matched}",
        f"- **Papers failed**: {total_failed}",
        f"- **Total supplementary references**: {total_links}",
        f"- **Total matched files**: {total_matched}",
        f"- **Previews extracted**: {total_previewed}",
        "",
        "## Content Status Distribution",
        "",
    ]
    for cs, cnt in content_status_dist.most_common():
        lines.append(f"- **{cs}**: {cnt}")

    lines.extend(["", "## Match Confidence Distribution", ""])
    for mc, cnt in match_confidence_dist.most_common():
        lines.append(f"- **{mc}**: {cnt}")

    lines.extend(["", "## File Type Distribution", ""])
    for ft, cnt in file_type_dist.most_common():
        lines.append(f"- **{ft}**: {cnt}")

    lines.extend(["", "## Match Method Distribution", ""])
    for mm, cnt in match_method_dist.most_common():
        lines.append(f"- **{mm}**: {cnt}")

    lines.extend(["", "## Top 20 Supplementary Link Samples", ""])
    for s in link_samples:
        lines.append(f"- {s}")

    lines.extend(["", "## Unmatched References (10)", ""])
    if unmatched_refs:
        for u in unmatched_refs:
            lines.append(f"- {u}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Failed Papers", ""])
    if failed_papers:
        for fp in failed_papers:
            lines.append(f"- {fp}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Notes", "",
        "- All supplementary files referenced in papers are stored on publisher websites",
        "- Local supplementary files (xlsx, csv) are not available in the current project",
        "- Links are primarily 'link_only' or 'file_missing' status",
        "- To enable file preview, download supplementary files to the project directory",
    ])

    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Report: {report_path}")


# ── CLI ──

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scientra PDF Data Assets — Phase 0 + 0.5 Assetization & Quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Phase 0: Build
  python -m scientra.pdf_data_assets.build_assets --paper-id "example_paper_id_here"
  python -m scientra.pdf_data_assets.build_assets --all
  python -m scientra.pdf_data_assets.build_assets --all --force
  python -m scientra.pdf_data_assets.build_assets --status

  # Phase 0.5: Quality
  python -m scientra.pdf_data_assets.build_assets --quality-check --paper-id "example_paper_id..."
  python -m scientra.pdf_data_assets.build_assets --quality-check
  python -m scientra.pdf_data_assets.build_assets --export-samples
  python -m scientra.pdf_data_assets.build_assets --export-samples --paper-id "example_paper_id..."
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

    # Phase 2A
    parser.add_argument("--tables", action="store_true",
                        help="Build table assets (Phase 2A: Table Caption + Reference Extraction)")

    # Phase 2C
    parser.add_argument("--supplementary", action="store_true",
                        help="Build supplementary table links (Phase 2C: Supplementary Table Linking)")

    # Phase 2D
    parser.add_argument("--import-supplementary", action="store_true",
                        help="Import manual supplementary files from 00_Supplementary/inbox/ (Phase 2D)")

    # Phase 2E
    parser.add_argument("--supplementary-entities", action="store_true",
                        help="Index entities from high-confidence supplementary files (Phase 2E)")

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

    # Phase 2A: Table extraction
    if args.tables:
        if args.paper_id:
            run_table_extraction(args.paper_id, root=root, force=args.force)
        elif args.all:
            run_table_extraction_all(root=root, force=args.force)
        else:
            print("Use --tables with --paper-id or --all")
        return 0

    # Phase 2C: Supplementary Table Linking
    if args.supplementary:
        if args.paper_id:
            run_supplementary_linking(args.paper_id, root=root, force=args.force)
        elif args.all:
            run_supplementary_linking_all(root=root, force=args.force)
        else:
            print("Use --supplementary with --paper-id or --all")
        return 0

    # Phase 2D: Manual Supplementary File Import
    if args.import_supplementary:
        from scientra.pdf_data_assets.supplementary_importer import SupplementaryImporter
        importer = SupplementaryImporter(root)
        print("\n=== Manual Supplementary File Import ===\n")
        registry = importer.build_registry()
        print(f"Files found: {registry['total_files']}")
        print(f"Previewed:   {registry['previewed']}")
        print(f"Types:       {registry['file_types']}")
        print(f"\n[OK] Import registry saved to 00_Supplementary/registry/supplementary_files.json")
        return 0

    # Phase 2E: Supplementary Entity Indexing
    if args.supplementary_entities:
        from scientra.pdf_data_assets.supplementary_entity_indexer import SupplementaryEntityIndexer
        indexer = SupplementaryEntityIndexer(root)
        if args.paper_id:
            print(f"\n=== Entity Indexing: {args.paper_id} ===\n")
            links_path = root / "06_PDF_DataAssets" / "08_supplementary_links" / args.paper_id / "supplementary_links.json"
            entities = indexer.index_paper(args.paper_id, links_path)
            print(f"  Entities indexed: {len(entities)}")
            print(f"\n[OK] Entity indexing complete for {args.paper_id}")
        elif args.all:
            print("\n=== Supplementary Entity Indexing: ALL ===\n")
            stats = indexer.index_all()
            print(f"Papers with high-conf data: {stats['papers_with_high_conf']}")
            print(f"Papers skipped:            {stats['papers_skipped']}")
            print(f"Total entity records:      {stats['total_entity_records']}")
            print(f"Entity types:              {stats['entity_types']}")

            # Regenerate chunks for papers with entities to include supplementary_entity chunks
            if stats['papers_with_high_conf'] > 0:
                from scientra.pdf_data_assets.agent_chunk_builder import AgentChunkBuilder
                chunk_builder = AgentChunkBuilder(root)
                ent_dir = root / "06_PDF_DataAssets" / "09_supplementary_entities"
                for paper_dir in ent_dir.iterdir():
                    if paper_dir.is_dir() and (paper_dir / "supplementary_entities.json").exists():
                        chunks = chunk_builder.build(paper_dir.name, force=True)
                        print(f"  Chunks regenerated for {paper_dir.name[:50]}...: {len(chunks)} chunks")

            print(f"\n[OK] Entity indexing complete")
        else:
            print("Use --supplementary-entities with --paper-id or --all")
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
