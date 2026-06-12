"""
Quality Report Builder — generates a full-library quality report in Markdown.

Aggregates data from:
  - asset_registry.json
  - quality_status.json
  - filtered_entities.json (per paper)
  - agent_chunks.quality.jsonl (per paper)
  - claims_evidence.quality.json (per paper)

Output: 06_PDF_DataAssets/00_registry/pdf_data_assets_quality_report.md
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QualityReportBuilder:
    """Builds a comprehensive quality report across all papers."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.data_dir = self.root / "06_PDF_DataAssets"
        self.registry_path = self.data_dir / "00_registry" / "asset_registry.json"

    def build(self) -> dict[str, Any]:
        """Generate the full quality report. Returns report data + writes .md file."""
        if not self.registry_path.exists():
            return {"error": "no_registry"}

        reg = json.loads(self.registry_path.read_text(encoding="utf-8"))
        entries = reg.get("entries", [])
        success_entries = [e for e in entries if e.get("build_status") == "success"]

        report: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_papers_in_registry": len(entries),
            "successful_papers": len(success_entries),
            "asset_totals": self._aggregate_asset_totals(entries),
            "per_paper_distribution": self._per_paper_distribution(entries),
            "entity_noise": self._entity_noise_summary(success_entries),
            "chunk_quality": self._chunk_quality_summary(success_entries),
            "claim_quality": self._claim_quality_summary(success_entries),
            "top_entities": self._top_entities(success_entries, top_n=20),
            "top_methods": self._top_methods(success_entries, top_n=20),
            "quality_risks": [],
            "recommendations": [],
        }

        # Quality risks
        ent_noise = report["entity_noise"]
        if ent_noise.get("avg_noise_pct", 100) > 60:
            report["quality_risks"].append(
                f"High entity noise ({ent_noise.get('avg_noise_pct', 0):.1f}% filtered). "
                "Consider tightening entity extraction regex patterns."
            )

        chunk_q = report["chunk_quality"]
        if chunk_q.get("avg_vector_ready_pct", 100) < 70:
            report["quality_risks"].append(
                f"Low vector-ready chunk rate ({chunk_q.get('avg_vector_ready_pct', 0):.1f}%). "
                "Review chunk text length and source_asset_ids completeness."
            )

        claim_q = report["claim_quality"]
        if claim_q.get("avg_needs_ai_pct", 0) > 50:
            report["quality_risks"].append(
                f"High proportion of claims need AI interpretation "
                f"({claim_q.get('avg_needs_ai_pct', 0):.1f}%). "
                "Consider running LLM-based claim validation in a future phase."
            )

        # Recommendations
        report["recommendations"].append(
            "Phase 0.5 complete. Entity noise filter applied. Review filtered entities before embedding."
        )
        if chunk_q.get("avg_vector_ready_pct", 100) < 90:
            report["recommendations"].append(
                "Improve chunk quality by ensuring all chunks have source_asset_ids and text >= 30 chars."
            )
        if claim_q.get("avg_has_evidence_pct", 100) < 50:
            report["recommendations"].append(
                "Increase claim-evidence linkage by enhancing result_discussion_links extraction."
            )
        report["recommendations"].append(
            "Phase 1 ready: Figure + Caption Extraction can proceed when quality risks are addressed."
        )

        # Write markdown
        md_content = self._build_markdown(report)
        md_path = self.data_dir / "00_registry" / "pdf_data_assets_quality_report.md"
        tmp = md_path.with_suffix(".tmp")
        tmp.write_text(md_content, encoding="utf-8")
        tmp.replace(md_path)

        report["md_path"] = str(md_path)
        return report

    def _aggregate_asset_totals(self, entries: list[dict[str, Any]]) -> dict[str, int]:
        """Sum asset counts across all entries."""
        totals: dict[str, int] = {}
        for e in entries:
            for key in ["section_assets", "method_assets", "result_assets",
                         "entity_assets", "claim_assets", "agent_chunks",
                         "figure_assets", "table_assets", "supplementary_links"]:
                totals[key] = totals.get(key, 0) + e.get(key, 0)
        return totals

    def _per_paper_distribution(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return per-paper counts sorted by paper_id."""
        dist: list[dict[str, Any]] = []
        for e in entries:
            dist.append({
                "paper_id": e.get("paper_id", ""),
                "methods": e.get("method_assets", 0),
                "results": e.get("result_assets", 0),
                "entities": e.get("entity_assets", 0),
                "claims": e.get("claim_assets", 0),
                "chunks": e.get("agent_chunks", 0),
            })
        return sorted(dist, key=lambda x: x["paper_id"])

    def _entity_noise_summary(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate entity noise filter stats across papers."""
        noise_pcts: list[float] = []
        total_original = 0
        total_kept = 0
        aggregate_stats: dict[str, int] = {}

        for e in entries:
            pid = e.get("paper_id", "")
            filter_path = self.data_dir / "06_entities" / pid / "filtered_entities.json"
            if not filter_path.exists():
                continue
            try:
                data = json.loads(filter_path.read_text(encoding="utf-8"))
                orig = data.get("original_count", 0)
                kept = data.get("kept_count", 0)
                total_original += orig
                total_kept += kept
                if orig > 0:
                    noise_pcts.append(round((orig - kept) / orig * 100, 1))
                for k, v in data.get("filter_stats", {}).items():
                    aggregate_stats[k] = aggregate_stats.get(k, 0) + v
            except Exception:
                pass

        avg_noise = round(sum(noise_pcts) / len(noise_pcts), 1) if noise_pcts else 0
        return {
            "papers_checked": len(noise_pcts),
            "total_entities_original": total_original,
            "total_entities_kept": total_kept,
            "total_entities_filtered": total_original - total_kept,
            "avg_noise_pct": avg_noise,
            "aggregate_stats": aggregate_stats,
        }

    def _chunk_quality_summary(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate chunk quality stats across papers."""
        vr_pcts: list[float] = []
        avg_scores: list[float] = []
        total_chunks = 0
        total_vr = 0

        for e in entries:
            pid = e.get("paper_id", "")
            quality_path = self.data_dir / "09_agent_chunks" / pid / "agent_chunks.quality.jsonl"
            if not quality_path.exists():
                continue
            try:
                chunks: list[dict] = []
                for line in quality_path.read_text(encoding="utf-8").strip().splitlines():
                    if line.strip():
                        chunks.append(json.loads(line))
                n = len(chunks)
                if n == 0:
                    continue
                vr = sum(1 for c in chunks if c.get("vector_ready", False))
                scores = [c.get("quality_score", 0) for c in chunks]
                total_chunks += n
                total_vr += vr
                vr_pcts.append(round(vr / n * 100, 1))
                avg_scores.append(round(sum(scores) / n, 1))
            except Exception:
                pass

        return {
            "papers_checked": len(vr_pcts),
            "total_chunks": total_chunks,
            "total_vector_ready": total_vr,
            "avg_vector_ready_pct": round(sum(vr_pcts) / len(vr_pcts), 1) if vr_pcts else 0,
            "avg_chunk_quality_score": round(sum(avg_scores) / len(avg_scores), 1) if avg_scores else 0,
        }

    def _claim_quality_summary(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate claim quality stats across papers."""
        needs_ai_pcts: list[float] = []
        has_ev_pcts: list[float] = []
        total_claims = 0
        total_needs_ai = 0
        total_has_ev = 0

        for e in entries:
            pid = e.get("paper_id", "")
            quality_path = self.data_dir / "07_claims_evidence" / pid / "claims_evidence.quality.json"
            if not quality_path.exists():
                continue
            try:
                data = json.loads(quality_path.read_text(encoding="utf-8"))
                qs = data.get("quality_summary", {})
                tc = qs.get("total_claims", 0)
                if tc == 0:
                    continue
                nai = qs.get("needs_ai_interpretation", 0)
                he = qs.get("has_evidence_pct", 0)
                total_claims += tc
                total_needs_ai += nai
                total_has_ev += int(tc * he / 100)
                needs_ai_pcts.append(qs.get("needs_ai_pct", 0))
                has_ev_pcts.append(he)
            except Exception:
                pass

        return {
            "papers_checked": len(needs_ai_pcts),
            "total_claims": total_claims,
            "total_needs_ai": total_needs_ai,
            "avg_needs_ai_pct": round(sum(needs_ai_pcts) / len(needs_ai_pcts), 1) if needs_ai_pcts else 0,
            "avg_has_evidence_pct": round(sum(has_ev_pcts) / len(has_ev_pcts), 1) if has_ev_pcts else 0,
        }

    def _top_entities(self, entries: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
        """Find top N most frequent kept entities."""
        counter: Counter = Counter()
        for e in entries:
            pid = e.get("paper_id", "")
            filter_path = self.data_dir / "06_entities" / pid / "filtered_entities.json"
            if not filter_path.exists():
                continue
            try:
                data = json.loads(filter_path.read_text(encoding="utf-8"))
                for ent in data.get("entities", []):
                    if ent.get("entity_status") == "kept":
                        name = ent.get("entity_name", "")
                        etype = ent.get("entity_type", "unknown")
                        freq = ent.get("frequency", 1)
                        counter[(name, etype)] += freq
            except Exception:
                pass

        return [
            {"entity_name": name, "entity_type": etype, "total_frequency": count}
            for (name, etype), count in counter.most_common(top_n)
        ]

    def _top_methods(self, entries: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
        """Find top N most common method names."""
        counter: Counter = Counter()
        for e in entries:
            pid = e.get("paper_id", "")
            meth_path = self.data_dir / "04_methods" / pid / "methods.json"
            if not meth_path.exists():
                continue
            try:
                methods = json.loads(meth_path.read_text(encoding="utf-8"))
                for m in methods:
                    name = m.get("method_name", "")
                    if name:
                        counter[name] += 1
            except Exception:
                pass

        return [
            {"method_name": name, "paper_count": count}
            for name, count in counter.most_common(top_n)
        ]

    def _build_markdown(self, report: dict[str, Any]) -> str:
        """Render the report as Markdown."""
        lines: list[str] = []
        lines.append("# Scientra Copilot — PDF Data Assets Quality Report")
        lines.append(f"")
        lines.append(f"**Generated:** {report['generated_at']}")
        lines.append(f"**Phase:** 0.5 — Quality Verification & Agent Readiness")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        # 1. Overview
        lines.append(f"## 1. Overview")
        lines.append(f"")
        lines.append(f"- Total papers in registry: **{report['total_papers_in_registry']}**")
        lines.append(f"- Successful builds: **{report['successful_papers']}**")
        lines.append(f"")

        # 2. Asset Totals
        at = report.get("asset_totals", {})
        lines.append(f"## 2. Asset Totals")
        lines.append(f"")
        lines.append(f"| Asset Type | Count |")
        lines.append(f"|---|---|")
        for k, v in at.items():
            lines.append(f"| {k} | {v} |")
        lines.append(f"")

        # 3. Per-Paper Distribution
        dist = report.get("per_paper_distribution", [])
        lines.append(f"## 3. Per-Paper Distribution")
        lines.append(f"")
        if dist:
            lines.append(f"| Paper ID | Methods | Results | Entities | Claims | Chunks |")
            lines.append(f"|---|---|---|---|---|---|")
            for d in dist[:30]:  # cap at 30 rows
                pid_short = d["paper_id"][:50] + "..." if len(d["paper_id"]) > 50 else d["paper_id"]
                lines.append(f"| {pid_short} | {d['methods']} | {d['results']} | {d['entities']} | {d['claims']} | {d['chunks']} |")
            if len(dist) > 30:
                lines.append(f"| ... | ... | ... | ... | ... | ... |")
                lines.append(f"| *({len(dist) - 30} more papers)* | | | | | |")
        lines.append(f"")

        # 4. Entity Noise
        en = report.get("entity_noise", {})
        lines.append(f"## 4. Entity Noise Filtering")
        lines.append(f"")
        lines.append(f"- Papers checked: **{en.get('papers_checked', 0)}**")
        lines.append(f"- Total entities (original): **{en.get('total_entities_original', 0)}**")
        lines.append(f"- Total entities (kept): **{en.get('total_entities_kept', 0)}**")
        lines.append(f"- Total entities (filtered): **{en.get('total_entities_filtered', 0)}**")
        lines.append(f"- Average noise rate: **{en.get('avg_noise_pct', 0):.1f}%**")
        lines.append(f"")
        agg = en.get("aggregate_stats", {})
        if agg:
            lines.append(f"### Filter Breakdown")
            lines.append(f"")
            lines.append(f"| Reason | Count |")
            lines.append(f"|---|---|")
            for k, v in sorted(agg.items(), key=lambda x: -x[1]):
                lines.append(f"| {k} | {v} |")
        lines.append(f"")

        # 5. Chunk Quality
        cq = report.get("chunk_quality", {})
        lines.append(f"## 5. Agent Chunk Quality")
        lines.append(f"")
        lines.append(f"- Papers checked: **{cq.get('papers_checked', 0)}**")
        lines.append(f"- Total chunks: **{cq.get('total_chunks', 0)}**")
        lines.append(f"- Vector-ready: **{cq.get('total_vector_ready', 0)}**")
        lines.append(f"- Avg vector-ready rate: **{cq.get('avg_vector_ready_pct', 0):.1f}%**")
        lines.append(f"- Avg chunk quality score: **{cq.get('avg_chunk_quality_score', 0)}**")
        lines.append(f"")

        # 6. Claim Quality
        clq = report.get("claim_quality", {})
        lines.append(f"## 6. Claim Quality")
        lines.append(f"")
        lines.append(f"- Papers checked: **{clq.get('papers_checked', 0)}**")
        lines.append(f"- Total claims: **{clq.get('total_claims', 0)}**")
        lines.append(f"- Claims needing AI: **{clq.get('total_needs_ai', 0)}**")
        lines.append(f"- Avg needs-AI rate: **{clq.get('avg_needs_ai_pct', 0):.1f}%**")
        lines.append(f"- Avg has-evidence rate: **{clq.get('avg_has_evidence_pct', 0):.1f}%**")
        lines.append(f"")

        # 7. Top Entities
        te = report.get("top_entities", [])
        lines.append(f"## 7. Top 20 Entities (kept)")
        lines.append(f"")
        lines.append(f"| Rank | Entity | Type | Frequency |")
        lines.append(f"|---|---|---|---|")
        for i, ent in enumerate(te[:20], 1):
            lines.append(f"| {i} | `{ent['entity_name']}` | {ent['entity_type']} | {ent['total_frequency']} |")
        lines.append(f"")

        # 8. Top Methods
        tm = report.get("top_methods", [])
        lines.append(f"## 8. Top 20 Methods")
        lines.append(f"")
        lines.append(f"| Rank | Method | Papers |")
        lines.append(f"|---|---|---|")
        for i, m in enumerate(tm[:20], 1):
            lines.append(f"| {i} | `{m['method_name']}` | {m['paper_count']} |")
        lines.append(f"")

        # 9. Quality Risks
        risks = report.get("quality_risks", [])
        lines.append(f"## 9. Quality Risks")
        lines.append(f"")
        if risks:
            for r in risks:
                lines.append(f"- ⚠ {r}")
        else:
            lines.append(f"> No critical quality risks detected.")
        lines.append(f"")

        # 10. Recommendations
        recs = report.get("recommendations", [])
        lines.append(f"## 10. Recommendations & Next Steps")
        lines.append(f"")
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. {r}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"*Generated by Scientra Copilot Phase 0.5 — Quality Report Builder*")

        return "\n".join(lines)
