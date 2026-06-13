"""Import Dashboard — read-only bundle registry access."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.io.storage_layout import StorageLayout


class ImportDashboard:
    """Read-only access to article bundle import status."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.storage = StorageLayout(root)
        self.storage.load()
        self.root = self.storage.root

    def list_bundles(self) -> dict[str, Any]:
        """List all article bundles."""
        reg = self.root / "10_System" / "registry" / "article_bundle_registry.json"
        if not reg.exists():
            return {"bundles": [], "total": 0, "message": "No bundles imported yet."}
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
        except Exception:
            return {"bundles": [], "total": 0, "message": "Registry unreadable."}

        bundles = []
        for b in data.get("bundles", []):
            bundles.append({
                "bundle_id": b.get("bundle_id", ""),
                "bundle_name": b.get("bundle_name", ""),
                "detected_main_pdf": Path(b.get("detected_main_pdf", "")).name if b.get("detected_main_pdf") else None,
                "tabular_supplementary_count": len(b.get("tabular_supplementary_files", [])),
                "supplementary_pdf_count": len(b.get("supplementary_pdfs", [])),
                "other_file_count": len(b.get("other_files", [])),
                "processing_status": b.get("processing_status", "unknown"),
                "archive_status": b.get("archive_status", "none"),
                "binding_method": b.get("binding_method", "folder_explicit"),
                "match_confidence": b.get("match_confidence", "high"),
                "warnings": b.get("warnings", []),
                "created_at": b.get("created_at"),
                "processed_at": b.get("processed_at"),
            })
        return {"bundles": bundles, "total": len(bundles),
                "processed": sum(1 for b in bundles if b["processing_status"] in ("processed", "scanned")),
                "failed": sum(1 for b in bundles if b["processing_status"].startswith("failed"))}

    def get_bundle_detail(self, bundle_id: str) -> dict[str, Any]:
        """Get single bundle detail."""
        reg = self.root / "10_System" / "registry" / "article_bundle_registry.json"
        if not reg.exists():
            return {"error": "No registry found"}

        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
        except Exception:
            return {"error": "Registry unreadable"}

        for b in data.get("bundles", []):
            if b.get("bundle_id") == bundle_id:
                # Load manifests if available
                pid = b.get("paper_id") or b.get("bundle_id", "")
                src_manifest = self._load_manifest("01_Sources/papers", pid, "source_manifest.json")
                suppl_manifest = self._load_manifest("01_Sources/supplementary", pid, "supplementary_manifest.json")

                return {
                    "bundle_id": b.get("bundle_id", ""),
                    "bundle_name": b.get("bundle_name", ""),
                    "detected_main_pdf": b.get("detected_main_pdf"),
                    "source_manifest": src_manifest,
                    "supplementary_manifest": suppl_manifest,
                    "tabular_supplementary_files": [Path(f).name for f in b.get("tabular_supplementary_files", [])],
                    "supplementary_pdfs": [Path(f).name for f in b.get("supplementary_pdfs", [])],
                    "other_files": [Path(f).name for f in b.get("other_files", [])],
                    "warnings": b.get("warnings", []),
                    "binding_method": b.get("binding_method", "folder_explicit"),
                    "match_confidence": b.get("match_confidence", "high"),
                    "paper_ingest_status": b.get("paper_ingest_status", "pending"),
                    "processing_status": b.get("processing_status", "unknown"),
                    "entity_index_status": "pending",
                }
        return {"error": "Bundle not found"}

    def list_loose_supplementary(self) -> dict[str, Any]:
        """List loose supplementary files needing review."""
        loose_dir = self.storage.get_path("inbox.loose_supplementary_review_needed")
        files = []
        if loose_dir.exists():
            for f in loose_dir.iterdir():
                if f.is_file():
                    files.append({
                        "file_name": f.name,
                        "file_type": f.suffix.lstrip("."),
                        "relative_path": str(f.relative_to(self.root)),
                        "status": "review_needed",
                        "requires_manual_review": True,
                        "reason": "Loose supplementary file requires manual binding to a paper.",
                        "created_at": None,
                    })
        # Also check loose_supplementary/new
        new_dir = self.storage.get_path("inbox.loose_supplementary_new")
        if new_dir.exists():
            for f in new_dir.iterdir():
                if f.is_file():
                    files.append({
                        "file_name": f.name,
                        "file_type": f.suffix.lstrip("."),
                        "relative_path": str(f.relative_to(self.root)),
                        "status": "review_needed",
                        "requires_manual_review": True,
                        "reason": "New loose supplementary file. Manual review required.",
                        "created_at": None,
                    })
        return {"files": files, "total": len(files),
                "message": "All loose files require manual review. They will not enter entity index automatically."}

    def _load_manifest(self, base_dir: str, pid: str, filename: str) -> dict | None:
        p = self.root / base_dir / pid / filename
        if p.exists():
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
                # Strip absolute paths from manifest values
                if "archived_main_pdf_relative_path" in m:
                    pass  # already relative
                return m
            except Exception:
                return None
        return None
