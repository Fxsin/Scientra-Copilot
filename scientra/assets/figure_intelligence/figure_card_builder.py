"""Figure Card Builder — merge context, interpretation, evidence classification, and quality check into a unified Figure Card."""

from __future__ import annotations

from typing import Any


class FigureCardBuilder:
    """Build unified Figure Cards from all pipeline outputs."""

    def build(
        self,
        context: dict[str, Any],
        interpretation: dict[str, Any],
        quality_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a single Figure Card.

        Args:
            context: Figure context from FigureContextBuilder.
            interpretation: Interpretation from FigureInterpreter.
            quality_report: Quality report from FigureQualityChecker.

        Returns:
            Figure Card dict.
        """
        figure_id = context.get("figure_id", "")

        # Collect linked evidence IDs
        linked_evidence_ids: list[str] = []
        for ev in context.get("linked_evidence", []):
            ev_id = ev.get("evidence_id", "")
            if ev_id:
                linked_evidence_ids.append(ev_id)

        # Collect all warnings
        all_warnings: list[str] = []
        all_warnings.extend(context.get("warnings", []))
        all_warnings.extend(quality_report.get("warnings", []))
        # Deduplicate
        all_warnings = list(dict.fromkeys(all_warnings))

        # Determine title
        title = self._determine_title(context, interpretation)

        # Build card
        card = {
            "figure_id": figure_id,
            "paper_id": context.get("paper_id", ""),
            "label": context.get("normalized_label", ""),
            "title": title,
            "asset_path": context.get("asset_path", ""),
            "thumbnail_path": "",  # Reserved for future thumbnail generation
            "caption": context.get("caption", ""),
            "figure_summary": interpretation.get("figure_summary", ""),
            "key_finding": interpretation.get("key_finding", ""),
            "evidence_type": interpretation.get("evidence_type", "unknown"),
            "evidence_type_confidence": interpretation.get("evidence_type_confidence", 0),
            "evidence_strength": interpretation.get("evidence_strength", "unclear"),
            "related_claims": interpretation.get("supported_claims", []),
            "related_methods": interpretation.get("related_methods", []),
            "linked_evidence_ids": linked_evidence_ids,
            "limitations": interpretation.get("limitations", []),
            "warnings": all_warnings,
            "quality_score": quality_report.get("quality_score", 0),
            "overclaim_risk": quality_report.get("overclaim_risk", "low"),
            "confidence": interpretation.get("interpretation_confidence", 0),
            "mode": interpretation.get("mode", "rule"),
            "grounding_sources": interpretation.get("grounding_sources", []),
            "context_completeness": context.get("context_completeness", {}),
        }

        return card

    def build_all(
        self,
        contexts: list[dict[str, Any]],
        interpretations: list[dict[str, Any]],
        quality_reports: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build Figure Cards for all figures."""
        int_by_id = {i.get("figure_id", ""): i for i in interpretations}
        qr_by_id = {q.get("figure_id", ""): q for q in quality_reports}

        cards = []
        for ctx in contexts:
            fig_id = ctx.get("figure_id", "")
            interp = int_by_id.get(fig_id, {})
            quality = qr_by_id.get(fig_id, {})
            cards.append(self.build(ctx, interp, quality))

        return cards

    @staticmethod
    def _determine_title(context: dict[str, Any], interpretation: dict[str, Any]) -> str:
        """Determine the best title for this figure card."""
        caption = context.get("caption", "")
        label = context.get("normalized_label", "")
        ev_type = interpretation.get("evidence_type", "unknown")

        # Try to extract a descriptive title from caption
        if caption:
            # Take first sentence, remove figure label prefix
            first = caption.replace("\n", " ").split(". ")[0].strip()
            # Remove common prefixes like "Figure 1." or "Fig. 1."
            import re
            first = re.sub(r"^(?:Figure|Fig\.?)\s+S?\d+[A-Za-z]?\.?\s*", "", first, flags=re.IGNORECASE).strip()
            if len(first) > 10:
                return first[:150]

        # Fallback: use label + evidence type
        ev_labels = {
            "microscopy": "Microscopy Image",
            "western_blot": "Western Blot",
            "gel_image": "Gel Electrophoresis",
            "survival_curve": "Survival Curve",
            "bioassay": "Bioassay Results",
            "binding_assay": "Binding Assay",
            "expression_analysis": "Expression Analysis",
            "heatmap": "Heatmap",
            "volcano_plot": "Volcano Plot",
            "phylogeny": "Phylogenetic Analysis",
            "structure_model": "Structure Model",
            "statistical_plot": "Statistical Analysis",
            "workflow_diagram": "Workflow Diagram",
        }
        type_label = ev_labels.get(ev_type, "Figure")
        return f"{label}: {type_label}"
