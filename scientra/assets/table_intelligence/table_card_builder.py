"""Table Card Builder — merge context, structure, schema, statistics, interpretation, and quality check into a unified Table Card."""

from __future__ import annotations

import re
from typing import Any


class TableCardBuilder:
    """Build unified Table Cards from all pipeline outputs."""

    def build(
        self,
        context: dict[str, Any],
        structure: dict[str, Any] | None,
        interpretation: dict[str, Any],
        quality_report: dict[str, Any],
    ) -> dict[str, Any]:
        table_id = context.get("table_id", "")
        linked_evidence_ids = [e.get("evidence_id", "") for e in context.get("linked_evidence", []) if e.get("evidence_id")]

        all_warnings = list(dict.fromkeys(
            list(context.get("warnings", [])) + list(quality_report.get("warnings", []))
        ))

        n_rows = 0
        n_columns = 0
        if structure:
            for sheet in structure.get("sheets", []):
                n_rows += sheet.get("n_rows", 0)
                if sheet.get("n_columns", 0) > n_columns:
                    n_columns = sheet.get("n_columns", 0)

        title = self._make_title(context, interpretation)

        return {
            "table_id": table_id,
            "paper_id": context.get("paper_id", ""),
            "label": context.get("normalized_label", ""),
            "title": title,
            "asset_path": context.get("asset_path", ""),
            "caption": context.get("caption", ""),
            "table_type": interpretation.get("table_type", "unknown"),
            "n_rows": n_rows,
            "n_columns": n_columns,
            "important_columns": interpretation.get("important_columns", []),
            "table_summary": interpretation.get("table_summary", ""),
            "key_finding": interpretation.get("key_finding", ""),
            "evidence_strength": interpretation.get("evidence_strength", "unclear"),
            "linked_evidence_ids": linked_evidence_ids,
            "related_claims": interpretation.get("related_claims", []),
            "detected_entities": interpretation.get("detected_entities", []),
            "statistical_fields": interpretation.get("statistical_fields_summary", []),
            "warnings": all_warnings,
            "quality_score": quality_report.get("quality_score", 0),
            "overclaim_risk": quality_report.get("overclaim_risk", "low"),
            "confidence": interpretation.get("interpretation_confidence", 0),
            "mode": interpretation.get("mode", "rule"),
        }

    def build_all(self, contexts, structures, interpretations, quality_reports):
        sid = {s.get("table_id", s.get("asset_id", "")): s for s in (structures or [])}
        iid = {i.get("table_id", ""): i for i in (interpretations or [])}
        qid = {q.get("table_id", ""): q for q in (quality_reports or [])}
        return [self.build(c, sid.get(c.get("table_id", "")), iid.get(c.get("table_id", ""), {}), qid.get(c.get("table_id", ""), {})) for c in contexts]

    @staticmethod
    def _make_title(ctx, interp):
        caption = ctx.get("caption", "")
        label = ctx.get("normalized_label", "")
        if caption:
            first = caption.replace("\n", " ").split(". ")[0].strip()
            first = re.sub(r"^(?:Table|Tab\.?)\s+S?\d+[A-Za-z]?\.?\s*", "", first, flags=re.IGNORECASE).strip()
            if len(first) > 10:
                return first[:150]
        ttype = interp.get("table_type", "unknown")
        return f"{label}: {ttype.replace('_', ' ').title()}"
