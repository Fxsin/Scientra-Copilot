"""Paper Asset Registry — per-paper asset tracking via paper_assets.json."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.assets.types import PaperAsset, PaperAssetRegistry
from scientra.assets.asset_status import ASSET_STATUSES


def _get_papers_root() -> Path:
    """Get the papers directory root."""
    candidate = Path(__file__).resolve().parent.parent.parent
    root = candidate / "01_Sources" / "papers"
    return root


def get_paper_dir(paper_id: str) -> Path:
    """Get the directory for a specific paper.

    Uses workspace resolution if available; falls back to legacy path.
    """
    try:
        from scientra.papers.paper_workspace import resolve_workspace_dir
        return resolve_workspace_dir(paper_id)
    except Exception:
        pass
    return _get_papers_root() / paper_id


def get_registry_path(paper_id: str) -> Path:
    """Get the path to paper_assets.json for a paper."""
    return get_paper_dir(paper_id) / "paper_assets.json"


def compute_sha256(filepath: str | Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _safe_filename(name: str) -> str:
    """Sanitize filename for safe storage on Windows/Linux."""
    # Replace problematic characters
    unsafe = '<>:"/\\|?*'
    for ch in unsafe:
        name = name.replace(ch, "_")
    # Trim to reasonable length, preserving extension
    if len(name) > 120:
        stem = Path(name).stem[:100]
        suffix = Path(name).suffix
        name = stem + suffix
    return name


def load_registry(paper_id: str) -> PaperAssetRegistry | None:
    """Load paper_assets.json for a paper, or return None."""
    path = get_registry_path(paper_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PaperAssetRegistry.from_dict(data)
    except Exception:
        return None


def save_registry(registry: PaperAssetRegistry) -> None:
    """Save registry to paper_assets.json."""
    path = get_registry_path(registry.paper_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_asset_by_sha256(registry: PaperAssetRegistry, sha256: str) -> dict[str, Any] | None:
    """Find an existing asset with the same SHA-256 hash."""
    # Check main_pdf
    if registry.main_pdf and registry.main_pdf.get("sha256") == sha256:
        return registry.main_pdf
    # Check assets list
    for a in registry.assets:
        if a.get("sha256") == sha256:
            return a
    return None


def _generate_asset_id(paper_id: str, index: int) -> str:
    """Generate a unique asset ID."""
    short_pid = paper_id.replace("paper_", "")[:8] if paper_id.startswith("paper_") else paper_id[:8]
    return f"asset_{short_pid}_{index:04d}"


def init_registry_for_paper(
    paper_id: str,
    main_pdf_source: str | None = None,
) -> PaperAssetRegistry:
    """Initialize a paper_assets.json for a paper.

    If main_pdf_source is provided, register it as the main PDF.
    Does NOT move files.
    """
    registry = PaperAssetRegistry(
        paper_id=paper_id,
        main_pdf=None,
        assets=[],
        last_updated=datetime.now(timezone.utc).isoformat(),
    )

    # If a main PDF source path is given, register it
    if main_pdf_source and Path(main_pdf_source).exists():
        src = Path(main_pdf_source)
        sha = compute_sha256(src)
        stat = src.stat()

        registry.main_pdf = {
            "asset_id": "main_pdf",
            "paper_id": paper_id,
            "asset_type": "main_pdf",
            "filename": src.name,
            "original_filename": src.name,
            "relative_path": "",  # Points to external source
            "source_path": str(src.resolve()),
            "sha256": sha,
            "size_bytes": stat.st_size,
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "source": "initial_import",
            "status": "registered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Main PDF — managed by primary import pipeline",
        }

    # Create required directories
    get_paper_dir(paper_id).mkdir(parents=True, exist_ok=True)
    for sub in ["assets/supplementary", "assets/figures", "assets/tables",
                "assets/datasets", "assets/images", "assets/archives",
                "assets/attachments", "links"]:
        (get_paper_dir(paper_id) / sub).mkdir(parents=True, exist_ok=True)

    save_registry(registry)
    return registry
