"""Table Intelligence Runner — orchestrator for the full Table Intelligence pipeline.

Stages:
  1. Build table contexts
  2. Parse table structures
  3. Infer table schemas
  4. Detect statistical fields
  5. Interpret tables (LLM or rule fallback)
  6. Check quality
  7. Build Table Cards
  8. Write output files
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.assets.asset_registry import get_paper_dir
from scientra.assets.table_intelligence.table_context_builder import TableContextBuilder
from scientra.assets.table_intelligence.table_structure_parser import parse_table_structure
from scientra.assets.table_intelligence.table_schema_inferer import infer_table_schema
from scientra.assets.table_intelligence.table_stat_detector import detect_statistical_fields
from scientra.assets.table_intelligence.table_interpreter import TableInterpreter
from scientra.assets.table_intelligence.table_quality_checker import TableQualityChecker
from scientra.assets.table_intelligence.table_card_builder import TableCardBuilder


class TableIntelligenceRunner:
    """Orchestrate the Table Intelligence pipeline."""

    def __init__(self, mode: str = "auto", max_sample_rows: int = 20, root: str | Path | None = None) -> None:
        if root is None:
            candidate = Path(__file__).resolve().parent.parent.parent.parent
            self.root = candidate
        else:
            self.root = Path(root).resolve()
        self.mode = mode
        self.max_sample_rows = max_sample_rows

    def run(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        output_dir = self._get_output_dir(paper_id)

        if not force and self._output_exists(output_dir):
            return self._load_existing_summary(paper_id, output_dir)

        # Stage 1: Context
        ctx_builder = TableContextBuilder(self.root)
        contexts = ctx_builder.build_all(paper_id)
        if not contexts:
            return {
                "paper_id": paper_id, "success": False,
                "error": "No table assets found. Run asset linking first.",
                "table_count": 0, "mode_used": self.mode, "mode_effective": "rule",
                "quality_summary": {},
            }

        # Stage 2: Parse structures
        structures = []
        for ctx in contexts:
            path = ctx.get("asset_path", "")
            struct = parse_table_structure(path, self.max_sample_rows)
            struct["table_id"] = ctx["table_id"]
            struct["asset_id"] = ctx["asset_id"]
            structures.append(struct)

        # Stage 3: Infer schemas
        schemas = []
        for ctx, struct in zip(contexts, structures):
            headers = struct["sheets"][0]["headers"] if struct.get("sheets") else []
            sample_rows = struct["sheets"][0]["sample_rows"] if struct.get("sheets") else []
            schema = infer_table_schema(headers, ctx.get("caption", ""), sample_rows, ctx.get("body_mentions", []))
            schema["table_id"] = ctx["table_id"]
            schemas.append(schema)

        # Stage 4: Detect statistics
        statistics = []
        for ctx, struct in zip(contexts, structures):
            headers = struct["sheets"][0]["headers"] if struct.get("sheets") else []
            sample_rows = struct["sheets"][0]["sample_rows"] if struct.get("sheets") else []
            stat = detect_statistical_fields(headers, sample_rows)
            stat["table_id"] = ctx["table_id"]
            statistics.append(stat)

        # Stage 5: Interpret
        interpreter = TableInterpreter(mode=self.mode, root=self.root)
        interpretations = interpreter.interpret_all(contexts, structures, schemas, statistics)
        effective_mode = interpretations[0].get("mode", "rule") if interpretations else "rule"

        # Stage 6: Quality
        checker = TableQualityChecker()
        quality_reports = checker.check_all(contexts, structures, interpretations)

        # Stage 7: Build cards
        card_builder = TableCardBuilder()
        cards = card_builder.build_all(contexts, structures, interpretations, quality_reports)

        # Stage 8: Write
        output_dir.mkdir(parents=True, exist_ok=True)
        self._wj(output_dir / "table_contexts.json", contexts)
        self._wj(output_dir / "table_structures.json", structures)
        self._wj(output_dir / "table_schemas.json", schemas)
        self._wj(output_dir / "table_statistics.json", statistics)
        self._wj(output_dir / "table_interpretations.json", interpretations)
        self._wj(output_dir / "table_cards.json", cards)
        self._wj(output_dir / "table_quality_report.json", quality_reports)

        summary = self._build_summary(paper_id, contexts, interpretations, quality_reports, effective_mode)
        self._write_summary_md(output_dir / "table_intelligence_summary.md", summary, cards)

        return summary

    def get_tables(self, paper_id: str) -> dict[str, Any]:
        output_dir = self._get_output_dir(paper_id)
        fpath = output_dir / "table_cards.json"
        if not fpath.exists():
            return {"paper_id": paper_id, "available": False, "message": "Table intelligence not yet built.", "tables": [], "summary": {}}
        try:
            cards = json.loads(fpath.read_text(encoding="utf-8"))
            return {"paper_id": paper_id, "available": True, "tables": cards, "summary": {"table_count": len(cards)}}
        except Exception:
            return {"paper_id": paper_id, "available": False, "message": "Error loading.", "tables": [], "summary": {}}

    def get_table_card(self, paper_id: str, table_id: str) -> dict[str, Any]:
        data = self.get_tables(paper_id)
        if not data.get("available"):
            return {"available": False, "table": None}
        for card in data.get("tables", []):
            if card.get("table_id") == table_id:
                return {"available": True, "table": card}
        return {"available": False, "table": None, "message": f"Table not found: {table_id}"}

    def get_summary(self, paper_id: str) -> dict[str, Any]:
        output_dir = self._get_output_dir(paper_id)
        fpath = output_dir / "table_cards.json"
        if not fpath.exists():
            return {"paper_id": paper_id, "available": False, "table_count": 0}
        try:
            cards = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            return {"paper_id": paper_id, "available": False, "table_count": 0}

        types: dict[str, int] = {}
        quality = {"high": 0, "medium": 0, "low": 0}
        overclaim = {"low": 0, "medium": 0, "high": 0}
        for c in cards:
            types[c.get("table_type", "unknown")] = types.get(c.get("table_type", "unknown"), 0) + 1
            qs = c.get("quality_score", 0)
            if qs >= 0.7:
                quality["high"] += 1
            elif qs >= 0.4:
                quality["medium"] += 1
            else:
                quality["low"] += 1
            overclaim[c.get("overclaim_risk", "low")] = overclaim.get(c.get("overclaim_risk", "low"), 0) + 1

        return {
            "paper_id": paper_id, "available": True, "table_count": len(cards),
            "table_types": types, "quality_distribution": quality,
            "overclaim_summary": overclaim,
        }

    def _get_output_dir(self, paper_id: str) -> Path:
        return get_paper_dir(paper_id) / "table_intelligence"

    @staticmethod
    def _output_exists(d: Path) -> bool:
        return all((d / f).exists() for f in ["table_contexts.json", "table_cards.json"])

    @staticmethod
    def _wj(p: Path, d: Any) -> None:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_existing_summary(self, paper_id, d):
        s = self.get_summary(paper_id)
        return {"paper_id": paper_id, "success": True, "table_count": s.get("table_count", 0),
                "mode_used": self.mode, "mode_effective": "cached", "quality_summary": s.get("quality_distribution", {})}

    @staticmethod
    def _build_summary(paper_id, contexts, interpretations, quality_reports, effective_mode):
        types: dict[str, int] = {}
        qd = {"high": 0, "medium": 0, "low": 0}
        oc = {"low": 0, "medium": 0, "high": 0}
        for i in interpretations:
            types[i.get("table_type", "unknown")] = types.get(i.get("table_type", "unknown"), 0) + 1
        for q in quality_reports:
            qs = q.get("quality_score", 0)
            if qs >= 0.7:
                qd["high"] += 1
            elif qs >= 0.4:
                qd["medium"] += 1
            else:
                qd["low"] += 1
            oc[q.get("overclaim_risk", "low")] = oc.get(q.get("overclaim_risk", "low"), 0) + 1
        return {
            "paper_id": paper_id, "success": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "table_count": len(contexts), "mode_used": effective_mode,
            "table_types": types, "quality_distribution": qd, "overclaim_summary": oc,
        }

    @staticmethod
    def _write_summary_md(path, summary, cards):
        lines = [
            f"# Table Intelligence Summary — {summary['paper_id']}",
            f"Generated: {summary.get('generated_at', 'N/A')}",
            f"Mode: {summary.get('mode_used', 'unknown')}",
            f"**Total tables:** {summary.get('table_count', 0)}",
            "",
            "## Table Types",
        ]
        for t, c in sorted(summary.get("table_types", {}).items()):
            lines.append(f"- {t}: {c}")
        lines.extend(["", "## Quality", ""])
        for l, c in summary.get("quality_distribution", {}).items():
            lines.append(f"- {l}: {c}")
        lines.extend(["", "## Tables", "", "| Label | Type | Rows | Cols | Quality | Overclaim | Mode |", "|-------|------|------|------|---------|-----------|------|"])
        for c in cards:
            lines.append(f"| {c.get('label', '?')} | {c.get('table_type', '?')} | {c.get('n_rows', 0)} | {c.get('n_columns', 0)} | {c.get('quality_score', 0):.2f} | {c.get('overclaim_risk', '?')} | {c.get('mode', '?')} |")
        path.write_text("\n".join(lines), encoding="utf-8")
