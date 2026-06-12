"""
Asset Registry — tracks which assets have been generated per paper.

Reads and writes 06_PDF_DataAssets/00_registry/asset_registry.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import (
    AssetRegistryFile,
    BuildStatus,
    RegistryEntry,
)


class AssetRegistry:
    """Manages the per-paper asset registry."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.registry_dir = self.root / "06_PDF_DataAssets" / "00_registry"
        self.registry_path = self.registry_dir / "asset_registry.json"
        self._data: AssetRegistryFile | None = None

    def load(self) -> AssetRegistryFile:
        """Load registry from disk, or return empty default."""
        if self.registry_path.exists():
            try:
                raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
                self._data = AssetRegistryFile(**raw)
                return self._data
            except Exception:
                pass
        self._data = AssetRegistryFile()
        return self._data

    def save(self) -> None:
        """Persist registry to disk."""
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        if self._data is None:
            self._data = AssetRegistryFile()
        self._data.generated_at = datetime.now(timezone.utc).isoformat()
        tmp = self.registry_path.with_suffix(".tmp")
        tmp.write_text(
            self._data.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )
        tmp.replace(self.registry_path)

    def get_entry(self, paper_id: str) -> RegistryEntry | None:
        """Return the registry entry for a paper, or None."""
        data = self.load()
        for entry in data.entries:
            if entry.paper_id == paper_id:
                return entry
        return None

    def upsert_entry(self, entry: RegistryEntry) -> None:
        """Insert or update a registry entry."""
        data = self.load()
        for i, existing in enumerate(data.entries):
            if existing.paper_id == entry.paper_id:
                data.entries[i] = entry
                self._data = data
                self.save()
                return
        data.entries.append(entry)
        self._data = data
        self.save()

    def remove_entry(self, paper_id: str) -> bool:
        """Remove a registry entry. Returns True if found and removed."""
        data = self.load()
        for i, entry in enumerate(data.entries):
            if entry.paper_id == paper_id:
                data.entries.pop(i)
                self._data = data
                self.save()
                return True
        return False

    def list_papers(self) -> list[str]:
        """Return all paper_ids in the registry."""
        data = self.load()
        return [e.paper_id for e in data.entries]

    def all_entries(self) -> list[RegistryEntry]:
        """Return all registry entries."""
        return self.load().entries

    def status_summary(self) -> dict[str, Any]:
        """Return a human-readable status summary."""
        data = self.load()
        statuses: dict[str, int] = {}
        total_assets: dict[str, int] = {}
        for entry in data.entries:
            s = entry.build_status.value
            statuses[s] = statuses.get(s, 0) + 1
            total_assets["sections"] = total_assets.get("sections", 0) + entry.section_assets
            total_assets["methods"] = total_assets.get("methods", 0) + entry.method_assets
            total_assets["results"] = total_assets.get("results", 0) + entry.result_assets
            total_assets["entities"] = total_assets.get("entities", 0) + entry.entity_assets
            total_assets["claims"] = total_assets.get("claims", 0) + entry.claim_assets
            total_assets["agent_chunks"] = total_assets.get("agent_chunks", 0) + entry.agent_chunks
        return {
            "total_papers": data.total_papers,
            "by_status": statuses,
            "total_assets": total_assets,
        }

    def update_totals(self) -> None:
        """Sync total_papers count with entries length."""
        data = self.load()
        data.total_papers = len(data.entries)
        self._data = data
        self.save()
