"""Quality Report Builder — generate markdown, JSON, CSV reports."""

from __future__ import annotations
import csv, io, json
from pathlib import Path
from typing import Any


class QualityReportBuilder:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)

    def build_all(self, inventory: dict, paper_status: list[dict], storage: dict,
                   module_health: dict, query_eval: dict, agent_eval: dict,
                   recommendations: dict) -> dict[str, str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        summary = {
            "pipeline_inventory": {k: v for k, v in inventory.items()},
            "paper_count": len(paper_status),
            "papers_complete": sum(1 for p in paper_status if p.get("completion_score", 0) >= 0.5),
            "storage_v3_compliant": storage.get("v3_compliant", False),
            "db_v2_clean": storage.get("db_v2_clean", False),
            "modules_ok": module_health.get("all_modules_ok", False),
            "scripts_ok": module_health.get("all_scripts_exist", False),
            "query_eval_passed": query_eval.get("passed", 0),
            "query_eval_total": query_eval.get("total_queries", 0),
            "agent_eval_passed": agent_eval.get("passed", 0),
            "agent_eval_total": agent_eval.get("total_queries", 0),
            "recommendations_p0": len(recommendations.get("P0", [])),
            "recommendations_p1": len(recommendations.get("P1", [])),
            "recommendations_total": sum(len(v) for v in recommendations.values()),
        }
        jp = self.output_dir / "e2e_validation_summary.json"
        jp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        paths["summary_json"] = str(jp)

        # CSV
        cp = self.output_dir / "paper_status_matrix.csv"
        if paper_status:
            with open(cp, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(paper_status[0].keys()))
                w.writeheader(); w.writerows(paper_status)
            paths["csv"] = str(cp)

        # MD
        mp = self.output_dir / "e2e_validation_report.md"
        self._write_md(mp, summary, paper_status, storage, module_health, query_eval, agent_eval, recommendations)
        paths["markdown"] = str(mp)

        return paths

    def _write_md(self, p: Path, summary: dict, paper_status: list, storage: dict,
                   mh: dict, qe: dict, ae: dict, recs: dict) -> None:
        lines = [
            "# P6.0 End-to-End Validation Report",
            "", "## Summary",
            f"- Papers: {summary['paper_count']} (complete: {summary['papers_complete']})",
            f"- Storage v3: {'✅' if summary['storage_v3_compliant'] else '❌'}",
            f"- DB/DB_v2 clean: {'✅' if summary['db_v2_clean'] else '❌'}",
            f"- Modules: {'✅' if summary['modules_ok'] else '❌'}",
            f"- Scripts: {'✅' if summary['scripts_ok'] else '❌'}",
            f"- Query eval: {summary['query_eval_passed']}/{summary['query_eval_total']}",
            f"- Agent eval: {summary['agent_eval_passed']}/{summary['agent_eval_total']}",
            "", "## Recommendations",
            f"P0: {summary['recommendations_p0']} | P1: {summary['recommendations_p1']} | Total: {summary['recommendations_total']}",
        ]
        for level in ["P0", "P1", "P2", "P3"]:
            items = recs.get(level, [])
            if items:
                lines.append(f"\n### {level}")
                for item in items[:10]:
                    lines.append(f"- **{item.get('title', '')}**: {item.get('detail', '')}")

        if storage.get("warnings"):
            lines.append("\n## Storage Warnings")
            for w in storage["warnings"][:10]:
                lines.append(f"- {w}")

        p.write_text("\n".join(lines), encoding="utf-8")
