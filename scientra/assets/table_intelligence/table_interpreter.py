"""Table Interpreter — generate table interpretation from context + structure + schema + statistics.

Dual-mode: LLM (with API key) or rule fallback (no API key needed).
All interpretations require grounding_sources.
"""

from __future__ import annotations

import json
from typing import Any


class TableInterpreter:
    """Generate interpretations for table contexts."""

    def __init__(self, mode: str = "auto", root: str | Any = None) -> None:
        self.mode = mode
        if root is None:
            from pathlib import Path
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = root

    def interpret(
        self,
        context: dict[str, Any],
        structure: dict[str, Any] | None = None,
        schema: dict[str, Any] | None = None,
        statistics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate interpretation for a single table."""
        table_id = context.get("table_id", "")
        effective_mode = self._resolve_mode()

        if effective_mode == "llm":
            result = self._interpret_llm(context, structure, schema, statistics)
        else:
            result = self._interpret_rule(context, structure, schema, statistics)

        result["table_id"] = table_id
        return result

    def interpret_all(
        self,
        contexts: list[dict[str, Any]],
        structures: list[dict[str, Any]] | None = None,
        schemas: list[dict[str, Any]] | None = None,
        statistics: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        struct_by_id = {s.get("table_id", s.get("asset_id", "")): s for s in (structures or [])}
        schema_by_id = {s.get("table_id", ""): s for s in (schemas or [])}
        stat_by_id = {s.get("table_id", ""): s for s in (statistics or [])}

        results = []
        for ctx in contexts:
            tid = ctx.get("table_id", "")
            results.append(self.interpret(
                ctx,
                struct_by_id.get(tid) or struct_by_id.get(ctx.get("asset_id", "")),
                schema_by_id.get(tid),
                stat_by_id.get(tid),
            ))
        return results

    def _resolve_mode(self) -> str:
        if self.mode == "rule":
            return "rule"
        if self.mode == "llm" and self._is_llm_available():
            return "llm"
        if self.mode == "auto" and self._is_llm_available():
            try:
                from scientra.ai import get_config
                config = get_config()
                if config and config.is_task_enabled("table_interpretation"):
                    return "llm"
            except Exception:
                pass
        return "rule"

    def _is_llm_available(self) -> bool:
        try:
            from scientra.ai import get_config
            config = get_config()
            return config is not None and config.enabled and bool(config.api_key)
        except Exception:
            return False

    def _interpret_llm(self, context, structure, schema, statistics) -> dict[str, Any]:
        try:
            from scientra.ai import call_llm
            prompt = self._build_llm_prompt(context, structure, schema, statistics)
            response = call_llm(
                prompt=prompt, task_name="table_interpretation",
                temperature=0.2, max_tokens=2048,
                system_prompt="You are a scientific table analyst. Return ONLY valid JSON.",
            )
            if response.success and response.text:
                try:
                    result = json.loads(response.text.strip())
                    result["mode"] = "llm"
                    result.setdefault("grounding_sources", [])
                    result.setdefault("limitations", [])
                    result.setdefault("interpretation_confidence", 0.7)
                    return result
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        result = self._interpret_rule(context, structure, schema, statistics)
        result["mode"] = "rule_fallback"
        return result

    def _interpret_rule(self, context, structure, schema, statistics) -> dict[str, Any]:
        caption = context.get("caption", "")
        completeness = context.get("context_completeness", {})
        label = context.get("normalized_label", "")
        related_claims = context.get("related_claims", [])
        related_methods = context.get("related_methods", [])
        linked_evidence = context.get("linked_evidence", [])
        is_large = False

        # Build summary from caption + structure info
        parts = []
        if structure:
            for sheet in structure.get("sheets", []):
                nr = sheet.get("n_rows", 0)
                nc = sheet.get("n_columns", 0)
                if nr > 0:
                    parts.append(f"{nr} rows × {nc} columns")
                    if nr > 100:
                        is_large = True
        table_summary = f"{label}: " + (caption[:200] if caption else "Table data.")
        if parts:
            table_summary += f" ({'; '.join(parts)})"

        # Schema info
        table_type = schema.get("table_type", "unknown") if schema else "unknown"
        schema_conf = schema.get("confidence", 0) if schema else 0

        # Key finding from evidence or caption
        key_finding = ""
        for ev in linked_evidence[:3]:
            f = ev.get("finding", ev.get("claim", ev.get("text", "")))
            if f and len(f) > 20:
                key_finding = str(f)[:300]
                break
        if not key_finding and caption:
            sentences = caption.replace("\n", " ").split(". ")
            key_finding = sentences[0].strip()[:300]

        # Evidence strength
        evidence_strength = self._assess_strength(completeness, linked_evidence)

        # Important columns
        important_columns: list[str] = []
        if schema and schema.get("key_columns"):
            for k, cols in schema["key_columns"].items():
                important_columns.extend(cols)
        if structure:
            for sheet in structure.get("sheets", []):
                headers = sheet.get("headers", [])
                if headers and not important_columns:
                    important_columns = headers[:10]

        # Statistical fields
        stat_fields: list[str] = []
        if statistics:
            for sf in statistics.get("statistical_fields", []):
                stat_fields.append(sf.get("field", ""))

        # Grounding sources
        grounding_sources: list[str] = []
        if completeness.get("has_caption"):
            grounding_sources.append("caption")
        if completeness.get("has_body_mention"):
            grounding_sources.append("body_citation")
        if structure and structure.get("parse_status") == "parsed":
            grounding_sources.append("table_headers")
            grounding_sources.append("sample_rows")
        if completeness.get("has_linked_evidence"):
            grounding_sources.append("evidence_chunk")

        # Limitations
        limitations: list[str] = []
        if not completeness.get("has_caption"):
            limitations.append("No caption available.")
        if not completeness.get("has_readable_table"):
            limitations.append("Table file not readable — structure could not be parsed.")
        if is_large:
            limitations.append(f"Large table ({structure['sheets'][0]['n_rows']} rows) — interpretation based on sample rows only.")
        if schema_conf < 0.5:
            limitations.append(f"Low table type confidence ({schema_conf:.2f}).")

        # Confidence
        conf = 0.3
        if completeness["has_caption"]:
            conf += 0.10
        if completeness["has_body_mention"]:
            conf += 0.15
        if completeness["has_linked_evidence"]:
            conf += 0.20
        if completeness["has_readable_table"]:
            conf += 0.20
        conf = min(conf, 0.85)

        return {
            "table_summary": table_summary,
            "key_finding": key_finding,
            "table_type": table_type,
            "evidence_strength": evidence_strength,
            "important_columns": important_columns[:15],
            "important_rows": [],
            "detected_entities": [],
            "related_claims": related_claims[:5],
            "statistical_fields_summary": stat_fields[:10],
            "limitations": limitations,
            "grounding_sources": grounding_sources,
            "interpretation_confidence": round(conf, 2),
            "is_large_table": is_large,
            "mode": "rule",
        }

    @staticmethod
    def _build_llm_prompt(context, structure, schema, statistics) -> str:
        caption = context.get("caption", "")
        label = context.get("normalized_label", "")
        headers_str = ""
        if structure:
            for sh in structure.get("sheets", []):
                h = sh.get("headers", [])
                headers_str += f"Headers ({sh.get('sheet_name')}): {', '.join(h[:20])}\n"
        body = " ".join([m.get("sentence", "") for m in context.get("body_mentions", [])[:3]])
        ev = " ".join([e.get("text", e.get("claim", "")) for e in context.get("linked_evidence", [])[:3]])

        return f"""Analyze this scientific table.

Table: {label}
Caption: {caption}
{headers_str}
Body mentions: {body if body else 'None'}
Evidence: {ev if ev else 'None'}

Return ONLY valid JSON:
{{"table_summary": "...", "key_finding": "...", "table_type": "...", "evidence_strength": "strong|moderate|weak|unclear", "important_columns": [...], "limitations": [...], "grounding_sources": [...], "interpretation_confidence": 0.0}}
CRITICAL: Only use provided context. No invented data."""

    @staticmethod
    def _assess_strength(completeness, linked_evidence):
        score = sum([completeness.get("has_caption", False),
                     completeness.get("has_body_mention", False),
                     completeness.get("has_linked_evidence", False) * 2,
                     completeness.get("has_readable_table", False)])
        if score >= 4:
            return "strong"
        elif score >= 2:
            return "moderate"
        elif score >= 1:
            return "weak"
        return "unclear"
