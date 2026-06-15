"""Research Plan Builder — generate research plans from gaps, hypotheses, and evidence."""

from __future__ import annotations
from typing import Any


class ResearchPlanBuilder:
    def build(self, query: str, tool_results: list[dict]) -> dict[str, Any] | None:
        """Build a research plan from tool results. Returns None if insufficient data."""
        gaps, hyps, evidence = self._extract(tool_results)

        if not gaps and not hyps:
            return None

        current_evidence = [e.get("title", "") for e in evidence[:5]]
        key_gaps = [g.get("title", "") for g in gaps[:5]]
        testable_hypotheses = [h.get("title", "") for h in hyps[:5]]

        suggested_experiments = []
        if any("expression" in g.lower() for g in key_gaps):
            suggested_experiments.append("RNA-seq or qPCR expression profiling")
        if any("mechanism" in g.lower() for g in key_gaps):
            suggested_experiments.append("Knockdown/knockout + functional assay")
        if any("receptor" in g.lower() or "binding" in g.lower() for g in key_gaps):
            suggested_experiments.append("Binding assay (SPR/ITC/pull-down)")
        if any("toxicity" in g.lower() or "lc50" in g.lower() for g in key_gaps):
            suggested_experiments.append("Dose-response bioassay with LC50 determination")
        if not suggested_experiments:
            suggested_experiments.append("Validation experiment targeting identified gap")

        return {
            "research_question": query,
            "current_evidence": current_evidence,
            "key_gaps": key_gaps,
            "testable_hypotheses": testable_hypotheses,
            "suggested_experiments": suggested_experiments,
            "required_data": ["Expression data", "Functional assay results", "Statistical analysis"],
            "expected_readouts": ["Differential expression", "Phenotypic change", "Mechanistic insight"],
            "risks": ["Insufficient sample size", "Technical variability", "Off-target effects"],
            "evidence_sources": [e.get("source_relative_path", "") for e in evidence[:5]],
        }

    @staticmethod
    def _extract(tool_results: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
        gaps, hyps, evidence = [], [], []
        for tr in tool_results:
            data = tr.get("data", [])
            items = data if isinstance(data, list) else []
            for h in items:
                at = h.get("asset_type", "")
                if at == "gap":
                    gaps.append(h)
                elif at == "hypothesis":
                    hyps.append(h)
                elif at == "evidence":
                    evidence.append(h)
        return gaps, hyps, evidence
