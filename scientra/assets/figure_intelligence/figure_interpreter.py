"""Figure Interpreter — generate figure interpretation from context.

Two modes:
  1. LLM mode — calls AI Gateway with a structured prompt when API key is available
  2. Rule fallback — uses caption, body mentions, and evidence to build a
     grounded interpretation without AI

All interpretations MUST have grounding_sources — no unsupported claims.
"""

from __future__ import annotations

import json
from typing import Any

from scientra.assets.figure_intelligence.figure_evidence_classifier import (
    classify_evidence_type,
)


class FigureInterpreter:
    """Generate interpretations for figure contexts."""

    def __init__(self, mode: str = "auto", root: str | Any = None) -> None:
        """Initialize interpreter.

        Args:
            mode: "auto" (try LLM, fallback to rule), "llm" (LLM only), "rule" (rule only)
            root: Project root path.
        """
        self.mode = mode
        if root is None:
            from pathlib import Path
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = root

    def interpret(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generate interpretation for a single figure context.

        Args:
            context: Figure context dict from FigureContextBuilder.

        Returns:
            Interpretation dict.
        """
        figure_id = context.get("figure_id", "")

        # Determine effective mode
        effective_mode = self._resolve_mode()

        if effective_mode == "llm":
            return self._interpret_llm(context)
        else:
            return self._interpret_rule(context)

    def interpret_all(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate interpretations for all figure contexts."""
        return [self.interpret(ctx) for ctx in contexts]

    def _resolve_mode(self) -> str:
        """Resolve effective mode based on configuration."""
        if self.mode == "rule":
            return "rule"
        if self.mode == "llm":
            # Check if API key is available
            if self._is_llm_available():
                return "llm"
            return "rule"  # Fallback

        # "auto" mode
        if self._is_llm_available():
            try:
                from scientra.ai import get_config
                config = get_config()
                if config and config.is_task_enabled("figure_interpretation"):
                    return "llm"
            except Exception:
                pass
        return "rule"

    def _is_llm_available(self) -> bool:
        """Check if LLM is configured and available."""
        try:
            from scientra.ai import get_config
            config = get_config()
            if config is None or not config.enabled:
                return False
            if not config.api_key:
                return False
            return True
        except Exception:
            return False

    def _interpret_llm(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generate interpretation using LLM."""
        figure_id = context.get("figure_id", "")

        try:
            from scientra.ai import call_llm

            prompt = self._build_llm_prompt(context)
            response = call_llm(
                prompt=prompt,
                task_name="figure_interpretation",
                temperature=0.2,
                max_tokens=2048,
                system_prompt=(
                    "You are a scientific figure analyst. Generate interpretations "
                    "ONLY from the provided context. Do not invent findings or data. "
                    "Return ONLY valid JSON, no markdown wrapping."
                ),
            )

            if response.success and response.text:
                try:
                    result = json.loads(response.text.strip())
                    result["figure_id"] = figure_id
                    result["mode"] = "llm"
                    result.setdefault("grounding_sources", [])
                    result.setdefault("limitations", [])
                    result.setdefault("supported_claims", [])
                    result.setdefault("related_methods", [])
                    result.setdefault("interpretation_confidence", 0.7)
                    return result
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

        # LLM failed — fallback to rule
        result = self._interpret_rule(context)
        result["mode"] = "rule_fallback"
        result.setdefault("warnings", []).append("LLM call failed; using rule-based fallback.")
        return result

    def _interpret_rule(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generate rule-based interpretation from context."""
        figure_id = context.get("figure_id", "")
        caption = context.get("caption", "")
        body_mentions = context.get("body_mentions", [])
        linked_evidence = context.get("linked_evidence", [])
        related_claims = context.get("related_claims", [])
        related_methods = context.get("related_methods", [])
        completeness = context.get("context_completeness", {})
        norm_label = context.get("normalized_label", "")

        # Classify evidence type
        ev_class = classify_evidence_type(
            caption=caption,
            body_mentions=body_mentions,
            asset_filename=context.get("asset_filename", ""),
        )

        # Build figure summary from caption (first 1-2 sentences)
        figure_summary = self._summarize_caption(caption)

        # Extract key finding
        key_finding = self._extract_key_finding(caption, body_mentions, linked_evidence)

        # Determine evidence strength
        evidence_strength = self._assess_strength(completeness, linked_evidence, ev_class)

        # Collect grounding sources
        grounding_sources: list[str] = []
        if completeness.get("has_caption"):
            grounding_sources.append("caption")
        if completeness.get("has_body_mention"):
            grounding_sources.append("body_citation")
        if completeness.get("has_linked_evidence"):
            grounding_sources.append("evidence_chunk")

        # Collect limitations
        limitations: list[str] = []
        if not completeness.get("has_caption"):
            limitations.append("No caption available — interpretation is speculative.")
        if not completeness.get("has_body_mention"):
            limitations.append("No body text mention — figure context is incomplete.")
        if caption and len(caption) < 50:
            limitations.append("Very short caption — limited interpretive detail.")
        if ev_class["confidence"] < 0.5:
            limitations.append(f"Low evidence type confidence ({ev_class['confidence']:.2f}).")

        # Build interpretation confidence
        conf = 0.3
        if completeness["has_caption"]:
            conf += 0.15
        if completeness["has_body_mention"]:
            conf += 0.20
        if completeness["has_linked_evidence"]:
            conf += 0.25
        if ev_class["confidence"] > 0.7:
            conf += 0.10
        conf = min(conf, 0.85)  # Cap at 0.85 for rule mode

        return {
            "figure_id": figure_id,
            "figure_summary": figure_summary,
            "key_finding": key_finding,
            "evidence_type": ev_class["evidence_type"],
            "evidence_type_confidence": ev_class["confidence"],
            "evidence_type_reason": ev_class["reason"],
            "evidence_strength": evidence_strength,
            "supported_claims": related_claims[:5],
            "related_methods": related_methods[:5],
            "limitations": limitations,
            "grounding_sources": grounding_sources,
            "interpretation_confidence": round(conf, 2),
            "mode": "rule",
        }

    # ── Rule-based helpers ──

    @staticmethod
    def _build_llm_prompt(context: dict[str, Any]) -> str:
        """Build structured prompt for LLM interpretation."""
        caption = context.get("caption", "")
        label = context.get("normalized_label", "")
        body_texts = " ".join([
            m.get("sentence", "") for m in context.get("body_mentions", [])[:5]
        ])
        evidence_texts = " ".join([
            e.get("text", e.get("claim", ""))
            for e in context.get("linked_evidence", [])[:5]
        ])
        methods_texts = " ".join(context.get("related_methods", [])[:3])

        return f"""Analyze this scientific figure and provide a structured interpretation.

Figure: {label}
Caption: {caption}

Body text mentions: {body_texts if body_texts else "None available"}

Related evidence: {evidence_texts if evidence_texts else "None available"}

Related methods: {methods_texts if methods_texts else "None available"}

Return ONLY valid JSON (no markdown, no code fences) with these fields:
{{
  "figure_summary": "1-2 sentence summary of what the figure shows",
  "key_finding": "The single most important finding from this figure",
  "evidence_type": "One of: microscopy, western_blot, gel_image, survival_curve, bioassay, binding_assay, expression_analysis, heatmap, volcano_plot, phylogeny, structure_model, statistical_plot, workflow_diagram, unknown",
  "evidence_strength": "strong | moderate | weak | unclear",
  "supported_claims": ["claim 1", "claim 2"],
  "related_methods": ["method 1"],
  "limitations": ["limitation in what can be determined"],
  "grounding_sources": ["caption", "body_citation", "evidence_chunk"],
  "interpretation_confidence": 0.0_to_1.0
}}

CRITICAL: Only use information from the provided context. Do NOT invent findings, data values, or claims not present in the input."""

    @staticmethod
    def _summarize_caption(caption: str) -> str:
        """Create a concise summary from caption text."""
        if not caption:
            return ""
        # Take first 2 sentences or first 300 chars
        sentences = caption.replace("\n", " ").split(". ")
        if len(sentences) <= 2:
            return caption[:300].strip()
        return ". ".join(sentences[:2]).strip() + "."

    @staticmethod
    def _extract_key_finding(
        caption: str,
        body_mentions: list[dict[str, Any]],
        linked_evidence: list[dict[str, Any]],
    ) -> str:
        """Extract the key finding from available sources."""
        # Priority: evidence claims > body mentions > caption
        for ev in linked_evidence[:3]:
            finding = ev.get("finding", ev.get("claim", ev.get("text", "")))
            if finding and len(finding) > 20:
                return str(finding)[:300]

        for mention in body_mentions[:3]:
            sentence = mention.get("sentence", "")
            if sentence and len(sentence) > 30:
                return sentence[:300]

        # Fall back to caption summary
        if caption:
            sentences = caption.replace("\n", " ").split(". ")
            if sentences:
                return sentences[0].strip()[:300]

        return ""

    @staticmethod
    def _assess_strength(
        completeness: dict[str, bool],
        linked_evidence: list[dict[str, Any]],
        ev_class: dict[str, Any],
    ) -> str:
        """Assess evidence strength based on available sources."""
        score = 0
        if completeness.get("has_caption"):
            score += 1
        if completeness.get("has_body_mention"):
            score += 1
        if completeness.get("has_linked_evidence"):
            score += 2  # Evidence links are strongest

        evidence_type = ev_class.get("evidence_type", "unknown")
        if evidence_type in ("western_blot", "microscopy", "survival_curve"):
            score += 1  # These tend to be direct evidence

        if score >= 4:
            return "strong"
        elif score >= 2:
            return "moderate"
        elif score >= 1:
            return "weak"
        return "unclear"
