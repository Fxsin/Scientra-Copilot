from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WORKFLOW_DIR.parents[0]
SCRIPTS_DIR = PROJECT_ROOT / "Scripts"
sys.path.insert(0, str(WORKFLOW_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "06_API"))
sys.path.insert(0, str(PROJECT_ROOT / "08_Agent_Interface"))

from workflow_models import (  # noqa: E402
    STAGES,
    WORKFLOW_VERSION,
    PaperWorkflowItem,
    PaperWorkflowResult,
    StageResult,
    WorkflowOptions,
    is_success_status,
)
from workflow_state import DEFAULT_STATE_PATH, WorkflowStateStore  # noqa: E402


DEFAULT_CONFIG_PATH = WORKFLOW_DIR / "workflow_config.yaml"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "05_Index" / "workflow_test_report.md"


class WorkflowRunner:
    def __init__(
        self,
        options: WorkflowOptions,
        config: dict[str, Any] | None = None,
        state_path: str | Path = DEFAULT_STATE_PATH,
    ) -> None:
        self.options = options
        self.root = options.root.resolve()
        self.config = config or load_workflow_config(DEFAULT_CONFIG_PATH)
        self.state = WorkflowStateStore(state_path)
        self.python = str(self.config.get("runtime", {}).get("python") or sys.executable)
        self.batch_name = infer_batch_name(options.input_path)

    def run(self) -> dict[str, Any]:
        start = time.perf_counter()
        if self.options.stage == "grobid_check":
            return self.run_grobid_check(start)
        papers = discover_workflow_papers(self.root, self.options)
        results: list[PaperWorkflowResult] = []
        selected_stages = (
            [self.options.stage]
            if self.options.stage in STAGES
            else ["parse", "metadata", "tag", "summary"] if not self.options.dry_run else STAGES
        )
        for paper in papers:
            self.state.upsert_paper(paper.paper_id, str(paper.pdf_path))
            results.append(self.run_paper(paper, stages=selected_stages))
        if not self.options.dry_run and self.options.stage is None:
            self.run_batch_embedding_and_lancedb(results, papers)
        failed = [result for result in results if result.failed]
        return {
            "workflow_version": WORKFLOW_VERSION,
            "dry_run": self.options.dry_run,
            "resume": self.options.resume,
            "skip_summary": self.options.skip_summary,
            "skip_embedding": self.options.skip_embedding,
            "paper_count": len(results),
            "failed_count": len(failed),
            "status": "failed" if failed else "succeeded",
            "duration_seconds": round(time.perf_counter() - start, 3),
            "papers": [paper_result_to_dict(result) for result in results],
        }

    def run_grobid_check(self, start: float) -> dict[str, Any]:
        input_path = self.options.input_path or (self.root / "00_Inbox")
        command = [
            self.python,
            str(SCRIPTS_DIR / "grobid_diagnostic.py"),
            "--input",
            str(input_path),
            "--report-dir",
            str(self.root / "reports"),
            "--metadata-dir",
            str(self.root / "02_Metadata"),
            "--grobid-config",
            str(self.root / "Config" / "grobid.yaml"),
            "--json",
        ]
        if self.options.limit is not None:
            command.extend(["--limit", str(self.options.limit)])
        completed = run_command(command, self.root)
        payload: dict[str, Any] = {}
        if completed.stdout.strip():
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError:
                payload = {"stdout": completed.stdout[-2000:]}
        return {
            "workflow_version": WORKFLOW_VERSION,
            "stage": "grobid_check",
            "dry_run": False,
            "paper_count": payload.get("total_pdf_count", 0),
            "failed_count": payload.get("grobid_fulltext_failed", 0),
            "status": "succeeded" if completed.returncode == 0 else "failed",
            "duration_seconds": round(time.perf_counter() - start, 3),
            "report_md": str(self.root / "reports" / "grobid_diagnostic_report.md"),
            "report_json": str(self.root / "reports" / "grobid_diagnostic_report.json"),
            "details": payload,
        }

    def run_paper(self, paper: PaperWorkflowItem, stages: list[str] | None = None) -> PaperWorkflowResult:
        result = PaperWorkflowResult(paper_id=paper.paper_id, paper_key=paper.paper_key, pdf_path=str(paper.pdf_path))
        for stage in stages or STAGES:
            stage_result = self.run_stage(paper, stage)
            result.stages[stage] = stage_result
            self.state.update_stage(
                paper.paper_id,
                stage,
                stage_result.status,
                stage_result.message if stage_result.status.startswith(("failed", "blocked")) else "",
            )
            if stage_result.status.startswith(("failed", "blocked")):
                result.failed = True
                result.error_message = f"{stage}: {stage_result.message}"
                break
        return result

    def run_batch_embedding_and_lancedb(
        self,
        results: list[PaperWorkflowResult],
        papers: list[PaperWorkflowItem],
    ) -> None:
        eligible = [
            (result, paper)
            for result, paper in zip(results, papers)
            if not result.failed
        ]
        if not eligible:
            return
        start = time.perf_counter()
        if self.options.skip_embedding:
            batch_result = self.stage_result("embedding", "skipped_by_user", "--skip-embedding", start)
        elif self.options.skip_summary:
            batch_result = self.stage_result(
                "embedding",
                "skipped_summary_embedding_not_run",
                "summary skipped; embedding disabled to avoid summary embedding",
                start,
            )
        else:
            batch_result = self.run_batch_embedding(start)

        for result, paper in eligible:
            result.stages["embedding"] = batch_result
            self.state.update_stage(
                paper.paper_id,
                "embedding",
                batch_result.status,
                batch_result.message if batch_result.status.startswith(("failed", "blocked")) else "",
            )
            if batch_result.status.startswith(("failed", "blocked")):
                result.failed = True
                result.error_message = f"embedding: {batch_result.message}"
                continue

            lancedb_start = time.perf_counter()
            if self.options.skip_embedding:
                lancedb_result = self.stage_result("lancedb", "skipped_embedding_not_run", "--skip-embedding", lancedb_start)
            else:
                indexed = paper_indexed_in_lancedb(self.root, paper.paper_id)
                searchable = query_api_searchable(self.root, paper) if indexed else False
                lancedb_result = self.stage_result(
                    "lancedb",
                    "completed" if indexed and searchable else "failed",
                    "Query API searchable" if indexed and searchable else "batch paper not searchable in LanceDB",
                    lancedb_start,
                    table_counts(self.root),
                )
            result.stages["lancedb"] = lancedb_result
            self.state.update_stage(
                paper.paper_id,
                "lancedb",
                lancedb_result.status,
                lancedb_result.message if lancedb_result.status.startswith(("failed", "blocked")) else "",
            )
            if lancedb_result.status.startswith(("failed", "blocked")):
                result.failed = True
                result.error_message = f"lancedb: {lancedb_result.message}"

    def run_stage(self, paper: PaperWorkflowItem, stage: str) -> StageResult:
        start = time.perf_counter()
        if self.options.resume and self.should_resume_skip(paper.paper_id, stage, paper):
            return self.stage_result(stage, "completed_resume_skipped", "previous successful state retained", start)
        if self.options.dry_run:
            return self.stage_result(stage, dry_run_status_for_stage(paper, stage, self.options), "dry-run only", start)
        try:
            if stage == "parse":
                return self.run_parse(paper, start)
            if stage == "metadata":
                return self.run_metadata(paper, start)
            if stage == "tag":
                return self.run_tag(paper, start)
            if stage == "summary":
                return self.run_summary(paper, start)
            if stage == "embedding":
                return self.run_embedding(paper, start)
            if stage == "lancedb":
                return self.run_lancedb(paper, start)
            return self.stage_result(stage, "failed", f"unknown stage: {stage}", start)
        except Exception as exc:
            return self.stage_result(stage, "failed", f"{type(exc).__name__}: {exc}", start)

    def should_resume_skip(self, paper_id: str, stage: str, paper: PaperWorkflowItem) -> bool:
        row = self.state.get_paper(paper_id) or {}
        if not is_success_status(row.get(f"{stage}_status")):
            return False
        return output_exists_for_stage(paper, stage, self.root)

    def run_parse(self, paper: PaperWorkflowItem, start: float) -> StageResult:
        if parse_outputs_exist(paper, self.root):
            parser_used = parser_used_from_metadata(paper.metadata_path)
            return self.stage_result("parse", "completed_existing", f"parser_used={parser_used or 'unknown'}", start, {"parser_used": parser_used})
        ensure_grobid()
        command = [
            self.python,
            str(SCRIPTS_DIR / "pdf_parser.py"),
            "--input-dir",
            str(paper.pdf_path.parent),
            "--metadata-dir",
            str(self.root / "02_Metadata"),
            "--raw-text-dir",
            str(self.root / "03_Summary" / "raw_text"),
            "--workers",
            "1",
        ]
        completed = run_command(command, self.root)
        refresh_paper_paths(paper, self.root)
        status = "completed" if completed.returncode == 0 and parse_outputs_exist(paper, self.root) else "failed"
        return self.stage_result("parse", status, completed_message(completed), start, {"command": command})

    def run_metadata(self, paper: PaperWorkflowItem, start: float) -> StageResult:
        refresh_paper_paths(paper, self.root)
        if metadata_exists(paper):
            return self.stage_result("metadata", "completed_existing", "metadata.yaml exists", start)
        command = [
            self.python,
            str(SCRIPTS_DIR / "metadata_extractor.py"),
            "--papers-dir",
            str(self.root / "02_Metadata" / "papers"),
            "--raw-text-dir",
            str(self.root / "03_Summary" / "raw_text"),
            "--output-dir",
            str(self.root / "02_Metadata"),
            "--aggregate-path",
            str(self.root / "02_Metadata" / "metadata.yaml"),
        ]
        completed = run_command(command, self.root)
        refresh_paper_paths(paper, self.root)
        status = "completed" if completed.returncode == 0 and metadata_exists(paper) else "failed"
        return self.stage_result("metadata", status, completed_message(completed), start, {"command": command})

    def run_tag(self, paper: PaperWorkflowItem, start: float) -> StageResult:
        refresh_paper_paths(paper, self.root)
        if tags_exist(paper):
            return self.stage_result("tag", "completed_existing", "tags.yaml exists", start)
        command = [
            self.python,
            str(SCRIPTS_DIR / "retag.py"),
            "--all",
            "--changed-only",
            "--root",
            str(self.root),
            "--no-lancedb",
        ]
        completed = run_command(command, self.root)
        refresh_paper_paths(paper, self.root)
        status = "completed" if completed.returncode == 0 and tags_exist(paper) else "failed"
        return self.stage_result("tag", status, completed_message(completed), start, {"command": command})

    def run_summary(self, paper: PaperWorkflowItem, start: float) -> StageResult:
        if self.options.skip_summary:
            return self.stage_result("summary", "skipped_by_user", "--skip-summary", start)
        refresh_paper_paths(paper, self.root)
        if summary_exists(paper):
            return self.stage_result("summary", "completed_existing", "summary.md exists", start)
        if not os.environ.get("DEEPSEEK_API_KEY") and not summary_cache_exists(self.root, paper.paper_id):
            return self.stage_result("summary", "blocked_missing_api_key", "DEEPSEEK_API_KEY is not set and no cached summary is available", start)
        command = [self.python, str(self.root / "summary_engine.py"), "--paper-id", paper.paper_id, "--root", str(self.root), "--force"]
        if not os.environ.get("DEEPSEEK_API_KEY"):
            command.append("--cache-only")
        completed = run_command(command, self.root)
        refresh_paper_paths(paper, self.root)
        status = "completed" if completed.returncode == 0 and summary_exists(paper) else "failed"
        return self.stage_result("summary", status, completed_message(completed), start, {"command": command})

    def run_embedding(self, paper: PaperWorkflowItem, start: float) -> StageResult:
        if self.options.skip_embedding:
            return self.stage_result("embedding", "skipped_by_user", "--skip-embedding", start)
        if self.options.skip_summary:
            return self.stage_result("embedding", "skipped_summary_embedding_not_run", "summary skipped; embedding disabled to avoid summary embedding", start)
        if lancedb_ready(self.root):
            return self.stage_result("embedding", "completed_existing", "LanceDB tables already available", start, table_counts(self.root))
        command = [
            self.python,
            str(SCRIPTS_DIR / "build_embeddings.py"),
            "--root",
            str(self.root),
            "--batch",
            self.batch_name or "batch_5",
            "--real-run",
        ]
        completed = run_command(command, self.root)
        status = "completed" if completed.returncode == 0 and lancedb_ready(self.root) else "failed"
        return self.stage_result("embedding", status, completed_message(completed), start, {"command": command})

    def run_batch_embedding(self, start: float) -> StageResult:
        command = [
            self.python,
            str(SCRIPTS_DIR / "build_embeddings.py"),
            "--root",
            str(self.root),
            "--batch",
            self.batch_name or "batch_5",
            "--real-run",
            "--report",
            str(self.root / "05_Index" / f"{self.batch_name or 'batch'}_embedding_report.md"),
        ]
        completed = run_command(command, self.root)
        status = "completed" if completed.returncode == 0 and lancedb_ready(self.root) else "failed"
        return self.stage_result("embedding", status, completed_message(completed), start, {"command": command})

    def run_lancedb(self, paper: PaperWorkflowItem, start: float) -> StageResult:
        if self.options.skip_embedding:
            return self.stage_result("lancedb", "skipped_embedding_not_run", "--skip-embedding", start)
        if not lancedb_ready(self.root):
            return self.stage_result("lancedb", "failed", "LanceDB tables are unavailable", start)
        searchable = query_api_searchable(self.root, paper)
        status = "completed" if searchable else "failed"
        return self.stage_result("lancedb", status, "Query API searchable" if searchable else "Query API search failed", start, table_counts(self.root))

    def stage_result(
        self,
        stage: str,
        status: str,
        message: str,
        start: float,
        details: dict[str, Any] | None = None,
    ) -> StageResult:
        return StageResult(stage=stage, status=status, message=message, duration_seconds=round(time.perf_counter() - start, 3), details=details or {})


