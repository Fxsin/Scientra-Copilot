"""Asset Storage — file placement and registration for paper assets."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.assets.types import PaperAsset
from scientra.assets.asset_registry import (
    get_paper_dir,
    get_registry_path,
    compute_sha256,
    _safe_filename,
    _generate_asset_id,
    load_registry,
    save_registry,
    find_asset_by_sha256,
    init_registry_for_paper,
)
from scientra.assets.asset_classifier import classify_asset

# Asset type → subdirectory mapping
ASSET_TYPE_DIRS: dict[str, str] = {
    "supplementary_pdf": "assets/supplementary",
    "supplementary_table": "assets/tables",
    "dataset": "assets/datasets",
    "figure_image": "assets/images",
    "table_image": "assets/images",
    "archive": "assets/archives",
    "attachment": "assets/attachments",
    "unknown": "assets/attachments",
    "main_pdf": "",  # main_pdf is tracked via main_pdf field, not stored here
}


def ensure_paper_asset_dirs(paper_id: str) -> Path:
    """Ensure all asset directories exist for a paper. Returns paper dir."""
    paper_dir = get_paper_dir(paper_id)
    paper_dir.mkdir(parents=True, exist_ok=True)
    for sub in ASSET_TYPE_DIRS.values():
        if sub:
            (paper_dir / sub).mkdir(parents=True, exist_ok=True)
    (paper_dir / "links").mkdir(parents=True, exist_ok=True)
    return paper_dir


def get_paper_assets_dir(paper_id: str) -> Path:
    """Get the assets directory for a paper."""
    return ensure_paper_asset_dirs(paper_id)


def register_asset_for_paper(
    paper_id: str,
    file_path: str,
    asset_type: str | None = None,
    source: str = "manual_upload",
    copy_mode: str = "copy",
) -> PaperAsset:
    """Register a file as an asset for a paper.

    Args:
        paper_id: The paper ID.
        file_path: Path to the source file.
        asset_type: Override automatic classification. If None, auto-detected.
        source: Source label (initial_import, manual_upload, web_upload, folder_scan).
        copy_mode: "copy" to copy file, "move" to move it.

    Returns:
        PaperAsset with registration details.
    """
    src = Path(file_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    # Load or create registry
    registry = load_registry(paper_id)
    paper_has_main = registry is not None and registry.main_pdf is not None
    if registry is None:
        registry = init_registry_for_paper(paper_id)

    paper_dir = get_paper_dir(paper_id)

    # Compute hash and check duplicates
    sha256 = compute_sha256(src)
    existing = find_asset_by_sha256(registry, sha256)
    if existing:
        now = datetime.now(timezone.utc).isoformat()
        return PaperAsset(
            asset_id=existing.get("asset_id", "duplicate"),
            paper_id=paper_id,
            asset_type=existing.get("asset_type", "unknown"),
            filename=existing.get("filename", src.name),
            original_filename=src.name,
            relative_path=existing.get("relative_path", ""),
            sha256=sha256,
            size_bytes=src.stat().st_size,
            mime_type=existing.get("mime_type", ""),
            extension=src.suffix.lower(),
            source=source,
            status="skipped",
            created_at=now,
            updated_at=now,
            notes="Duplicate — same SHA-256 as existing asset",
            warnings=["Duplicate asset: same SHA-256 hash already registered"],
        )

    # Classify
    if asset_type:
        atype = asset_type
        confidence = 0.99
        warnings: list[str] = []
    else:
        atype, confidence, warnings = classify_asset(
            str(src), src.name, None, paper_has_main,
        )

    # Special case: if classified as main_pdf but paper already has one
    if atype == "main_pdf" and paper_has_main:
        atype = "attachment"
        warnings.append("Paper already has a main PDF. Classified as attachment.")

    # Determine target directory
    target_subdir = ASSET_TYPE_DIRS.get(atype, "assets/attachments")
    target_dir = paper_dir / target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    # Safe filename
    safe_name = _safe_filename(src.name)
    target_path = target_dir / safe_name

    # Avoid name collision
    counter = 1
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix
    while target_path.exists():
        safe_name = f"{stem}_{counter}{suffix}"
        target_path = target_dir / safe_name
        counter += 1

    # Copy or move
    try:
        if copy_mode == "move":
            shutil.move(str(src), str(target_path))
        else:
            shutil.copy2(str(src), str(target_path))
    except Exception as e:
        raise RuntimeError(f"Failed to {copy_mode} file to {target_path}: {e}")

    # Generate asset ID
    asset_index = len(registry.assets)
    asset_id = _generate_asset_id(paper_id, asset_index)

    # Compute MIME type
    import mimetypes
    mime_type, _ = mimetypes.guess_type(str(target_path))
    mime_type = mime_type or "application/octet-stream"

    now = datetime.now(timezone.utc).isoformat()

    # Compute relative path from paper dir
    try:
        rel_path = str(target_path.relative_to(paper_dir))
    except ValueError:
        rel_path = str(target_path)

    asset = PaperAsset(
        asset_id=asset_id,
        paper_id=paper_id,
        asset_type=atype,
        filename=safe_name,
        original_filename=src.name,
        relative_path=rel_path,
        sha256=sha256,
        size_bytes=target_path.stat().st_size,
        mime_type=mime_type,
        extension=src.suffix.lower(),
        source=source,
        status="registered",
        created_at=now,
        updated_at=now,
        notes=f"Classified as {atype} (confidence: {confidence:.2f})",
        warnings=warnings,
    )

    # Update registry
    registry.add_asset(asset)
    save_registry(registry)

    return asset
