"""Supplementary Interpreter — generate interpretation from context + sections + evidence.

Dual-mode: LLM (with API key) or rule fallback (no API key needed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SupplementaryInterpreter:
    """Generate interpretations for supplementary contexts."""

    def __init__(self, mode: str = "auto", root: str | Any = None) -> None:
        self.mode = mode
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = root

    def interpret(
        self,
        context: dict[str, Any],
        sections: list[dict[str, Any]] | None = None,
        evidence_list: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        supp_id = context.get("supplementary_id", "")
        effective_mode = self._resolve_mode()

        if effective_mode == "llm":
            result = self._interpret_llm(context, sections, evidence_list)
        else:
            result = self._interpret_rule(context, sections, evidence_list)

        result["supplementary_id"] = supp_id
        return result

    def interpret_all(self, contexts, sections_map=None, evidence_map=None):
        sm = sections_map or {}
        em = evidence_map or {}
        return [self.interpret(c, sm.get(c.get("supplementary_id", ""), []), em.get(c.get("supplementary_id", ""), [])) for c in contexts]

    def _resolve_mode(self) -> str:
        if self.mode == "rule":
            return "rule"
        if self.mode == "llm" and self._is_llm():
            return "llm"
        if self.mode == "auto" and self._is_llm():
            try:
                from scientra.ai import get_config
                if get_config() and get_config().is_task_enabled("supplementary_interpretation"):
                    return "llm"
            except Exception:
                pass
        return "rule"

    def _is_llm(self) -> bool:
        try:
            from scientra.ai import get_config
            c = get_config()
            return c is not None and c.enabled and bool(c.api_key)
        except Exception:
            return False

    def _interpret_llm(self, context, sections, evidence_list) -> dict[str, Any]:
        try:
            from scientra.ai import call_llm
            prompt = self._build_llm_prompt(context, sections, evidence_list)
            resp = call_llm(prompt=prompt, task_name="supplementary_interpretation", temperature=0.2, max_tokens=2048, system_prompt="You are a scientific supplementary material analyst. Return ONLY valid JSON.")
            if resp.success and resp.text:
                try:
                    r = json.loads(resp.text.strip())
                    r["mode"] = "llm"
                    r.setdefault("grounding_sources", [])
                    r.setdefault("limitations", [])
                    return r
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        r = self._interpret_rule(context, sections, evidence_list)
        r["mode"] = "rule_fallback"
        return r

    def _interpret_rule(self, context, sections, evidence_list) -> dict[str, Any]:
        sections = sections or []
        evidence_list = evidence_list or []
        completeness = context.get("context_completeness", {})

        # Key contents from section titles
        key_contents = [s.get("section_title", "") for s in sections if s.get("section_title")]

        # Main evidence types
        ev_types = list(dict.fromkeys(e.get("evidence_type", "unknown") for e in evidence_list))

        # Summary
        label = context.get("normalized_label", "Supplementary")
        n_sec = len(sections)
        n_ev = len(evidence_list)
        summary = f"{label}: {n_sec} section(s), {n_ev} evidence item(s)"
        if key_contents:
            summary += f". Contains: {', '.join(key_contents[:5])}"

        # Linked assets
        linked = []
        linked.extend(context.get("related_figures", []))
        linked.extend(context.get("related_tables", []))

        # Grounding sources
        grounding = []
        if sections:
            grounding.append("section_titles")
        if completeness.get("has_body_mention"):
            grounding.append("body_citation")
        if evidence_list:
            grounding.append("supplementary_evidence")

        # Limitations
        limitations = []
        if not sections:
            limitations.append("No sections detected.")
        if not completeness.get("has_body_mention"):
            limitations.append("No body text citation.")
        if len(evidence_list) == 0:
            limitations.append("No evidence extracted from supplementary text.")

        return {
            "supplementary_summary": summary,
            "key_contents": key_contents[:10],
            "main_evidence_types": ev_types[:10],
            "linked_assets": linked[:20],
            "related_claims": [],
            "limitations": limitations,
            "grounding_sources": grounding,
            "interpretation_confidence": min(0.3 + 0.1 * len(grounding), 0.85),
            "mode": "rule",
        }

    @staticmethod
    def _build_llm_prompt(context, sections, evidence_list) -> str:
        s_titles = [s.get("section_title", "") for s in (sections or [])[:10]]
        ev_texts = [e.get("text", "")[:300] for e in (evidence_list or [])[:5]]
        return f"""Analyze this supplementary material.

Label: {context.get('normalized_label', '')}
Sections: {', '.join(s_titles)}
Evidence samples: {' | '.join(ev_texts)}

Return ONLY valid JSON:
{{"supplementary_summary": "...", "key_contents": [...], "main_evidence_types": [...], "limitations": [...], "grounding_sources": [...]}}
CRITICAL: Only use provided context."""