def discover_workflow_papers(root: Path, options: WorkflowOptions) -> list[PaperWorkflowItem]:
    pdfs = discover_input_pdfs(root, options)
    if options.limit is not None:
        pdfs = pdfs[: options.limit]
    items = [build_paper_item(root, pdf) for pdf in pdfs]
    if options.paper_id:
        wanted = options.paper_id.casefold()
        items = [
            item
            for item in items
            if item.paper_id.casefold() == wanted or item.paper_key.casefold() == wanted or item.pdf_path.stem.casefold() == wanted
        ]
    return sorted(items, key=lambda item: item.paper_key)


def discover_input_pdfs(root: Path, options: WorkflowOptions) -> list[Path]:
    if options.paper_id:
        candidates = [
            root / "01_PDF" / f"{options.paper_id}.pdf",
            root / "01_PDF" / "batch_5" / f"{options.paper_id}.pdf",
        ]
        candidates.extend(sorted((root / "01_PDF").glob(f"**/{options.paper_id}*.pdf")))
        return unique_paths([path for path in candidates if path.exists()])
    if options.input_path:
        path = options.input_path if options.input_path.is_absolute() else root / options.input_path
        if path.is_file() and path.suffix.lower() == ".pdf":
            return [path.resolve()]
        return sorted(path.glob("*.pdf")) if path.exists() else []
    if options.all_papers:
        return sorted((root / "01_PDF").glob("**/*.pdf"))
    return sorted((root / "00_Inbox").glob("*.pdf"))


