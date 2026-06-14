"""Figure Intelligence Runner — orchestrator for the full Figure Intelligence pipeline.

Stages:
  1. Build figure contexts (FigureContextBuilder)
  2. Interpret figures (FigureInterpreter) — LLM or rule fallback
  3. Check quality (FigureQualityChecker)
  4. Build cards (FigureCardBuilder)
  5. Write output files

Output directory: {paper_dir}/figure_intelligence/
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.assets.asset_registry import get_paper_dir
from scientra.assets.figure_intelligence.figure_context_builder import FigureContextBuilder
from scientra.assets.figure_intelligence.figure_interpreter import FigureInterpreter
from scientra.assets.figure_intelligence.figure_quality_checker import FigureQualityChecker
from scientra.assets.figure_intelligence.figure_card_builder import FigureCardBuilder


class FigureIntelligenceRunner:
    """Orchestrate the Figure Intelligence pipeline."""

    def __init__(self, mode: str = "auto", root: str | Path | None = None) -> None:
        if root is None:
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()
        self.mode = mode

    def run(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        """Run full Figure Intelligence pipeline for a paper.

        Args:
            paper_id: The paper ID.
            force: If True, overwrite existing outputs.

        Returns:
            Summary dict.
        """
        output_dir = self._get_output_dir(paper_id)

        # Check if already built
        if not force and self._output_exists(output_dir):
            return self._load_existing_summary(paper_id, output_dir)

        # Stage 1: Build contexts
        ctx_builder = FigureContextBuilder(self.root)
        contexts = ctx_builder.build_all(paper_id)

        if not contexts:
            return {
                "paper_id": paper_id,
                "success": False,
                "error": "No figure assets found. Run asset linking first: python Scripts/build_asset_links.py",
                "figure_count": 0,
                "mode_used": self.mode,
                "mode_effective": "rule",
                "quality_summary": {},
            }

        # Stage 2: Interpret figures
        interpreter = FigureInterpreter(mode=self.mode, root=self.root)
        interpretations = interpreter.interpret_all(contexts)
        effective_mode = interpretations[0].get("mode", "rule") if interpretations else "rule"

        # Stage 3: Quality check
        checker = FigureQualityChecker()
        quality_reports = checker.check_all(contexts, interpretations)

        # Stage 4: Build cards
        card_builder = FigureCardBuilder()
        cards = card_builder.build_all(contexts, interpretations, quality_reports)

        # Stage 5: Write outputs
        output_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(output_dir / "figure_contexts.json", contexts)
        self._write_json(output_dir / "figure_interpretations.json", interpretations)
        self._write_json(output_dir / "figure_cards.json", cards)
        self._write_json(output_dir / "figure_quality_report.json", quality_reports)

        # Build summary
        summary = self._build_summary(paper_id, contexts, interpretations, quality_reports, effective_mode)
        self._write_summary_md(output_dir / "figure_intelligence_summary.md", summary, cards, quality_reports)

        return summary

    def get_figures(self, paper_id: str) -> dict[str, Any]:
        """Get figure cards for a paper (read-only)."""
        output_dir = self._get_output_dir(paper_id)
        fpath = output_dir / "figure_cards.json"

        if not fpath.exists():
            return {
                "paper_id": paper_id,
                "available": False,
                "message": "Figure intelligence not yet built. Run: python Scripts/build_figure_intelligence.py --paper-id " + paper_id,
                "figures": [],
                "summary": {},
            }

        try:
            cards = json.loads(fpath.read_text(encoding="utf-8"))
            # Load other data files
            summary_data = {}
            sum_path = output_dir / "figure_intelligence_summary.md"
            if sum_path.exists():
                summary_data = {"summary_md_path": str(sum_path)}

            return {
                "paper_id": paper_id,
                "available": True,
                "figures": cards,
                "summary": {
                    "figure_count": len(cards),
                    "mode": cards[0].get("mode", "unknown") if cards else "unknown",
                    **summary_data,
                },
            }
        except Exception:
            return {
                "paper_id": paper_id,
                "available": False,
                "message": "Error loading figure intelligence data.",
                "figures": [],
                "summary": {},
            }

    def get_figure_card(self, paper_id: str, figure_id: str) -> dict[str, Any]:
        """Get a single figure card."""
        data = self.get_figures(paper_id)
        if not data.get("available"):
            return {"available": False, "figure": None}

        for card in data.get("figures", []):
            if card.get("figure_id") == figure_id:
                return {"available": True, "figure": card}

        return {"available": False, "figure": None, "message": f"Figure not found: {figure_id}"}

    def get_summary(self, paper_id: str) -> dict[str, Any]:
        """Get figure intelligence summary for a paper."""
        output_dir = self._get_output_dir(paper_id)
        cards_path = output_dir / "figure_cards.json"

        if not cards_path.exists():
            return {
                "paper_id": paper_id,
                "available": False,
                "figure_count": 0,
                "evidence_types": {},
                "quality_distribution": {},
                "overclaim_summary": {},
                "mode": "unknown",
            }

        try:
            cards = json.loads(cards_path.read_text(encoding="utf-8"))
        except Exception:
            return {"paper_id": paper_id, "available": False, "figure_count": 0}

        # Aggregate statistics
        evidence_types: dict[str, int] = {}
        quality_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        overclaim_summary: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        modes: dict[str, int] = {}

        for card in cards:
            et = card.get("evidence_type", "unknown")
            evidence_types[et] = evidence_types.get(et, 0) + 1

            qs = card.get("quality_score", 0)
            if qs >= 0.7:
                quality_dist["high"] += 1
            elif qs >= 0.4:
                quality_dist["medium"] += 1
            else:
                quality_dist["low"] += 1

            oc = card.get("overclaim_risk", "low")
            overclaim_summary[oc] = overclaim_summary.get(oc, 0) + 1

            mode = card.get("mode", "unknown")
            modes[mode] = modes.get(mode, 0) + 1

        return {
            "paper_id": paper_id,
            "available": True,
            "figure_count": len(cards),
            "evidence_types": evidence_types,
            "quality_distribution": quality_dist,
            "overclaim_summary": overclaim_summary,
            "mode": max(modes, key=modes.get) if modes else "unknown",
            "modes": modes,
        }

    # ── Helpers ──

    def _get_output_dir(self, paper_id: str) -> Path:
        """Get output directory for figure intelligence."""
        paper_dir = get_paper_dir(paper_id)
        return paper_dir / "figure_intelligence"

    @staticmethod
    def _output_exists(output_dir: Path) -> bool:
        """Check if all output files exist."""
        required = ["figure_contexts.json", "figure_interpretations.json", "figure_cards.json"]
        return all((output_dir / f).exists() for f in required)

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_existing_summary(self, paper_id: str, output_dir: Path) -> dict[str, Any]:
        """Load summary from existing outputs."""
        summary = self.get_summary(paper_id)
        return {
            "paper_id": paper_id,
            "success": True,
            "figure_count": summary.get("figure_count", 0),
            "mode_used": self.mode,
            "mode_effective": summary.get("mode", "unknown"),
            "quality_summary": summary.get("quality_distribution", {}),
            "overclaim_summary": summary.get("overclaim_summary", {}),
            "evidence_types": summary.get("evidence_types", {}),
        }

    @staticmethod
    def _build_summary(
        paper_id: str,
        contexts: list[dict[str, Any]],
        interpretations: list[dict[str, Any]],
        quality_reports: list[dict[str, Any]],
        effective_mode: str,
    ) -> dict[str, Any]:
        """Build pipeline summary."""
        evidence_types: dict[str, int] = {}
        modes: dict[str, int] = {}
        quality_dist = {"high": 0, "medium": 0, "low": 0}
        overclaim = {"low": 0, "medium": 0, "high": 0}

        for interp in interpretations:
            et = interp.get("evidence_type", "unknown")
            evidence_types[et] = evidence_types.get(et, 0) + 1
            mode = interp.get("mode", "rule")
            modes[mode] = modes.get(mode, 0) + 1

        for qr in quality_reports:
            qs = qr.get("quality_score", 0)
            if qs >= 0.7:
                quality_dist["high"] += 1
            elif qs >= 0.4:
                quality_dist["medium"] += 1
            else:
                quality_dist["low"] += 1
            oc = qr.get("overclaim_risk", "low")
            overclaim[oc] = overclaim.get(oc, 0) + 1

        return {
            "paper_id": paper_id,
            "success": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "figure_count": len(contexts),
            "mode_used": effective_mode,
            "evidence_types": evidence_types,
            "quality_distribution": quality_dist,
            "overclaim_summary": overclaim,
            "modes": modes,
        }

    @staticmethod
    def _write_summary_md(
        path: Path,
        summary: dict[str, Any],
        cards: list[dict[str, Any]],
        quality_reports: list[dict[str, Any]],
    ) -> None:
        """Write human-readable summary markdown."""
        lines = [
            f"# Figure Intelligence Summary — {summary['paper_id']}",
            "",
            f"Generated: {summary.get('generated_at', 'N/A')}",
            f"Mode: {summary.get('mode_used', 'unknown')}",
            "",
            "## Statistics",
            "",
            f"- **Total figures:** {summary.get('figure_count', 0)}",
            "",
            "### Evidence Types",
            "",
        ]
        for et, count in sorted(summary.get("evidence_types", {}).items()):
            lines.append(f"- {et}: {count}")

        lines.extend([
            "",
            "### Quality Distribution",
            "",
        ])
        for level, count in summary.get("quality_distribution", {}).items():
            lines.append(f"- {level}: {count}")

        lines.extend([
            "",
            "### Overclaim Risk",
            "",
        ])
        for level, count in summary.get("overclaim_summary", {}).items():
            lines.append(f"- {level}: {count}")

        lines.extend([
            "",
            "## Figures",
            "",
            "| Label | Evidence Type | Quality | Overclaim | Mode |",
            "|-------|---------------|---------|-----------|------|",
        ])

        for card in cards:
            label = card.get("label", "?")
            ev_type = card.get("evidence_type", "?")
            qs = card.get("quality_score", 0)
            quality_label = "⬤ High" if qs >= 0.7 else ("⬤ Med" if qs >= 0.4 else "⬤ Low")
            oc = card.get("overclaim_risk", "?")
            mode = card.get("mode", "?")
            lines.append(f"| {label} | {ev_type} | {quality_label} | {oc} | {mode} |")

        if cards:
            lines.append("")

        # Warnings section
        all_warnings: list[str] = []
        for card in cards:
            for w in card.get("warnings", []):
                if w not in all_warnings:
                    all_warnings.append(w)

        if all_warnings:
            lines.append("## Warnings")
            lines.append("")
            for w in all_warnings[:15]:
                lines.append(f"- ⚠️ {w}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
