"""Dashboard Exporter — export dashboard summary to JSON/MD/CSV."""

from __future__ import annotations
import csv, json
from pathlib import Path
from typing import Any


class DashboardExporter:
    def __init__(self, output_dir: str | Path = "09_Exports/quality_dashboard") -> None:
        self.out = Path(output_dir)

    def export(self, summary: dict, pipeline: list[dict], papers: list[dict],
               recs: list[dict], fmt_json: bool = True, fmt_md: bool = False, fmt_csv: bool = False) -> dict[str, str]:
        self.out.mkdir(parents=True, exist_ok=True)
        paths = {}

        if fmt_json:
            p = self.out / "quality_dashboard_summary.json"
            p.write_text(json.dumps({"summary": summary, "pipeline_health": pipeline, "recommendations": recs}, ensure_ascii=False, indent=2), encoding="utf-8")
            paths["json"] = str(p)

        if fmt_md:
            p = self.out / "quality_dashboard_report.md"
            lines = ["# Quality Dashboard Report", "", f"Papers: {summary.get('total_papers', 0)} | Complete: {summary.get('completed_papers', 0)} | Avg Score: {summary.get('average_completion_score', 0)}",
                      f"P0: {summary.get('p0_count', 0)} P1: {summary.get('p1_count', 0)} Storage: {'✅' if summary.get('storage_layout_ok') else '❌'}",
                      "", "## Pipeline Health"]
            for s in pipeline: lines.append(f"- {s['stage']}: {s['complete_papers']}/{s['total_papers']} ({s['completion_pct']}%)")
            lines.append("\n## Recommendations")
            for r in recs[:10]: lines.append(f"- **[{r['priority']}]** {r['title']}: {r['description']}")
            p.write_text("\n".join(lines), encoding="utf-8")
            paths["md"] = str(p)

        if fmt_csv and papers:
            p = self.out / "paper_quality_table.csv"
            with open(p, "w", newline="", encoding="utf-8") as f:
                if papers:
                    w = csv.DictWriter(f, fieldnames=list(papers[0].keys()))
                    w.writeheader(); w.writerows(papers)
            paths["csv"] = str(p)

        return paths