def build_paper_item(root: Path, pdf_path: Path) -> PaperWorkflowItem:
    paper_key = pdf_path.stem
    metadata_path = find_metadata_path(root, paper_key)
    metadata = read_yaml(metadata_path)
    paper_id = str(metadata.get("paper_id") or deterministic_paper_id(pdf_path))
    item = PaperWorkflowItem(
        paper_id=paper_id,
        paper_key=paper_key,
        pdf_path=pdf_path.resolve(),
        metadata_path=metadata_path,
    )
    refresh_paper_paths(item, root)
    return item


def refresh_paper_paths(item: PaperWorkflowItem, root: Path) -> None:
    metadata_path = find_metadata_path(root, item.paper_key) or find_metadata_by_paper_id(root, item.paper_id)
    metadata = read_yaml(metadata_path)
    if metadata.get("paper_id"):
        item.paper_id = str(metadata["paper_id"])
    item.metadata_path = metadata_path
    item.tags_path = find_tags_path(root, item.paper_id, item.paper_key)
    item.summary_path = find_summary_path(root, item.paper_id, item.paper_key)
    item.raw_text_path = find_raw_text_path(root, item.paper_key, metadata)
    item.parser_used = parser_used_from_metadata(item.metadata_path)


def find_metadata_path(root: Path, paper_key: str) -> Path | None:
    safe_key = safe_path_name(paper_key)
    raw_safe_key = raw_safe_path_name(paper_key)
    candidates = [
        root / "02_Metadata" / paper_key / "metadata.yaml",
        root / "02_Metadata" / safe_key / "metadata.yaml",
        root / "02_Metadata" / raw_safe_key / "metadata.yaml",
    ]
    candidates.extend(sorted((root / "02_Metadata").glob(f"{paper_key}*/metadata.yaml")))
    candidates.extend(sorted((root / "02_Metadata").glob(f"{safe_key}*/metadata.yaml")))
    candidates.extend(sorted((root / "02_Metadata").glob(f"{raw_safe_key}*/metadata.yaml")))
    for candidate in [safe_key, raw_safe_key]:
        for length in [160, 140, 120, 100, 80]:
            if len(candidate) > length:
                candidates.extend(sorted((root / "02_Metadata").glob(f"{candidate[:length]}*/metadata.yaml")))
    return next((path for path in candidates if path.exists()), None)


