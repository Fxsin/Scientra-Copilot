"""Type definitions for the Paper Asset Layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PaperAsset:
    """A single asset attached to a paper."""

    asset_id: str
    paper_id: str
    asset_type: str  # main_pdf, supplementary_pdf, supplementary_table, dataset, figure_image, table_image, archive, attachment, unknown
    filename: str
    original_filename: str
    relative_path: str
    sha256: str
    size_bytes: int
    mime_type: str
    extension: str
    source: str  # initial_import, manual_upload, web_upload, folder_scan
    status: str  # registered, pending, processing, processed, failed, skipped
    processing_stage: str = ""
    created_at: str = ""
    updated_at: str = ""
    notes: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Reserved for future pipeline stages
    figure_intelligence_status: str = ""
    table_intelligence_status: str = ""
    supplementary_intelligence_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "paper_id": self.paper_id,
            "asset_type": self.asset_type,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "extension": self.extension,
            "source": self.source,
            "status": self.status,
            "processing_stage": self.processing_stage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PaperAsset:
        return cls(
            asset_id=d.get("asset_id", ""),
            paper_id=d.get("paper_id", ""),
            asset_type=d.get("asset_type", "unknown"),
            filename=d.get("filename", ""),
            original_filename=d.get("original_filename", ""),
            relative_path=d.get("relative_path", ""),
            sha256=d.get("sha256", ""),
            size_bytes=d.get("size_bytes", 0),
            mime_type=d.get("mime_type", ""),
            extension=d.get("extension", ""),
            source=d.get("source", "manual_upload"),
            status=d.get("status", "registered"),
            processing_stage=d.get("processing_stage", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            notes=d.get("notes", ""),
            warnings=list(d.get("warnings", [])),
            errors=list(d.get("errors", [])),
            figure_intelligence_status=d.get("figure_intelligence_status", ""),
            table_intelligence_status=d.get("table_intelligence_status", ""),
            supplementary_intelligence_status=d.get("supplementary_intelligence_status", ""),
        )


@dataclass
class PaperAssetRegistry:
    """Registry of all assets for a single paper."""

    paper_id: str
    main_pdf: dict[str, Any] | None = None
    assets: list[dict[str, Any]] = field(default_factory=list)
    asset_counts: dict[str, int] = field(default_factory=lambda: {
        "supplementary_pdf": 0,
        "supplementary_table": 0,
        "dataset": 0,
        "figure_image": 0,
        "table_image": 0,
        "archive": 0,
        "attachment": 0,
        "unknown": 0,
    })
    last_updated: str = ""

    def add_asset(self, asset: PaperAsset) -> None:
        d = asset.to_dict()
        self.assets.append(d)
        atype = asset.asset_type
        if atype in self.asset_counts:
            self.asset_counts[atype] += 1
        else:
            self.asset_counts["unknown"] += 1
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "main_pdf": self.main_pdf,
            "assets": self.assets,
            "asset_counts": self.asset_counts,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PaperAssetRegistry:
        return cls(
            paper_id=d.get("paper_id", ""),
            main_pdf=d.get("main_pdf"),
            assets=list(d.get("assets", [])),
            asset_counts=dict(d.get("asset_counts", {})),
            last_updated=d.get("last_updated", ""),
        )
