"""CLI Reference Builder — generate docs/CLI_REFERENCE.md."""

from __future__ import annotations
from pathlib import Path

SCRIPTS = [
    ("Setup", ["Scripts/setup.py", "Scripts/dev_restart.py"]),
    ("Import & Assets", ["Scripts/add_paper_asset.py", "Scripts/init_paper_assets.py"]),
    ("Asset Intelligence (P4)", ["Scripts/build_asset_links.py", "Scripts/build_figure_intelligence.py", "Scripts/build_table_intelligence.py", "Scripts/build_supplementary_intelligence.py"]),
    ("Knowledge Layer (P5)", ["Scripts/build_unified_evidence_graph.py", "Scripts/query_cross_assets.py", "Scripts/build_dataset_intelligence.py", "Scripts/query_datasets.py", "Scripts/ask_research_agent.py"]),
    ("Quality & Demo (P6)", ["Scripts/run_e2e_validation.py", "Scripts/export_quality_dashboard.py", "Scripts/create_demo_project.py", "Scripts/run_demo_queries.py", "Scripts/update_docs.py"]),
]


class CLIReferenceBuilder:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def build(self, output_path: str = "docs/CLI_REFERENCE.md") -> str:
        lines = ["# CLI Reference", ""]
        for category, scripts in SCRIPTS:
            lines.append(f"## {category}")
            lines.append("")
            lines.append("| Script | Purpose |")
            lines.append("|--------|---------|")
            for s in scripts:
                p = self.root / s
                purpose = self._read_purpose(p)
                exists = "✅" if p.exists() else "❌"
                lines.append(f"| `{s}` {exists} | {purpose} |")
            lines.append("")
        content = "\n".join(lines)
        dest = self.root / output_path
        dest.write_text(content, encoding="utf-8")
        return str(dest)

    @staticmethod
    def _read_purpose(path: Path) -> str:
        if not path.exists(): return "Missing"
        try:
            first = path.read_text(encoding="utf-8").split("\n")[1:4]
            for line in first:
                line = line.strip().strip('"').strip("'")
                if line and not line.startswith("#") and not line.startswith('"""') and len(line) > 10:
                    return line[:80]
            return "See script"
        except Exception:
            return "Read error"