def find_metadata_by_paper_id(root: Path, paper_id: str) -> Path | None:
    for path in sorted((root / "02_Metadata").glob("*/metadata.yaml")):
        if read_yaml(path).get("paper_id") == paper_id:
            return path
    return None


def find_tags_path(root: Path, paper_id: str, paper_key: str) -> Path | None:
    safe_key = safe_path_name(paper_key)
    candidates = [
        root / "05_Index" / "tags" / paper_id / "tags.yaml",
        root / "02_Metadata" / paper_key / "tags.yaml",
        root / "02_Metadata" / safe_key / "tags.yaml",
    ]
    return next((path for path in candidates if path.exists()), None)


def find_summary_path(root: Path, paper_id: str, paper_key: str) -> Path | None:
    safe_key = safe_path_name(paper_key)
    candidates = [
        root / "03_Summary" / paper_id / "summary.md",
        root / "03_Summary" / paper_key / "summary.md",
        root / "03_Summary" / safe_key / "summary.md",
    ]
    return next((path for path in candidates if path.exists()), None)


def find_raw_text_path(root: Path, paper_key: str, metadata: dict[str, Any]) -> Path | None:
    output_path = metadata.get("outputs", {}).get("raw_text_path") if isinstance(metadata.get("outputs"), dict) else None
    candidates = [Path(str(output_path))] if output_path else []
    candidates.extend(sorted((root / "03_Summary" / "raw_text").glob(f"{paper_key}*.txt")))
    candidates.extend(sorted((root / "03_Summary" / "raw_text").glob(f"{safe_path_name(paper_key)}*.txt")))
    for candidate in [safe_path_name(paper_key), raw_safe_path_name(paper_key)]:
        candidates.extend(sorted((root / "03_Summary" / "raw_text").glob(f"{candidate}*.txt")))
        for length in [160, 140, 120, 100, 80]:
            if len(candidate) > length:
                candidates.extend(sorted((root / "03_Summary" / "raw_text").glob(f"{candidate[:length]}*.txt")))
    return next((path for path in candidates if path.exists()), None)


