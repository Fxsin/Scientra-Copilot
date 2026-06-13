"""
Storage Layout v3 — path resolver with legacy fallback.

All paths are relative to project root. New paths preferred; legacy paths
used as fallback when new path has no data. No absolute paths exposed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _get_project_root() -> Path:
    """Resolve project root from this file's location."""
    return Path(__file__).resolve().parent.parent.parent


class StorageLayout:
    """Storage Layout v3 path resolver with legacy fallback."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).resolve() if root else _get_project_root()
        self._config: dict[str, Any] | None = None
        self._paths: dict[str, str] = {}
        self._legacy: dict[str, str] = {}
        self._loaded = False

    def load(self) -> dict[str, Any]:
        """Load storage layout config. Creates from template if missing."""
        if self._loaded:
            return self._config or {}

        import yaml
        config_path = self.root / "Config" / "storage_layout.yaml"
        template_path = self.root / "Config" / "storage_layout.template.yaml"

        # Load or create config
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}
        else:
            # Copy from template
            if template_path.exists():
                try:
                    with open(template_path, encoding="utf-8") as f:
                        self._config = yaml.safe_load(f) or {}
                    with open(config_path, "w", encoding="utf-8") as f:
                        yaml.safe_dump(self._config, f)
                except Exception:
                    self._config = {}

        if not self._config:
            self._config = {"layout_version": "3.0", "paths": {}, "legacy_paths": {}}

        self._paths = self._config.get("paths", {})
        self._legacy = self._config.get("legacy_paths", {})
        self._loaded = True
        return self._config

    def get_path(self, key: str) -> Path:
        """Get new layout path for a key. Creates dir if it doesn't exist."""
        if not self._loaded:
            self.load()
        rel = self._paths.get(key, "")
        if not rel:
            return self.root
        full = self.root / rel
        full.mkdir(parents=True, exist_ok=True)
        return full

    def get_legacy_path(self, key: str) -> Path:
        """Get legacy path for a key."""
        if not self._loaded:
            self.load()
        rel = self._legacy.get(key, "")
        return self.root / rel if rel else self.root

    def resolve_path(self, key: str, legacy_key: str | None = None,
                     prefer_new: bool = True) -> Path:
        """Resolve a path with legacy fallback.

        If prefer_new and new path exists (or is a known key), returns new.
        Falls back to legacy_key if specified and new path doesn't exist
        or has no data.
        """
        new_path = self.get_path(key) if key in self._paths else None

        if prefer_new and new_path is not None:
            # Check if new path has any data
            if new_path.exists() and any(new_path.iterdir()):
                return new_path

        # Fallback to legacy
        if legacy_key:
            legacy_path = self.get_legacy_path(legacy_key)
            if legacy_path.exists():
                return legacy_path

        # Return new path as default (may be empty)
        return new_path if new_path is not None else self.root

    def ensure_all_directories(self) -> list[str]:
        """Create all new layout directories. Returns list of created paths."""
        if not self._loaded:
            self.load()
        created = []
        for key, rel in sorted(self._paths.items()):
            full = self.root / rel
            if not full.exists():
                full.mkdir(parents=True, exist_ok=True)
                created.append(rel)
        return created

    def validate(self) -> dict[str, Any]:
        """Validate storage layout. Returns report dict."""
        if not self._loaded:
            self.load()
        report: dict[str, Any] = {
            "layout_version": self._config.get("layout_version", "unknown"),
            "total_paths": len(self._paths),
            "total_legacy": len(self._legacy),
            "paths_created": 0,
            "paths_existing": 0,
            "legacy_dirs_found": 0,
            "legacy_dirs_missing": 0,
            "issues": [],
        }
        for rel in self._paths.values():
            full = self.root / rel
            if full.exists():
                report["paths_existing"] += 1
            else:
                report["issues"].append(f"New path not created: {rel}")

        for key, rel in self._legacy.items():
            full = self.root / rel
            if full.exists():
                report["legacy_dirs_found"] += 1
            else:
                report["legacy_dirs_missing"] += 1
                report["issues"].append(f"Legacy dir missing: {rel} (key={key})")

        return report

    def write_report(self) -> Path:
        """Write storage layout report to 10_System/registry/. Returns path."""
        report = self.validate()
        report_path = self.root / "10_System" / "registry" / "storage_layout_v3_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Storage Layout v3 Report", "",
            f"Layout version: {report['layout_version']}",
            f"Total paths: {report['total_paths']}",
            f"Paths existing: {report['paths_existing']}",
            f"Total legacy dirs: {report['total_legacy']}",
            f"Legacy dirs found: {report['legacy_dirs_found']}",
            f"Legacy dirs missing: {report['legacy_dirs_missing']}",
            "", "## Issues", "",
        ]
        if report["issues"]:
            for issue in report["issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("- No issues")
        lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path


# ── Module-level singleton ──
_default_layout: StorageLayout | None = None


def get_storage() -> StorageLayout:
    """Get the default storage layout singleton."""
    global _default_layout
    if _default_layout is None:
        _default_layout = StorageLayout()
        _default_layout.load()
    return _default_layout


def get_path(key: str) -> Path:
    return get_storage().get_path(key)


def resolve_path(key: str, legacy_key: str | None = None, prefer_new: bool = True) -> Path:
    return get_storage().resolve_path(key, legacy_key, prefer_new)
