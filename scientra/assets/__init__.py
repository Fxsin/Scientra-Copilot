"""Scientra Paper Asset Layer (Phase 4.0).

Provides unified asset management for research papers:
- Per-paper asset directories
- Asset classification by type
- Sha256-based deduplication
- Incremental registration without triggering main PDF pipeline
"""

from scientra.assets.types import PaperAsset, PaperAssetRegistry
from scientra.assets.asset_classifier import classify_asset
from scientra.assets.asset_registry import (
    load_registry,
    save_registry,
    find_asset_by_sha256,
    init_registry_for_paper,
)
from scientra.assets.asset_storage import (
    ensure_paper_asset_dirs,
    register_asset_for_paper,
    get_paper_assets_dir,
)
from scientra.assets.asset_status import (
    ASSET_STATUSES,
    VALID_TRANSITIONS,
    can_transition,
)

__all__ = [
    "PaperAsset",
    "PaperAssetRegistry",
    "classify_asset",
    "load_registry",
    "save_registry",
    "find_asset_by_sha256",
    "init_registry_for_paper",
    "ensure_paper_asset_dirs",
    "register_asset_for_paper",
    "get_paper_assets_dir",
    "ASSET_STATUSES",
    "VALID_TRANSITIONS",
    "can_transition",
]
