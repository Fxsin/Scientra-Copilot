"""Supplementary Card Builder — merge everything into a unified Supplementary Card."""

from __future__ import annotations

from typing import Any


class SupplementaryCardBuilder:
    """Build Supplementary Cards from all pipeline outputs."""

    def build(
        self,
        context: dict[str, Any],
        parse_result: dict[str, Any],
        sections: list[dict[str, Any]] | None,
        evidence_list: list[dict[str, Any]] | None,
        interpretation: dict[str, Any],
        quality_report: dict[str, Any],
    ) -> dict[str, Any]:
        supp_id = context.get("supplementary_id", "")
        sections = sections or []
        evidence_list = evidence_list or []

        linked_figure_ids = context.get("related_figures", [])
        linked_table_ids = context.get("related_tables", [])
        linked_evidence_ids = [e.get("evidence_id", "") for e in evidence_list if e.get("evidence_id")]

        all_warnings = list(dict.fromkeys(quality_report.get("warnings", [])))

        return {
            "supplementary_id": supp_id,
            "paper_id": context.get("paper_id", ""),
            "asset_id": context.get("asset_id", ""),
            "label": context.get("normalized_label", "Supplementary"),
            "title": self._make_title(context, sections),
            "asset_path": context.get("asset_path", ""),
            "source_relative_path": context.get("source_relative_path", ""),
            "file_type": parse_result.get("file_type", "unknown"),
            "parse_status": parse_result.get("parse_status", "unknown"),
            "section_count": len(sections),
            "evidence_count": len(evidence_list),
            "chunk_count": 0,
            "supplementary_summary": interpretation.get("supplementary_summary", ""),
            "key_contents": interpretation.get("key_contents", []),
            "main_evidence_types": interpretation.get("main_evidence_types", []),
            "linked_figure_ids": linked_figure_ids,
            "linked_table_ids": linked_table_ids,
            "linked_evidence_ids": linked_evidence_ids,
            "warnings": all_warnings,
            "quality_score": quality_report.get("quality_score", 0),
            "overclaim_risk": quality_report.get("overclaim_risk", "low"),
            "confidence": interpretation.get("interpretation_confidence", 0),
            "mode": interpretation.get("mode", "rule"),
        }

    def build_all(self, contexts, parse_results, sections_list, evidence_list, interpretations, quality_reports):
        im = {i.get("supplementary_id", ""): i for i in (interpretations or [])}
        qm = {q.get("supplementary_id", ""): q for q in (quality_reports or [])}
        cards = []
        for ctx in contexts:
            sid = ctx.get("supplementary_id", "")
            cards.append(self.build(ctx, parse_results.get(sid, {}), sections_list.get(sid, []), evidence_list.get(sid, []), im.get(sid, {}), qm.get(sid, {})))
        return cards

    @staticmethod
    def _make_title(ctx, sections) -> str:
        label = ctx.get("normalized_label", "Supplementary")
        if sections:
            types = list(dict.fromkeys(s.get("section_type", "").replace("_", " ").title() for s in sections[:3] if s.get("section_type")))
            if types:
                return f"{label}: {', '.join(types)}"
        return label
