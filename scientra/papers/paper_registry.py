"""Global Paper Registry — maps paper_id to human-friendly workspace info."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_project_root() -> Path:
    candidate = Path(__file__).resolve().parent.parent.parent
    return candidate


REGISTRY_PATH = _get_project_root() / "05_Knowledge" / "paper_registry.json"


def build_paper_registry(
    metadata_dir: str | None = None,
    papers_source_dir: str | None = None,
) -> dict[str, Any]:
    """Build or rebuild the global paper registry from metadata and existing workspaces.

    Args:
        metadata_dir: Path to YAML metadata directory.
        papers_source_dir: Path to 01_Sources/papers.

    Returns:
        The registry dict.
    """
    root = _get_project_root()
    yaml_dir = Path(metadata_dir) if metadata_dir else root / "02_Metadata" / "yaml"
    papers_dir = Path(papers_source_dir) if papers_source_dir else root / "01_Sources" / "papers"

    # Load metadata
    papers: dict[str, dict[str, Any]] = {}
    title_index: dict[str, str] = {}
    doi_index: dict[str, str] = {}

    if yaml_dir.exists():
        import yaml
        for yf in sorted(yaml_dir.glob("*.metadata.yaml")):
            try:
                doc = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
                pid = doc.get("paper_id", "")
                if not pid:
                    continue

                title = str(doc.get("title", "")).strip()
                year_val = doc.get("year")
                year_str = str(int(year_val)) if year_val else ""
                doi = str(doc.get("doi", "")).strip()

                # Determine existing workspace
                legacy_dir = papers_dir / pid
                display_name = ""
                source_dir = ""

                # Check if a display-name directory already exists
                if legacy_dir.exists():
                    source_dir = str(legacy_dir.relative_to(root))
                else:
                    # Search for a directory containing this paper_id in its paper_assets.json
                    for d in sorted(papers_dir.iterdir()):
                        if d.is_dir() and d.name != "README.md" and not d.name.startswith("paper_"):
                            assets_file = d / "paper_assets.json"
                            if assets_file.exists():
                                try:
                                    ad = json.loads(assets_file.read_text(encoding="utf-8"))
                                    if ad.get("paper_id") == pid:
                                        source_dir = str(d.relative_to(root))
                                        break
                                except Exception:
                                    pass

                # Generate display name
                if title:
                    from scientra.papers.paper_workspace import make_safe_display_name
                    display_name = make_safe_display_name(title, year_str)
                else:
                    display_name = f"Unknown_Title_{pid.replace('paper_', '')[:12]}"

                entry = {
                    "paper_id": pid,
                    "title": title,
                    "year": year_str,
                    "doi": doi,
                    "display_name": display_name,
                    "source_dir": source_dir or f"01_Sources/papers/{display_name}",
                    "legacy_source_dir": f"01_Sources/papers/{pid}" if legacy_dir.exists() else "",
                    "metadata_path": f"02_Metadata/yaml/{yf.name}",
                    "assets_registry_path": "",
                }
                papers[pid] = entry

                # Index
                if title:
                    norm = _normalize(title)
                    title_index[norm] = pid
                if doi:
                    doi_index[doi] = pid
            except Exception:
                pass

    # Resolve assets_registry_path for each paper
    for pid, entry in papers.items():
        src = entry.get("source_dir", "")
        if src:
            entry["assets_registry_path"] = f"{src}/paper_assets.json"

    registry = {
        "papers": papers,
        "title_index": title_index,
        "doi_index": doi_index,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "total_papers": len(papers),
    }

    save_paper_registry(registry)
    return registry


def _normalize(text: str) -> str:
    """Normalize text for fuzzy matching."""
    return re.sub(r'[^a-z0-9]', '', text.lower())


def load_paper_registry() -> dict[str, Any] | None:
    """Load the global paper registry from disk."""
    if not REGISTRY_PATH.exists():
        return None
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_paper_registry(registry: dict[str, Any]) -> None:
    """Save the registry to disk."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_paper_entry(paper_id: str) -> dict[str, Any] | None:
    """Get a single paper's registry entry."""
    reg = load_paper_registry()
    if not reg:
        return None
    return reg.get("papers", {}).get(paper_id)
