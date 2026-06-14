"""Graph Summary Builder — generate markdown summary of the unified graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_summary_md(nodes: list[dict], edges: list[dict], validation: dict, output_path: Path) -> None:
    """Generate a markdown summary of the unified evidence graph."""
    node_types: dict[str, int] = {}
    edge_types: dict[str, int] = {}
    papers: set[str] = set()
    for n in nodes:
        node_types[n.get("node_type", "?")] = node_types.get(n.get("node_type", "?"), 0) + 1
        if n.get("paper_id"):
            papers.add(n["paper_id"])
    for e in edges:
        edge_types[e.get("edge_type", "?")] = edge_types.get(e.get("edge_type", "?"), 0) + 1

    lines = [
        "# Unified Evidence Graph Summary",
        f"Generated: P5.1",
        "",
        "## Overview",
        f"- **Total Nodes:** {len(nodes)}",
        f"- **Total Edges:** {len(edges)}",
        f"- **Papers:** {len(papers)}",
        "",
        "## Node Distribution",
        "| Type | Count |",
        "|------|-------|",
    ]
    for t, c in sorted(node_types.items()):
        lines.append(f"| {t} | {c} |")

    lines.extend(["", "## Edge Distribution", "| Type | Count |", "|------|-------|"])
    for t, c in sorted(edge_types.items()):
        lines.append(f"| {t} | {c} |")

    lines.extend(["", "## Validation", f"- Valid: {validation.get('valid', False)}",
                   f"- Errors: {validation.get('error_count', 0)}",
                   f"- Warnings: {validation.get('warning_count', 0)}",
                   f"- Orphan Nodes: {validation.get('orphan_count', 0)}"])

    if validation.get("warnings"):
        lines.append("\n### Warnings")
        for w in validation["warnings"][:15]:
            lines.append(f"- {w}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
