"""Paper Workspace — human-friendly directory naming and migration."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


_PAPERS_DIR = _get_project_root() / "01_Sources" / "papers"

# Characters unsafe for filenames on Windows + Linux
_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_UNDERSCORE_RE = re.compile(r'_+')


def make_safe_display_name(title: str, year: str | None = None, max_length: int = 80) -> str:
    """Create a human-friendly, filesystem-safe display name from a paper title.

    Format: {year}_{title_slug}

    Rules:
    - Remove unsafe chars
    - Replace spaces with underscore
    - Collapse multiple underscores
    - Max length 80
    - Fallback if title is empty
    """
    if not title or not title.strip():
        short = year or "Unknown"
        return f"{short}_Untitled_Paper"

    # Clean
    cleaned = _UNSAFE_RE.sub('', title)
    cleaned = cleaned.replace(' ', '_')
    cleaned = cleaned.replace('-', '_')
    cleaned = cleaned.replace(',', '')
    cleaned = cleaned.replace('.', '')
    cleaned = cleaned.replace(';', '')
    cleaned = cleaned.replace('(', '').replace(')', '')
    cleaned = cleaned.replace('[', '').replace(']', '')
    cleaned = cleaned.replace("'", '').replace('"', '')
    cleaned = _MULTI_UNDERSCORE_RE.sub('_', cleaned)
    cleaned = cleaned.strip('_')

    # Capitalize first letter of each word
    parts = cleaned.split('_')
    parts = [p[0].upper() + p[1:] if p else p for p in parts]
    cleaned = '_'.join(parts)

    # Add year prefix
    if year:
        prefix = str(year)
    else:
        prefix = "NoYear"

    name = f"{prefix}_{cleaned}"

    # Truncate
    if len(name) > max_length:
        # Keep prefix, truncate title part
        avail = max_length - len(prefix) - 15  # reserve for hash
        name = f"{prefix}_{cleaned[:avail]}"

    return name[:max_length]


def resolve_workspace_dir(paper_id: str) -> Path:
    """Resolve the actual workspace directory for a paper_id.

    Checks:
    1. Global registry → source_dir
    2. Legacy path 01_Sources/papers/{paper_id}
    3. Fallback to legacy path creation

    Returns the Path to the paper's workspace directory.
    """
    # Try registry first
    from scientra.papers.paper_registry import load_paper_registry
    reg = load_paper_registry()
    if reg:
        entry = reg.get("papers", {}).get(paper_id)
        if entry:
            src = entry.get("source_dir", "")
            if src:
                full = _get_project_root() / src
                if full.exists():
                    return full
            # Try legacy
            legacy = entry.get("legacy_source_dir", "")
            if legacy:
                full = _get_project_root() / legacy
                if full.exists():
                    return full

    # Fallback: legacy path
    legacy = _PAPERS_DIR / paper_id
    if legacy.exists():
        return legacy

    # Create legacy path as last resort
    legacy.mkdir(parents=True, exist_ok=True)
    return legacy


def migrate_workspace_to_display_name(
    paper_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Migrate a single paper's workspace from paper_id to display name.

    Args:
        paper_id: The paper ID to migrate.
        dry_run: If True, only plan without executing.

    Returns:
        Migration result dict.
    """
    result = {
        "paper_id": paper_id,
        "status": "unknown",
        "old_dir": "",
        "new_dir": "",
        "error": "",
    }

    from scientra.papers.paper_registry import load_paper_registry, save_paper_registry, build_paper_registry

    # Ensure registry exists
    reg = load_paper_registry()
    if not reg:
        build_paper_registry()
        reg = load_paper_registry()
        if not reg:
            result["status"] = "error"
            result["error"] = "Cannot build registry"
            return result

    entry = reg.get("papers", {}).get(paper_id)
    if not entry:
        result["status"] = "error"
        result["error"] = f"Paper {paper_id} not in registry"
        return result

    old_src = entry.get("source_dir", "") or f"01_Sources/papers/{paper_id}"
    old_path = _get_project_root() / old_src

    if not old_path.exists():
        result["status"] = "skipped"
        result["error"] = f"Source directory does not exist: {old_src}"
        return result

    # Check if already migrated (directory name != paper_id)
    if old_path.name != paper_id and not old_path.name.startswith("paper_"):
        result["status"] = "skipped"
        result["old_dir"] = old_src
        result["new_dir"] = old_src
        result["error"] = "Already migrated"
        return result

    display_name = entry.get("display_name", "")
    if not display_name:
        result["status"] = "error"
        result["error"] = "No display name"
        return result

    new_path = _PAPERS_DIR / display_name

    # Handle name collision
    counter = 0
    while new_path.exists():
        short_hash = paper_id.replace("paper_", "")[:6] if paper_id.startswith("paper_") else ""
        new_name = f"{display_name}_{short_hash}"
        new_path = _PAPERS_DIR / new_name
        counter += 1
        if counter > 10:
            result["status"] = "error"
            result["error"] = "Cannot resolve name collision"
            return result

    result["old_dir"] = str(old_path.relative_to(_get_project_root()))
    result["new_dir"] = str(new_path.relative_to(_get_project_root()))

    if dry_run:
        result["status"] = "planned"
        return result

    # Execute migration
    try:
        shutil.move(str(old_path), str(new_path))

        # Update paper_assets.json inside the workspace
        assets_file = new_path / "paper_assets.json"
        if assets_file.exists():
            ad = json.loads(assets_file.read_text(encoding="utf-8"))
            ad["workspace_dir"] = str(new_path.relative_to(_get_project_root()))
            ad["legacy_workspace_dir"] = str(old_path.relative_to(_get_project_root()))
            ad["display_title"] = entry.get("title", "")
            assets_file.write_text(
                json.dumps(ad, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # Update registry
        entry["source_dir"] = str(new_path.relative_to(_get_project_root()))
        entry["legacy_source_dir"] = str(old_path.relative_to(_get_project_root()))
        entry["assets_registry_path"] = f"{entry['source_dir']}/paper_assets.json"
        save_paper_registry(reg)

        result["status"] = "migrated"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def migrate_all_workspaces(dry_run: bool = True) -> dict[str, Any]:
    """Migrate all paper workspaces to display names.

    Args:
        dry_run: If True, only plan.

    Returns:
        Migration report dict.
    """
    from scientra.papers.paper_registry import load_paper_registry, build_paper_registry

    # Ensure registry is built
    reg = load_paper_registry()
    if not reg:
        reg = build_paper_registry()
    reg = load_paper_registry()
    if not reg:
        return {"error": "Cannot build registry", "total_papers": 0}

    papers = reg.get("papers", {})
    report = {
        "total_papers": len(papers),
        "planned": 0,
        "migrated": 0,
        "skipped": 0,
        "conflicts": 0,
        "errors": 0,
        "dry_run": dry_run,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": [],
    }

    for pid in sorted(papers.keys()):
        result = migrate_workspace_to_display_name(pid, dry_run=dry_run)
        report["details"].append(result)

        status = result.get("status", "unknown")
        if status == "planned":
            report["planned"] += 1
        elif status == "migrated":
            report["migrated"] += 1
        elif status == "skipped":
            report["skipped"] += 1
        elif status == "error":
            report["errors"] += 1

    # Save report
    report_dir = _get_project_root() / "10_System" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "paper_workspace_migration_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report
