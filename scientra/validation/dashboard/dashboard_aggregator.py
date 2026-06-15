"""Dashboard Aggregator — compute dashboard metrics from P6.0 data."""

from __future__ import annotations
from typing import Any
from scientra.validation.dashboard.dashboard_schema import make_summary, make_pipeline_health


class DashboardAggregator:
    def aggregate(self, data: dict[str, Any]) -> dict[str, Any]:
        papers = data.get("paper_details") or []
        total = len(papers)
        completed = sum(1 for p in papers if p.get("completion_score", 0) >= 0.5)
        warned = sum(1 for p in papers if p.get("warnings") and len(p.get("warnings", [])) > 0)
        avg = sum(p.get("completion_score", 0) for p in papers) / total if total else 0

        recs = data.get("recommendations") or {}
        mods = data.get("modules") or {}
        storage = data.get("storage") or {}
        qe = data.get("query_eval") or {}
        ae = data.get("agent_eval") or {}

        summary = make_summary(
            total, completed, warned, avg,
            p0=len(recs.get("P0", [])), p1=len(recs.get("P1", [])),
            p2=len(recs.get("P2", [])), p3=len(recs.get("P3", [])),
            modules_ok=mods.get("all_modules_ok", False),
            storage_ok=storage.get("v3_compliant", False),
            query_pass=qe.get("passed", 0), agent_pass=ae.get("passed", 0),
            last_run=(data.get("summary") or {}).get("last_validation_run", ""),
        )

        stages = [
            ("Source", "has_source"), ("Parse", "has_parse"), ("Evidence", "has_evidence"),
            ("Asset Linking", "has_asset_links"), ("Figure Intelligence", "has_figure_intelligence"),
            ("Table Intelligence", "has_table_intelligence"), ("Supplementary Intelligence", "has_supplementary_intelligence"),
            ("Dataset Intelligence", "has_dataset_intelligence"), ("Unified Graph", "has_graph_subgraph"),
            ("Cross-Asset Query", "has_cross_asset_support"), ("Research Agent", "has_agent_traces"),
        ]
        pipeline = []
        for name, key in stages:
            c = sum(1 for p in papers if p.get(key))
            pipeline.append(make_pipeline_health(name, total, c, "ok" if c > total * 0.3 else "needs_attention"))

        return {"summary": summary, "pipeline_health": pipeline, "paper_count": total}
