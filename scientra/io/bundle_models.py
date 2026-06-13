"""Article Bundle Import — data models. No absolute paths."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArticleBundleRecord:
    """A scanned article bundle from 00_Inbox/article_bundles/new/."""

    def __init__(self, **kwargs: Any):
        self.bundle_id: str = kwargs.get("bundle_id", "")
        self.bundle_name: str = kwargs.get("bundle_name", "")
        self.bundle_relative_path: str = kwargs.get("bundle_relative_path", "")
        self.detected_main_pdf: str | None = kwargs.get("detected_main_pdf")
        self.supplementary_files: list[str] = kwargs.get("supplementary_files", [])
        self.supplementary_pdfs: list[str] = kwargs.get("supplementary_pdfs", [])
        self.tabular_supplementary_files: list[str] = kwargs.get("tabular_supplementary_files", [])
        self.other_files: list[str] = kwargs.get("other_files", [])
        self.paper_id: str | None = kwargs.get("paper_id")
        self.paper_title: str | None = kwargs.get("paper_title")
        self.doi: str | None = kwargs.get("doi")
        self.binding_method: str = kwargs.get("binding_method", "folder_explicit")
        self.match_confidence: str = kwargs.get("match_confidence", "high")
        self.processing_status: str = kwargs.get("processing_status", "pending")
        self.archive_status: str = kwargs.get("archive_status", "none")
        self.paper_ingest_status: str = kwargs.get("paper_ingest_status", "pending")
        self.created_at: str = kwargs.get("created_at", _utc_now())
        self.processed_at: str | None = kwargs.get("processed_at")
        self.error_message: str | None = kwargs.get("error_message")
        self.warnings: list[str] = kwargs.get("warnings", [])
        self.notes: list[str] = kwargs.get("notes", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_name": self.bundle_name,
            "bundle_relative_path": self.bundle_relative_path,
            "detected_main_pdf": self.detected_main_pdf,
            "supplementary_files": self.supplementary_files,
            "supplementary_pdfs": self.supplementary_pdfs,
            "tabular_supplementary_files": self.tabular_supplementary_files,
            "other_files": self.other_files,
            "paper_id": self.paper_id,
            "paper_title": self.paper_title,
            "doi": self.doi,
            "binding_method": self.binding_method,
            "match_confidence": self.match_confidence,
            "processing_status": self.processing_status,
            "archive_status": self.archive_status,
            "paper_ingest_status": self.paper_ingest_status,
            "created_at": self.created_at,
            "processed_at": self.processed_at,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "notes": self.notes,
        }