def parse_outputs_exist(paper: PaperWorkflowItem, root: Path) -> bool:
    refresh_paper_paths(paper, root)
    return bool(paper.raw_text_path and paper.raw_text_path.exists() and paper.metadata_path and paper.metadata_path.exists())


def metadata_exists(paper: PaperWorkflowItem) -> bool:
    metadata = read_yaml(paper.metadata_path)
    return bool(metadata.get("title") and metadata.get("paper_id"))


def tags_exist(paper: PaperWorkflowItem) -> bool:
    return bool(paper.tags_path and paper.tags_path.exists())


def summary_exists(paper: PaperWorkflowItem) -> bool:
    if not paper.summary_path or not paper.summary_path.exists():
        return False
    text = paper.summary_path.read_text(encoding="utf-8", errors="replace")
    return "# Citation Anchors" in text and re.search(r"\bS\d{3}\b", text) is not None


def output_exists_for_stage(paper: PaperWorkflowItem, stage: str, root: Path) -> bool:
    if stage == "parse":
        return parse_outputs_exist(paper, root)
    if stage == "metadata":
        return metadata_exists(paper)
    if stage == "tag":
        return tags_exist(paper)
    if stage == "summary":
        return summary_exists(paper)
    if stage in {"embedding", "lancedb"}:
        return lancedb_ready(root)
    return False


