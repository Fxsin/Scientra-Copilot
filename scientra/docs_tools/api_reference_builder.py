"""API Reference Builder — generate docs/API_REFERENCE.md from curated list."""

from __future__ import annotations
from pathlib import Path

ENDPOINTS = [
    ("Core", [("/health", "GET"), ("/papers", "GET"), ("/papers/registry", "GET"), ("/papers/lookup", "GET")]),
    ("Evidence & Query", [("/query/assets", "POST"), ("/query/evidence", "POST"), ("/query/cross-assets", "POST")]),
    ("Paper Detail", [("/paper/{id}/metadata", "GET"), ("/paper/{id}/evidence", "GET"), ("/paper/{id}/asset-links", "GET"), ("/paper/{id}/figure-cards", "GET"), ("/paper/{id}/table-cards", "GET"), ("/paper/{id}/supplementaries", "GET"), ("/paper/{id}/datasets", "GET")]),
    ("Knowledge Graph", [("/knowledge-network", "GET"), ("/knowledge/unified-evidence-graph", "GET"), ("/knowledge/unified-evidence-graph/stats", "GET")]),
    ("Datasets", [("/datasets", "GET"), ("/datasets/search", "GET"), ("/datasets/entity/{text}", "GET"), ("/datasets/status", "GET")]),
    ("Research Agent", [("/v1/research-agent/ask", "POST"), ("/v1/research-agent/status", "GET")]),
    ("Validation & Quality", [("/validation/e2e/status", "GET"), ("/quality-dashboard/summary", "GET"), ("/quality-dashboard/recommendations", "GET")]),
    ("Demo", [("/demo/status", "GET"), ("/demo/queries", "GET")]),
]


class APIReferenceBuilder:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def build(self, output_path: str = "docs/API_REFERENCE.md") -> str:
        lines = ["# API Reference", "", "Base: `http://127.0.0.1:8710`", ""]
        for category, endpoints in ENDPOINTS:
            lines.append(f"## {category}")
            lines.append("")
            lines.append("| Endpoint | Method |")
            lines.append("|----------|--------|")
            for ep, method in endpoints:
                lines.append(f"| `{ep}` | {method} |")
            lines.append("")
        lines.append("> All endpoints return `{\"available\": false}` instead of 500 for missing data.")
        content = "\n".join(lines)
        dest = self.root / output_path
        dest.write_text(content, encoding="utf-8")
        return str(dest)
