from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow_models import STAGES, WORKFLOW_VERSION


DEFAULT_STATE_PATH = Path(__file__).resolve().parents[1] / "05_Index" / "workflow_state.sqlite"


class WorkflowStateStore:
    def __init__(self, path: str | Path = DEFAULT_STATE_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_schema(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_workflow_state (
                    paper_id TEXT PRIMARY KEY,
                    pdf_path TEXT,
                    parse_status TEXT,
                    metadata_status TEXT,
                    tag_status TEXT,
                    summary_status TEXT,
                    embedding_status TEXT,
                    lancedb_status TEXT,
                    error_message TEXT,
                    last_updated TEXT,
                    workflow_version TEXT
                )
                """
            )
            connection.commit()

    def upsert_paper(self, paper_id: str, pdf_path: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO paper_workflow_state (
                    paper_id, pdf_path, parse_status, metadata_status, tag_status,
                    summary_status, embedding_status, lancedb_status, error_message,
                    last_updated, workflow_version
                )
                VALUES (?, ?, 'pending', 'pending', 'pending', 'pending', 'pending', 'pending', '', ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    pdf_path=excluded.pdf_path,
                    last_updated=excluded.last_updated,
                    workflow_version=excluded.workflow_version
                """,
                (paper_id, pdf_path, now, WORKFLOW_VERSION),
            )
            connection.commit()

    def update_stage(self, paper_id: str, stage: str, status: str, error_message: str = "") -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown workflow stage: {stage}")
        column = f"{stage}_status"
        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE paper_workflow_state
                SET {column} = ?, error_message = ?, last_updated = ?, workflow_version = ?
                WHERE paper_id = ?
                """,
                (status, error_message, utc_now(), WORKFLOW_VERSION, paper_id),
            )
            connection.commit()

    def get_paper(self, paper_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_workflow_state WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_papers(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM paper_workflow_state ORDER BY paper_id").fetchall()
        return [dict(row) for row in rows]

    def set_failure(self, paper_id: str, stage: str, error_message: str) -> None:
        self.update_stage(paper_id, stage, "failed", error_message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