def dry_run_status_for_stage(paper: PaperWorkflowItem, stage: str, options: WorkflowOptions) -> str:
    if stage == "summary" and options.skip_summary:
        return "dry_run_skip_summary"
    if stage in {"embedding", "lancedb"} and options.skip_embedding:
        return "dry_run_skip_embedding"
    return "dry_run_ready" if output_exists_for_stage(paper, stage, options.root) else "dry_run_would_run"


def parser_used_from_metadata(path: Path | None) -> str | None:
    metadata = read_yaml(path)
    parse_status = metadata.get("parse_status") if isinstance(metadata.get("parse_status"), dict) else {}
    return parse_status.get("parser_used")


def summary_cache_exists(root: Path, paper_id: str) -> bool:
    return any((root / "03_Summary" / "cache" / paper_id).glob("*.summary.json"))


def ensure_grobid() -> dict[str, Any]:
    from ensure_grobid import ensure_grobid_available

    return ensure_grobid_available()


def lancedb_ready(root: Path) -> bool:
    counts = table_counts(root)
    return counts.get("metadata_embeddings", 0) > 0 and counts.get("summary_embeddings", 0) > 0 and counts.get("chunk_embeddings", 0) > 0


def table_counts(root: Path) -> dict[str, int]:
    try:
        import lancedb

        db = lancedb.connect(str(root / "04_VectorDB" / "lancedb"))
        names = lancedb_table_names(db)
        counts: dict[str, int] = {}
        for table_name in ["metadata_embeddings", "summary_embeddings", "chunk_embeddings"]:
            if table_name in names:
                counts[table_name] = len(db.open_table(table_name).to_arrow())
            else:
                counts[table_name] = 0
        return counts
    except Exception:
        return {}


