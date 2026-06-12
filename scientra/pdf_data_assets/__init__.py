"""
PDF Data Assets — Phase 0 assetization layer.

Converts existing evidence, summaries, and metadata into structured,
traceable, agent-ready data assets. Enhances (does NOT replace) 03_Evidence.

Usage:
    from scientra.pdf_data_assets.build_assets import build_all, build_paper, show_status
    from scientra.pdf_data_assets.schemas import PDFAssetBase, SectionAsset, ...
"""

from __future__ import annotations

__all__ = [
    "PDFAssetBase",
    "SectionAsset",
    "MethodAsset",
    "ResultAsset",
    "FigureAsset",
    "TableAsset",
    "EntityAsset",
    "ClaimAsset",
    "EvidenceLink",
    "SupplementaryLink",
    "AgentChunkAsset",
    "AssetRegistry",
    "build_all",
    "build_paper",
    "show_status",
]

# Schemas are importable directly
from scientra.pdf_data_assets.schemas import (
    PDFAssetBase,
    SectionAsset,
    MethodAsset,
    ResultAsset,
    FigureAsset,
    TableAsset,
    EntityAsset,
    ClaimAsset,
    EvidenceLink,
    SupplementaryLink,
    AgentChunkAsset,
)

# Registry
from scientra.pdf_data_assets.asset_registry import AssetRegistry

# Build entry points
from scientra.pdf_data_assets.build_assets import build_all, build_paper, show_status
