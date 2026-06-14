"""Scientra Paper Registry & Workspace (Phase 4.0.1).

Human-friendly paper workspaces:
- paper_id remains the primary key everywhere
- 01_Sources/papers/ directories use human-readable names
- Global paper_registry.json maps paper_id <-> display_name
"""

from scientra.papers.paper_registry import (
    build_paper_registry,
    load_paper_registry,
    save_paper_registry,
    get_paper_entry,
)
from scientra.papers.paper_workspace import (
    make_safe_display_name,
    resolve_workspace_dir,
    migrate_workspace_to_display_name,
    migrate_all_workspaces,
)
from scientra.papers.paper_lookup import (
    find_paper_by_id,
    find_paper_by_doi,
    find_paper_by_title,
    search_papers,
)

__all__ = [
    "build_paper_registry",
    "load_paper_registry",
    "save_paper_registry",
    "get_paper_entry",
    "make_safe_display_name",
    "resolve_workspace_dir",
    "migrate_workspace_to_display_name",
    "migrate_all_workspaces",
    "find_paper_by_id",
    "find_paper_by_doi",
    "find_paper_by_title",
    "search_papers",
]
