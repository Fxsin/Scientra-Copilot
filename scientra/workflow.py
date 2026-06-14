from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal environments
    import logging

    class _LoggerCompat:
        def __init__(self) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
            self._logger = logging.getLogger("scientra.workflow_runner")

        def remove(self) -> None:
            return None

        def add(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def info(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.info(format_log(message, *args, **kwargs))

        def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.warning(format_log(message, *args, **kwargs))

        def error(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.error(format_log(message, *args, **kwargs))

    def format_log(message: str, *args: Any, **kwargs: Any) -> str:
        try:
            return message.format(*args, **kwargs)
        except Exception:
            return message

    logger = _LoggerCompat()


def _detect_project_root() -> Path:
    """Walk up from this file until a 'Config/workflow_config.yaml' is found."""
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    # Fallback to the scientra/ directory's parent
    return Path(__file__).resolve().parent.parent


WORKFLOW_RUNNER_VERSION = "0.1.0"
PROJECT_ROOT = _detect_project_root()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "Config" / "workflow_config.yaml"
STEP_ORDER = [
    "import_pdf",
    "parse",
    "metadata",
    "tag",
    "summary",
    "hybrid_parse",
    "evidence",
    "evidence_chunks",
    "ai_summary_v2",
    "ai_evidence_enrichment",
    "ai_gap_extraction",
    "ai_hypothesis_generation",
    "embedding",
    "lancedb",
    "index_update",
]


@dataclass(frozen=True)
class WorkflowOptions:
    config_path: Path
    root: Path
    file: Path | None
    input_dir: Path | None
    changed_only: bool
    resume: bool
    force: bool
    dry_run: bool
    from_step: str | None
    to_step: str | None


@dataclass(frozen=True)
class ImportedPdf:
    source_path: Path
    target_path: Path
    sha256: str
    changed: bool


@dataclass(frozen=True)
class StepResult:
    step: str
    status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    command: list[str] | None = None
    returncode: int | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    error: str | None = None


class WorkflowRunner:
    def __init__(self, config: dict[str, Any], options: WorkflowOptions) -> None:
        self.config = config
        self.options = options
        self.root = options.root
        self.paths = resolve_paths(config, self.root)
        self.state_path = self.paths["state_path"]
        self.failure_path = self.paths["failure_path"]
        self.report_dir = self.paths["report_dir"]
        self.log_dir = self.paths["log_dir"]
        self.state = self.load_state()

    def run(self) -> dict[str, Any]:
        self.ensure_directories()
        selected_steps = self.selected_steps()
        imported = self.import_inputs()
        changed_inputs = [item for item in imported if item.changed]

        if self.options.changed_only and imported and not changed_inputs and not self.options.force:
            report = self.write_report(
                run_status="skipped",
                imported=imported,
                step_results=[],
                reason="changed_only requested and no input PDF changed",
            )
            return report

        if self.options.resume:
            selected_steps = self.apply_resume(selected_steps)

        step_results: list[StepResult] = []
        run_status = "succeeded"
        for step in selected_steps:
            result = self.run_step(step, imported)
            step_results.append(result)
            self.mark_step(step, result)
            if result.status == "failed":
                self.record_failure(step, result)
                run_status = "failed"
                if self.should_stop_on_failure(step):
                    break

        return self.write_report(
            run_status=run_status,
            imported=imported,
            step_results=step_results,
            reason=None,
        )

    def import_inputs(self) -> list[ImportedPdf]:
        if not self.step_enabled("import_pdf"):
            return []

        sources = self.collect_input_pdfs()

        # When no explicit sources are provided (inbox empty, no --file/--input-dir),
        # discover PDFs already present in pdf_dir (01_PDF) and register them.
        if not sources:
            pdf_dir = self.paths["pdf_dir"]
            if pdf_dir.exists():
                existing = sorted(pdf_dir.glob("*.pdf"))
                if existing:
                    logger.info(
                        "No inbox PDFs provided; registering {} existing PDF(s) from {}",
                        len(existing),
                        pdf_dir,
                    )
                sources = existing

        imported: list[ImportedPdf] = []
        for source in sources:
            # If the source is already inside pdf_dir, use it as both source & target
            if source.parent.resolve() == self.paths["pdf_dir"].resolve():
                target = source
            else:
                target = self.paths["pdf_dir"] / source.name
            source_hash = file_sha256(source)
            previous = self.state.get("pdfs", {}).get(str(target))
            changed = previous is None or previous.get("sha256") != source_hash or not target.exists()
            if self.options.dry_run:
                imported.append(ImportedPdf(source, target, source_hash, changed))
                continue
            if changed or self.options.force:
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != target.resolve():
                    shutil.copy2(source, target)
            imported.append(ImportedPdf(source, target, source_hash, changed))
            self.state.setdefault("pdfs", {})[str(target)] = {
                "source_path": str(source),
                "target_path": str(target),
                "sha256": source_hash,
                "updated_at": utc_now(),
            }
        self.save_state()
        return imported

    def run_step(self, step: str, imported: list[ImportedPdf]) -> StepResult:
        started = time.perf_counter()
        started_at = utc_now()
        step_config = self.config.get("steps", {}).get(step, {})
        logger.info("Workflow step started: {}", step)

        if self.options.dry_run:
            return StepResult(
                step=step,
                status="dry_run",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                command=self.build_step_command(step) if step_config.get("command") else None,
            )

        try:
            if step == "import_pdf":
                status = "succeeded"
                return StepResult(
                    step=step,
                    status=status,
                    started_at=started_at,
                    finished_at=utc_now(),
                    duration_seconds=round(time.perf_counter() - started, 3),
                    error=None if imported else "no input PDFs provided; existing 01_PDF will be used",
                )

            builtin = step_config.get("builtin")
            if builtin:
                return self.run_builtin_step(step, builtin, started_at, started)

            command = self.build_step_command(step)
            timeout = int(step_config.get("timeout_seconds") or self.config.get("runtime", {}).get("default_timeout_seconds") or 3600)
            completed = subprocess.run(
                command,
                cwd=str(self.root),
                text=True,
                capture_output=True,
                timeout=timeout,
                env=self.command_env(),
            )
            status = "succeeded" if completed.returncode == 0 else "failed"
            return StepResult(
                step=step,
                status=status,
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                command=command,
                returncode=completed.returncode,
                stdout_tail=tail_text(completed.stdout),
                stderr_tail=tail_text(completed.stderr),
                error=None if status == "succeeded" else f"command returned {completed.returncode}",
            )
        except Exception as exc:
            return StepResult(
                step=step,
                status="failed",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                command=self.build_step_command(step) if step_config.get("command") else None,
                error=f"{type(exc).__name__}: {exc}",
            )

    def run_builtin_step(
        self,
        step: str,
        builtin: str,
        started_at: str,
        started: float,
    ) -> StepResult:
        if builtin == "verify_lancedb":
            report_path = self.paths["vector_db_dir"].parent / "embedding_report.json"
            status = "succeeded" if report_path.exists() else "failed"
            error = None if status == "succeeded" else f"embedding report not found: {report_path}"
        elif builtin == "hybrid_parse":
            return self._run_hybrid_parse_builtin(started_at, started)
        elif builtin == "index_update":
            self.write_index_update()
            status = "succeeded"
            error = None
        elif builtin == "ai_summary_v2":
            return self._run_ai_summary_v2_builtin(started_at, started)
        elif builtin == "ai_evidence_enrichment":
            return self._run_ai_evidence_enrichment_builtin(started_at, started)
        elif builtin == "ai_gap_extraction":
            return self._run_ai_gap_extraction_builtin(started_at, started)
        elif builtin == "ai_hypothesis_generation":
            return self._run_ai_hypothesis_generation_builtin(started_at, started)
        else:
            status = "failed"
            error = f"unknown builtin step: {builtin}"

        return StepResult(
            step=step,
            status=status,
            started_at=started_at,
            finished_at=utc_now(),
            duration_seconds=round(time.perf_counter() - started, 3),
            error=error,
        )

    def _run_hybrid_parse_builtin(
        self,
        started_at: str,
        started: float,
    ) -> StepResult:
        """Builtin: run hybrid parser on all imported PDFs.

        Only runs when hybrid_parser.enabled is True in workflow_config.yaml.
        When disabled, the step is skipped gracefully with status="skipped".

        Each PDF in pdf_dir (01_PDF or legacy 01_Sources/papers/) is processed
        through the hyrid parser pipeline: PyMuPDF scan → GROBID + OpenDataLoader
        → quality score → Marker fallback → merge → manifest.
        """
        hybrid_config = self.config.get("hybrid_parser", {})
        hybrid_enabled = hybrid_config.get("enabled", False)

        if not hybrid_enabled:
            logger.info("Hybrid parser is disabled (hybrid_parser.enabled=false). Skipping.")
            return StepResult(
                step="hybrid_parse",
                status="skipped",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error="Hybrid parser disabled by config. Set hybrid_parser.enabled=true to enable.",
            )

        try:
            from scientra.parsers.parser_router import run_hybrid_parse

            pdf_dir = self.paths["pdf_dir"]
            # Also check legacy 01_Sources/papers/ path
            legacy_pdf_dir = self.root / "01_Sources" / "papers"
            pdf_paths: list[Path] = []

            if pdf_dir.exists():
                pdf_paths.extend(sorted(pdf_dir.glob("*.pdf")))
            if legacy_pdf_dir.exists():
                pdf_paths.extend(sorted(legacy_pdf_dir.glob("**/*.pdf")))

            if not pdf_paths:
                return StepResult(
                    step="hybrid_parse",
                    status="skipped",
                    started_at=started_at,
                    finished_at=utc_now(),
                    duration_seconds=round(time.perf_counter() - started, 3),
                    error="No PDFs found to parse.",
                )

            success_count = 0
            skip_count = 0
            fail_count = 0
            errors: list[str] = []

            for pdf_path in pdf_paths:
                # Derive paper_id from filename
                paper_id = pdf_path.stem
                try:
                    result = run_hybrid_parse(
                        pdf_path=pdf_path,
                        paper_id=paper_id,
                        config=hybrid_config,
                        output_root=self.root,
                    )
                    if result.manifest_path:
                        success_count += 1
                    elif result.warnings and any(
                        "disabled" in w.lower() for w in result.warnings
                    ):
                        skip_count += 1
                    else:
                        fail_count += 1
                        if result.errors:
                            errors.extend(result.errors[:3])
                except Exception as exc:
                    fail_count += 1
                    errors.append(f"{paper_id}: {exc}")

            status = "succeeded"
            error_msg = None
            if fail_count > 0 and success_count == 0:
                status = "failed"
                error_msg = f"All {fail_count} PDF(s) failed hybrid parsing."
                if errors:
                    error_msg += f" First errors: {'; '.join(errors[:3])}"
            elif fail_count > 0:
                error_msg = f"{success_count} succeeded, {fail_count} failed, {skip_count} skipped."
                if errors:
                    error_msg += f" Errors: {'; '.join(errors[:3])}"

            logger.info(
                "Hybrid parse complete: {} succeeded, {} failed, {} skipped",
                success_count, fail_count, skip_count,
            )

            return StepResult(
                step="hybrid_parse",
                status=status,
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=error_msg,
            )

        except Exception as exc:
            return StepResult(
                step="hybrid_parse",
                status="failed",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=f"Hybrid parser error: {type(exc).__name__}: {exc}",
            )

    def _run_ai_summary_v2_builtin(
        self,
        started_at: str,
        started: float,
        limit: int | None = None,
    ) -> StepResult:
        """Builtin: generate AI-enhanced Summary V2 for all papers.

        Reads evidence_chunks.json and paper text, generates structured summary
        via LLM Gateway. Output written to 03_Assets/ai/summary_v2/.

        Gated by ai_enrichment.enabled and ai_enrichment.summary_v2.
        """
        ai_config = self.config.get("ai_enrichment", {})
        ai_enabled = ai_config.get("enabled", False)
        summary_v2_enabled = ai_config.get("summary_v2", False)
        paper_limit = ai_config.get("paper_limit", 0) or None

        if not ai_enabled or not summary_v2_enabled:
            logger.info("AI Summary V2 is disabled. Skipping.")
            return StepResult(
                step="ai_summary_v2",
                status="skipped",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error="AI enrichment disabled. Set ai_enrichment.enabled=true and ai_enrichment.summary_v2=true.",
            )

        try:
            from scientra.ai.summary_v2 import generate_summary_v2

            evidence_dir = self.root / "03_Evidence"
            metadata_dir = self.root / "02_Metadata" / "yaml"

            if not evidence_dir.exists():
                return StepResult(
                    step="ai_summary_v2",
                    status="skipped",
                    started_at=started_at,
                    finished_at=utc_now(),
                    duration_seconds=round(time.perf_counter() - started, 3),
                    error="No evidence directory found.",
                )

            import yaml

            generated = 0
            skipped_chunks = 0
            failed = 0
            paper_ids = sorted(
                d.name for d in evidence_dir.iterdir()
                if d.is_dir() and (d / "evidence_chunks.json").exists()
            )
            if limit:
                paper_ids = paper_ids[:limit]

            for pid in paper_ids:
                try:
                    chunks_path = evidence_dir / pid / "evidence_chunks.json"
                    chunks_data = json.loads(
                        chunks_path.read_text(encoding="utf-8")
                    )
                    chunks = chunks_data.get("chunks", [])

                    # Load metadata
                    metadata: dict[str, Any] = {}
                    meta_yaml = metadata_dir / f"{pid}.metadata.yaml"
                    if meta_yaml.exists():
                        metadata = yaml.safe_load(
                            meta_yaml.read_text(encoding="utf-8")
                        ) or {}

                    # Load paper text (try multiple sources)
                    text = ""
                    raw_text = evidence_dir / pid / "sections.json"
                    if raw_text.exists():
                        sections = json.loads(
                            raw_text.read_text(encoding="utf-8")
                        )
                        text = "\n\n".join(
                            s.get("text", "")
                            for s in sections.get("sections", [])
                        )[:24000]
                    if not text:
                        meta_json = metadata_dir.parent / "json" / f"{pid}.metadata.json"
                        if meta_json.exists():
                            meta_data = json.loads(
                                meta_json.read_text(encoding="utf-8")
                            )
                            text = meta_data.get("abstract", "") or ""

                    result = generate_summary_v2(
                        paper_id=pid,
                        text=text,
                        metadata=metadata,
                        evidence_chunks=chunks if chunks else None,
                    )

                    if result.get("status") == "generated":
                        generated += 1
                    elif result.get("status") == "skipped":
                        skipped_chunks += 1
                    else:
                        failed += 1

                except Exception as exc:
                    logger.error(f"Summary V2 failed for {pid}: {exc}")
                    failed += 1

            status = "succeeded" if failed == 0 else "partial"
            return StepResult(
                step="ai_summary_v2",
                status=status,
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=(
                    f"generated={generated}, skipped={skipped_chunks}, "
                    f"failed={failed}, total={len(paper_ids)}"
                ) if failed > 0 else None,
            )

        except Exception as exc:
            return StepResult(
                step="ai_summary_v2",
                status="failed",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=f"AI Summary V2 error: {type(exc).__name__}: {exc}",
            )

    def _run_ai_evidence_enrichment_builtin(
        self,
        started_at: str,
        started: float,
        limit: int | None = None,
    ) -> StepResult:
        """Builtin: enrich evidence chunks with AI analysis for all papers.

        Gated by ai_enrichment.enabled and ai_enrichment.evidence_enrichment.
        """
        ai_config = self.config.get("ai_enrichment", {})
        ai_enabled = ai_config.get("enabled", False)
        enrichment_enabled = ai_config.get("evidence_enrichment", False)
        batch_size = ai_config.get("batch_size", 8)
        max_chunks = ai_config.get("max_chunks_per_paper", 40)
        min_chunk_length = ai_config.get("min_chunk_length", 80)
        paper_limit = ai_config.get("paper_limit", 0) or None

        if not ai_enabled or not enrichment_enabled:
            logger.info("AI Evidence Enrichment is disabled. Skipping.")
            return StepResult(
                step="ai_evidence_enrichment",
                status="skipped",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error="AI enrichment disabled. Set ai_enrichment.enabled=true and ai_enrichment.evidence_enrichment=true.",
            )

        try:
            from scientra.ai.evidence_enrichment import enrich_evidence_chunks

            evidence_dir = self.root / "03_Evidence"
            if not evidence_dir.exists():
                return StepResult(
                    step="ai_evidence_enrichment",
                    status="skipped",
                    started_at=started_at,
                    finished_at=utc_now(),
                    duration_seconds=round(time.perf_counter() - started, 3),
                    error="No evidence directory found.",
                )

            generated = 0
            skipped = 0
            failed = 0
            paper_ids = sorted(
                d.name for d in evidence_dir.iterdir()
                if d.is_dir() and (d / "evidence_chunks.json").exists()
            )
            if limit:
                paper_ids = paper_ids[:limit]

            for pid in paper_ids:
                try:
                    result = enrich_evidence_chunks(
                        paper_id=pid,
                        batch_size=batch_size,
                        max_chunks=max_chunks,
                        min_chunk_length=min_chunk_length,
                    )

                    status = result.get("status", "")
                    if status == "enriched":
                        generated += 1
                    elif status == "skipped":
                        skipped += 1
                    else:
                        failed += 1

                except Exception as exc:
                    logger.error(f"Evidence enrichment failed for {pid}: {exc}")
                    failed += 1

            overall = "succeeded" if failed == 0 else "partial"
            return StepResult(
                step="ai_evidence_enrichment",
                status=overall,
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=(
                    f"generated={generated}, skipped={skipped}, "
                    f"failed={failed}, total={len(paper_ids)}"
                ) if failed > 0 else None,
            )

        except Exception as exc:
            return StepResult(
                step="ai_evidence_enrichment",
                status="failed",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=f"Evidence enrichment error: {type(exc).__name__}: {exc}",
            )

    def _run_ai_gap_extraction_builtin(
        self,
        started_at: str,
        started: float,
    ) -> StepResult:
        """Builtin: extract research gaps from Summary V2 and Evidence Enrichment.

        Gated by ai_enrichment.enabled and ai_enrichment.gap_extraction.
        """
        ai_config = self.config.get("ai_enrichment", {})
        ai_enabled = ai_config.get("enabled", False)
        gap_enabled = ai_config.get("gap_extraction", False)
        max_gaps = ai_config.get("max_gaps_per_paper", 8)
        paper_limit = ai_config.get("paper_limit", 0) or None

        if not ai_enabled or not gap_enabled:
            logger.info("AI Gap Extraction is disabled. Skipping.")
            return StepResult(
                step="ai_gap_extraction",
                status="skipped",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error="AI enrichment disabled. Set ai_enrichment.enabled=true and ai_enrichment.gap_extraction=true.",
            )

        try:
            from scientra.ai.gap_extraction import extract_research_gaps

            evidence_dir = self.root / "03_Evidence"
            if not evidence_dir.exists():
                return StepResult(
                    step="ai_gap_extraction", status="skipped",
                    started_at=started_at, finished_at=utc_now(),
                    duration_seconds=round(time.perf_counter() - started, 3),
                    error="No evidence directory found.",
                )

            paper_ids = sorted(
                d.name for d in evidence_dir.iterdir()
                if d.is_dir() and (d / "evidence_chunks.json").exists()
            )
            if paper_limit:
                paper_ids = paper_ids[:paper_limit]

            generated = 0
            failed = 0
            for pid in paper_ids:
                try:
                    result = extract_research_gaps(paper_id=pid, max_gaps=max_gaps)
                    if result.get("status") == "generated":
                        generated += 1
                    else:
                        failed += 1
                except Exception as exc:
                    logger.error(f"Gap extraction failed for {pid}: {exc}")
                    failed += 1

            overall = "succeeded" if failed == 0 else "partial"
            return StepResult(
                step="ai_gap_extraction", status=overall,
                started_at=started_at, finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=(
                    f"generated={generated}, failed={failed}, total={len(paper_ids)}"
                ) if failed > 0 else None,
            )

        except Exception as exc:
            return StepResult(
                step="ai_gap_extraction", status="failed",
                started_at=started_at, finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=f"Gap extraction error: {type(exc).__name__}: {exc}",
            )

    def _run_ai_hypothesis_generation_builtin(
        self,
        started_at: str,
        started: float,
    ) -> StepResult:
        """Builtin: generate hypotheses from identified gaps.

        Gated by ai_enrichment.enabled and ai_enrichment.hypothesis_generation.
        """
        ai_config = self.config.get("ai_enrichment", {})
        ai_enabled = ai_config.get("enabled", False)
        hyp_enabled = ai_config.get("hypothesis_generation", False)
        max_hyps = ai_config.get("max_hypotheses_per_paper", 8)
        paper_limit = ai_config.get("paper_limit", 0) or None

        if not ai_enabled or not hyp_enabled:
            logger.info("AI Hypothesis Generation is disabled. Skipping.")
            return StepResult(
                step="ai_hypothesis_generation",
                status="skipped",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error="AI enrichment disabled. Set ai_enrichment.enabled=true and ai_enrichment.hypothesis_generation=true.",
            )

        try:
            from scientra.ai.hypothesis_generation import generate_hypotheses

            evidence_dir = self.root / "03_Evidence"
            if not evidence_dir.exists():
                return StepResult(
                    step="ai_hypothesis_generation", status="skipped",
                    started_at=started_at, finished_at=utc_now(),
                    duration_seconds=round(time.perf_counter() - started, 3),
                    error="No evidence directory found.",
                )

            paper_ids = sorted(
                d.name for d in evidence_dir.iterdir()
                if d.is_dir() and (d / "evidence_chunks.json").exists()
            )
            if paper_limit:
                paper_ids = paper_ids[:paper_limit]

            generated = 0
            failed = 0
            for pid in paper_ids:
                try:
                    result = generate_hypotheses(paper_id=pid, max_hypotheses=max_hyps)
                    if result.get("status") == "generated":
                        generated += 1
                    else:
                        failed += 1
                except Exception as exc:
                    logger.error(f"Hypothesis generation failed for {pid}: {exc}")
                    failed += 1

            overall = "succeeded" if failed == 0 else "partial"
            return StepResult(
                step="ai_hypothesis_generation", status=overall,
                started_at=started_at, finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=(
                    f"generated={generated}, failed={failed}, total={len(paper_ids)}"
                ) if failed > 0 else None,
            )

        except Exception as exc:
            return StepResult(
                step="ai_hypothesis_generation", status="failed",
                started_at=started_at, finished_at=utc_now(),
                duration_seconds=round(time.perf_counter() - started, 3),
                error=f"Hypothesis generation error: {type(exc).__name__}: {exc}",
            )

    def build_step_command(self, step: str) -> list[str]:
        step_config = self.config.get("steps", {}).get(step, {})
        command_config = step_config.get("command")
        if not command_config:
            raise ValueError(f"step has no command: {step}")

        python_exe = self.config.get("runtime", {}).get("python") or sys.executable
        command = [python_exe]
        if self.config.get("runtime", {}).get("python_no_bytecode", True):
            command.append("-B")
        module = command_config.get("module")
        script = command_config.get("script")
        if step == "summary":
            module = self._resolve_summary_module()
        if module:
            command.extend(["-m", str(module)])
        elif script:
            command.append(str(self.root / script))
        else:
            raise ValueError(f"step command must define module or script: {step}")

        args = list(command_config.get("args") or [])
        args = self.expand_args_for_step(step, args)
        command.extend(args)
        return command

    def _resolve_summary_module(self) -> str:
        """Resolve summary module based on summary.mode in config.

        mode == "agent"      → scientra.summary
        mode == "direct_api" → scientra.summary_engine
        """
        summary_config = self.config.get("steps", {}).get("summary", {})
        mode = summary_config.get("mode", "agent")
        fallback = summary_config.get("fallback_mode", "direct_api")
        if mode == "agent":
            return "scientra.summary"
        elif mode == "direct_api":
            return "scientra.summary_engine"
        else:
            logger.warning("Unknown summary.mode '{}', falling back to {}", mode, fallback)
            if fallback == "agent":
                return "scientra.summary"
            return "scientra.summary_engine"

    def expand_args_for_step(self, step: str, args: list[str]) -> list[str]:
        expanded = list(args)
        if step == "parse":
            expanded.extend(["--input-dir", str(self.paths["pdf_dir"])])
            expanded.extend(["--metadata-dir", str(self.paths["metadata_dir"])])
            expanded.extend(["--raw-text-dir", str(self.paths["summary_dir"] / "raw_text")])
            expanded.extend(["--log-dir", str(self.log_dir)])
            if self.options.force and "--force" not in expanded:
                expanded.append("--force")
        elif step == "metadata":
            expanded.extend(["--papers-dir", str(self.paths["metadata_dir"] / "papers")])
            expanded.extend(["--raw-text-dir", str(self.paths["summary_dir"] / "raw_text")])
            expanded.extend(["--output-dir", str(self.paths["metadata_dir"] / "yaml")])
            expanded.extend(["--aggregate-path", str(self.paths["metadata_dir"] / "metadata.yaml")])
            expanded.extend(["--log-dir", str(self.log_dir)])
            if self.options.force and "--force" not in expanded:
                expanded.append("--force")
        elif step == "tag":
            expanded.extend(["--root", str(self.root)])
            if self.options.changed_only and "--changed-only" not in expanded:
                expanded.append("--changed-only")
        elif step == "evidence_chunks":
            expanded.extend(["--root", str(self.root)])
            if self.options.force and "--force" not in expanded:
                expanded.append("--force")
        elif step == "summary":
            expanded.extend(["--root", str(self.root)])
            if self.options.force and "--force" not in expanded:
                expanded.append("--force")
        elif step == "embedding":
            expanded.extend(["--root", str(self.root)])
            expanded.extend(["--db-dir", str(self.paths["vector_db_dir"])])
            if self.options.force and "--force" not in expanded:
                expanded.append("--force")
        return expanded

    def collect_input_pdfs(self) -> list[Path]:
        sources: list[Path] = []
        if self.options.file:
            sources.append(self.options.file)
        if self.options.input_dir:
            sources.extend(sorted(self.options.input_dir.glob("*.pdf")))
        if not sources:
            inbox = self.paths["inbox_dir"]
            if inbox.exists():
                sources.extend(sorted(inbox.glob("*.pdf")))
        valid = []
        for path in sources:
            if path.exists() and path.is_file() and path.suffix.lower() == ".pdf":
                valid.append(path.resolve())
        return unique_paths(valid)

    def selected_steps(self) -> list[str]:
        start_index = STEP_ORDER.index(self.options.from_step) if self.options.from_step else 0
        end_index = STEP_ORDER.index(self.options.to_step) if self.options.to_step else len(STEP_ORDER) - 1
        selected = STEP_ORDER[start_index : end_index + 1]
        return [step for step in selected if self.step_enabled(step)]

    def apply_resume(self, steps: list[str]) -> list[str]:
        last_failed = self.state.get("last_failed_step")
        if last_failed and last_failed in steps:
            return steps[steps.index(last_failed) :]
        return steps

    def step_enabled(self, step: str) -> bool:
        return bool(self.config.get("steps", {}).get(step, {}).get("enabled", False))

    def should_stop_on_failure(self, step: str) -> bool:
        step_config = self.config.get("steps", {}).get(step, {})
        if step_config.get("optional") and self.config.get("runtime", {}).get("continue_on_optional_failure", True):
            return False
        return bool(self.config.get("runtime", {}).get("stop_on_failure", True))

    def mark_step(self, step: str, result: StepResult) -> None:
        self.state.setdefault("steps", {})[step] = {
            "status": result.status,
            "updated_at": result.finished_at,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
        }
        if result.status == "failed":
            self.state["last_failed_step"] = step
        elif self.state.get("last_failed_step") == step:
            self.state["last_failed_step"] = None
        self.state["updated_at"] = utc_now()
        self.save_state()

    def write_index_update(self) -> None:
        index_report = {
            "workflow_runner_version": WORKFLOW_RUNNER_VERSION,
            "workflow_version": self.config.get("workflow_version"),
            "updated_at": utc_now(),
            "metadata_yaml": str(self.paths["metadata_dir"] / "metadata.yaml"),
            "tag_dir": str(self.paths["index_dir"] / "tags"),
            "summary_dir": str(self.paths["summary_dir"]),
            "vector_db_dir": str(self.paths["vector_db_dir"]),
            "agent_entrypoint": "literature_query",
        }
        path = self.paths["index_dir"] / "workflow_index_update.json"
        write_json_atomic(path, index_report)

    def write_report(
        self,
        run_status: str,
        imported: list[ImportedPdf],
        step_results: list[StepResult],
        reason: str | None,
    ) -> dict[str, Any]:
        report = {
            "workflow_runner_version": WORKFLOW_RUNNER_VERSION,
            "workflow_version": self.config.get("workflow_version"),
            "status": run_status,
            "reason": reason,
            "generated_at": utc_now(),
            "imported_pdfs": [imported_pdf_to_dict(item) for item in imported],
            "steps": [step_result_to_dict(result) for result in step_results],
            "policy": self.config.get("policy", {}),
        }
        self.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.report_dir / "workflow_report.json"
        write_json_atomic(report_path, report)
        self.state["last_report_path"] = str(report_path)
        self.save_state()
        return report

    def record_failure(self, step: str, result: StepResult) -> None:
        payload = {
            "timestamp": utc_now(),
            "step": step,
            "result": step_result_to_dict(result),
        }
        self.failure_path.parent.mkdir(parents=True, exist_ok=True)
        with self.failure_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": WORKFLOW_RUNNER_VERSION, "pdfs": {}, "steps": {}}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.state_path.with_suffix(".corrupt.json")
            self.state_path.replace(backup)
            return {"version": WORKFLOW_RUNNER_VERSION, "pdfs": {}, "steps": {}}

    def save_state(self) -> None:
        self.state["version"] = WORKFLOW_RUNNER_VERSION
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self.state_path, self.state)

    def ensure_directories(self) -> None:
        for path in [
            self.paths["inbox_dir"],
            self.paths["pdf_dir"],
            self.paths["metadata_dir"],
            self.paths["summary_dir"],
            self.paths["vector_db_dir"],
            self.paths["index_dir"],
            self.paths["workflow_dir"],
            self.log_dir,
            self.report_dir,
            self.failure_path.parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def command_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Ensure `python -m scientra.xxx` can find the scientra package
        existing_path = env.get("PYTHONPATH", "")
        project_root = str(self.root)
        if existing_path:
            env["PYTHONPATH"] = project_root + os.pathsep + existing_path
        else:
            env["PYTHONPATH"] = project_root
        return env


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_paths(config: dict[str, Any], root: Path) -> dict[str, Path]:
    raw_paths = config.get("paths", {})

    def resolve(name: str, default: str) -> Path:
        value = raw_paths.get(name) or default
        path = Path(str(value))
        if not path.is_absolute():
            path = root / path
        return path.resolve()

    return {
        "root": root,
        "inbox_dir": resolve("inbox_dir", "00_Inbox"),
        "pdf_dir": resolve("pdf_dir", "01_PDF"),
        "metadata_dir": resolve("metadata_dir", "02_Metadata"),
        "summary_dir": resolve("summary_dir", "03_Summary"),
        "vector_db_dir": resolve("vector_db_dir", "04_VectorDB/lancedb"),
        "index_dir": resolve("index_dir", "05_Index"),
        "workflow_dir": resolve("workflow_dir", "07_Workflows"),
        "log_dir": resolve("log_dir", "07_Workflows/logs"),
        "report_dir": resolve("report_dir", "07_Workflows/reports"),
        "state_path": resolve("state_path", "07_Workflows/workflow_state.json"),
        "failure_path": resolve("failure_path", "07_Workflows/workflow_failures.jsonl"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Scientra Copilot PDF -> Parse -> Metadata -> Tag -> Summary -> Embedding -> LanceDB workflow.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run the workflow.")
    run_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    run_parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    run_parser.add_argument("--file", type=Path, default=None)
    run_parser.add_argument("--input-dir", type=Path, default=None)
    run_parser.add_argument("--changed-only", action="store_true")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--from-step", choices=STEP_ORDER, default=None)
    run_parser.add_argument("--to-step", choices=STEP_ORDER, default=None)
    run_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show workflow state.")
    status_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    status_parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    status_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    root = args.root.resolve()
    configure_logging(root)

    if args.command == "status":
        paths = resolve_paths(config, root)
        state = {}
        if paths["state_path"].exists():
            state = json.loads(paths["state_path"].read_text(encoding="utf-8"))
        if args.json:
            print(json.dumps(state, ensure_ascii=False, indent=2))
        else:
            print(yaml.safe_dump(state, allow_unicode=True, sort_keys=False))
        return 0

    options = WorkflowOptions(
        config_path=args.config.resolve(),
        root=root,
        file=args.file.resolve() if args.file else None,
        input_dir=args.input_dir.resolve() if args.input_dir else None,
        changed_only=args.changed_only,
        resume=args.resume,
        force=args.force,
        dry_run=args.dry_run,
        from_step=args.from_step,
        to_step=args.to_step,
    )
    runner = WorkflowRunner(config, options)
    report = runner.run()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 1 if report.get("status") == "failed" else 0


def configure_logging(root: Path) -> Path:
    log_dir = root / "07_Workflows" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"workflow_runner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    try:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(log_path, level="INFO", rotation="10 MB", retention=20, encoding="utf-8")
    except AttributeError:
        pass
    return log_path


def imported_pdf_to_dict(item: ImportedPdf) -> dict[str, Any]:
    return {
        "source_path": str(item.source_path),
        "target_path": str(item.target_path),
        "sha256": item.sha256,
        "changed": item.changed,
    }


def step_result_to_dict(result: StepResult) -> dict[str, Any]:
    return {
        "step": result.step,
        "status": result.status,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_seconds": result.duration_seconds,
        "command": result.command,
        "returncode": result.returncode,
        "stdout_tail": result.stdout_tail,
        "stderr_tail": result.stderr_tail,
        "error": result.error,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Retry on Windows where file locks may cause PermissionError
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            temp_path.replace(path)
            return
        except PermissionError:
            if attempt == max_attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


def tail_text(value: str | None, max_chars: int = 3000) -> str | None:
    if not value:
        return None
    return value[-max_chars:]


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())