def paper_indexed_in_lancedb(root: Path, paper_id: str) -> bool:
    try:
        import lancedb

        db = lancedb.connect(str(root / "04_VectorDB" / "lancedb"))
        names = lancedb_table_names(db)
        for table_name in ["metadata_embeddings", "summary_embeddings", "chunk_embeddings"]:
            if table_name not in names:
                continue
            for row in db.open_table(table_name).to_arrow().to_pylist():
                if str(row.get("paper_id") or "") == paper_id:
                    return True
    except Exception:
        return False
    return False


def query_api_searchable(root: Path, paper: PaperWorkflowItem) -> bool:
    try:
        from scientra.query import LiteratureQueryService

        service = LiteratureQueryService(root)
        response = service.literature_query({"query": paper.paper_key.replace("_", " "), "mode": "keyword", "top_k": 10, "level": "all"})
        return any(item.paper_id == paper.paper_id for item in response.results)
    except Exception:
        return False


def lancedb_table_names(db: Any) -> set[str]:
    if hasattr(db, "list_tables"):
        payload = db.list_tables()
        if hasattr(payload, "tables"):
            return set(str(name) for name in payload.tables)
        return set(str(name) for name in payload)
    return set(str(name) for name in db.table_names())


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    secret_prefix = "s" + "k-"
    safe_command = ["[redacted]" if secret_prefix in part else part for part in command]
    completed = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, timeout=7200)
    completed.args = safe_command
    return completed


def completed_message(completed: subprocess.CompletedProcess[str]) -> str:
    if completed.returncode == 0:
        return "command succeeded"
    stderr = (completed.stderr or "").strip().splitlines()
    stdout = (completed.stdout or "").strip().splitlines()
    tail = stderr[-1] if stderr else (stdout[-1] if stdout else "")
    return f"command failed ({completed.returncode}): {tail[:500]}"


def read_yaml(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def deterministic_paper_id(pdf_path: Path) -> str:
    return "paper_" + re.sub(r"[^A-Za-z0-9]+", "_", pdf_path.stem).strip("_")[:48]


def safe_path_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    value = re.sub(r"_+", "_", value)
    return value[:180] or "paper"


def raw_safe_path_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")[:180] or "paper"


def infer_batch_name(input_path: Path | None) -> str | None:
    if input_path and input_path.name:
        return input_path.name
    return None


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        result.append(path.resolve())
    return result


def paper_result_to_dict(result: PaperWorkflowResult) -> dict[str, Any]:
    return {
        "paper_id": result.paper_id,
        "paper_key": result.paper_key,
        "pdf_path": result.pdf_path,
        "failed": result.failed,
        "error_message": result.error_message,
        "stages": {
            name: {
                "status": stage.status,
                "message": stage.message,
                "duration_seconds": stage.duration_seconds,
                "details": stage.details,
            }
            for name, stage in result.stages.items()
        },
    }


def load_workflow_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Scientra Copilot PDF-to-query workflow.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--paper-id", default=None)
    parser.add_argument("--input", dest="input_path", type=Path, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-summary", action="store_true")
    parser.add_argument("--skip-embedding", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--stage", choices=["grobid_check", "parse", "metadata", "tag", "summary", "embedding", "lancedb"], default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def options_from_args(args: argparse.Namespace) -> WorkflowOptions:
    root = args.root.resolve()
    input_path = args.input_path
    if input_path and not input_path.is_absolute():
        input_path = root / input_path
    return WorkflowOptions(
        root=root,
        input_path=input_path.resolve() if input_path else None,
        paper_id=args.paper_id,
        all_papers=args.all,
        resume=args.resume,
        dry_run=args.dry_run,
        skip_summary=args.skip_summary,
        skip_embedding=args.skip_embedding,
        force=args.force,
        stage=args.stage,
        limit=args.limit,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_workflow_config(args.config)
    runner = WorkflowRunner(options_from_args(args), config=config)
    report = runner.run()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
