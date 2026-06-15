"""Release Report Builder — generate markdown and JSON reports."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class ReleaseReportBuilder:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def build(self, report: dict) -> dict[str, str]:
        out = self.root / "10_System/release"
        out.mkdir(parents=True, exist_ok=True)

        # JSON
        jp = out / "release_check_summary.json"
        jp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        # MD
        mp = out / "release_check_report.md"
        lines = ["# Release Check Report", "", f"Passed: {'✅' if report['passed'] else '❌'}", f"Total issues: {report['total_issues']}"]
        for level in ["P0", "P1", "P2", "P3"]:
            items = report.get(level, [])
            if items:
                lines.append(f"\n## {level} ({len(items)})")
                for item in items[:15]:
                    lines.append(f"- **{item.get('title', '')}**: {item.get('detail', '')} ({item.get('file', '')})")
        mp.write_text("\n".join(lines), encoding="utf-8")

        return {"json": str(jp), "markdown": str(mp)}
