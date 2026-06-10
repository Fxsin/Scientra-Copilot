from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WORKFLOW_VERSION = "0.1.0"
STAGES = ["parse", "metadata", "tag", "summary", "embedding", "lancedb"]
TERMINAL_SUCCESS_PREFIXES = ("completed", "skipped")


@dataclass(frozen=True)
class WorkflowOptions:
    root: Path
    input_path: Path | None = None
    paper_id: str | None = None
    all_papers: bool = False
    resume: bool = False
    dry_run: bool = False
    skip_summary: bool = False
    skip_embedding: bool = False
    force: bool = False
    stage: str | None = None
    limit: int | None = None


@dataclass
class PaperWorkflowItem:
    paper_id: str
    paper_key: str
    pdf_path: Path
    metadata_path: Path | None = None
    tags_path: Path | None = None
    summary_path: Path | None = None
    raw_text_path: Path | None = None
    parser_used: str | None = None


@dataclass
class StageResult:
    stage: str
    status: str
    message: str = ""
    duration_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperWorkflowResult:
    paper_id: str
    paper_key: str
    pdf_path: str
    stages: dict[str, StageResult] = field(default_factory=dict)
    failed: bool = False
    error_message: str = ""


def is_success_status(status: str | None) -> bool:
    return bool(status) and str(status).startswith(TERMINAL_SUCCESS_PREFIXES)
