"""Figure Quality Checker — evaluate interpretation quality and detect overclaim risk.

Checks:
  1. Caption presence
  2. Body citation presence
  3. Linked evidence presence
  4. Overclaim risk (strong claims without sufficient grounding)
  5. Evidence strength appropriateness
  6. Interpretation confidence vs grounding
"""

from __future__ import annotations

from typing import Any

# Overclaim trigger words that suggest strong claims
OVERCLAIM_PATTERNS = [
    "demonstrate", "prove", "confirm", "establish", "validate",
    "definitively", "conclusively", "undoubtedly", "unequivocally",
    "first time", "novel", "breakthrough", "discovery",
]

# Conservative language patterns (good)
CONSERVATIVE_PATTERNS = [
    "suggest", "indicate", "consistent with", "support the hypothesis",
    "may", "might", "could", "appears to", "likely", "potentially",
    "further studies", "additional experiments", "preliminary",
]


class FigureQualityChecker:
    """Check and score figure interpretation quality."""

    def check(self, context: dict[str, Any], interpretation: dict[str, Any]) -> dict[str, Any]:
        """Run all quality checks on a figure context + interpretation.

        Args:
            context: Figure context dict.
            interpretation: Interpretation dict.

        Returns:
            Quality report dict.
        """
        figure_id = context.get("figure_id", "")
        warnings: list[str] = []
        issues: list[str] = []

        # Check 1: Caption presence
        caption_score = self._check_caption(context)

        # Check 2: Body citation presence
        body_score = self._check_body_mentions(context)

        # Check 3: Linked evidence presence
        evidence_score = self._check_linked_evidence(context, interpretation)

        # Check 4: Overclaim risk
        overclaim_risk, overclaim_details = self._check_overclaim(context, interpretation)

        # Check 5: Evidence strength appropriateness
        strength_ok, strength_detail = self._check_strength_appropriateness(
            context, interpretation
        )

        # Check 6: Interpretation confidence vs grounding
        conf_ok, conf_detail = self._check_confidence_grounding(context, interpretation)

        # Aggregate
        if caption_score < 0.7:
            warnings.append("Figure has no or very short caption.")
            issues.append("caption_missing_or_short")
        if body_score < 0.5:
            warnings.append("Figure not cited in body text.")
            issues.append("no_body_citation")
        if evidence_score < 0.5:
            warnings.append("No evidence chunks linked to this figure.")
            issues.append("no_linked_evidence")
        if overclaim_risk != "low":
            warnings.append(f"Overclaim risk: {overclaim_risk} — {overclaim_details}")
            issues.append(f"overclaim_{overclaim_risk}")
        if not strength_ok:
            warnings.append(strength_detail)
            issues.append("strength_mismatch")
        if not conf_ok:
            warnings.append(conf_detail)
            issues.append("confidence_grounding_mismatch")

        # Compute overall quality score
        scores = [caption_score, body_score, evidence_score]
        if overclaim_risk == "low":
            scores.append(0.9)
        elif overclaim_risk == "medium":
            scores.append(0.6)
        else:
            scores.append(0.3)

        quality_score = round(sum(scores) / len(scores), 2)

        # Add mode-specific warnings
        mode = interpretation.get("mode", "rule")
        if mode in ("rule", "rule_fallback"):
            if interpretation.get("interpretation_confidence", 0) > 0.7:
                warnings.append(
                    "Rule-based interpretation has high confidence — consider reviewing manually."
                )

        return {
            "figure_id": figure_id,
            "quality_score": quality_score,
            "warnings": warnings,
            "issues": issues,
            "overclaim_risk": overclaim_risk,
            "overclaim_details": overclaim_details,
            "caption_score": round(caption_score, 2),
            "body_citation_score": round(body_score, 2),
            "evidence_score": round(evidence_score, 2),
        }

    def check_all(
        self, contexts: list[dict[str, Any]], interpretations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Run checks on all figures."""
        int_by_id = {i.get("figure_id", ""): i for i in interpretations}
        results = []
        for ctx in contexts:
            fig_id = ctx.get("figure_id", "")
            interp = int_by_id.get(fig_id, {})
            results.append(self.check(ctx, interp))
        return results

    # ── Individual checks ──

    @staticmethod
    def _check_caption(context: dict[str, Any]) -> float:
        caption = context.get("caption", "")
        if not caption:
            return 0.1
        if len(caption) < 30:
            return 0.4
        if len(caption) < 80:
            return 0.7
        return 0.95

    @staticmethod
    def _check_body_mentions(context: dict[str, Any]) -> float:
        mentions = context.get("body_mentions", [])
        if not mentions:
            return 0.1
        if len(mentions) == 1:
            return 0.6
        return 0.9

    @staticmethod
    def _check_linked_evidence(context: dict[str, Any], interpretation: dict[str, Any]) -> float:
        evidence = context.get("linked_evidence", [])
        if not evidence:
            return 0.1
        if len(evidence) == 1:
            return 0.65
        return 0.9

    @staticmethod
    def _check_overclaim(
        context: dict[str, Any], interpretation: dict[str, Any]
    ) -> tuple[str, str]:
        """Detect overclaim risk in interpretation."""
        text_parts = [
            interpretation.get("figure_summary", ""),
            interpretation.get("key_finding", ""),
        ]
        # Add supported claims
        for claim in interpretation.get("supported_claims", []):
            text_parts.append(str(claim))

        combined = " ".join(text_parts).lower()

        completeness = context.get("context_completeness", {})
        grounding_count = sum(1 for v in completeness.values() if v)

        overclaim_count = sum(1 for kw in OVERCLAIM_PATTERNS if kw in combined)
        conservative_count = sum(1 for kw in CONSERVATIVE_PATTERNS if kw in combined)

        if overclaim_count >= 3 and grounding_count <= 1:
            return ("high", f"Strong language ({overclaim_count} overclaim terms) with only {grounding_count} grounding sources.")
        elif overclaim_count >= 2 and grounding_count <= 1:
            return ("medium", f"Some strong claims with limited grounding ({grounding_count} sources).")
        elif overclaim_count >= 1 and conservative_count == 0:
            return ("medium", "Assertive language without caveats — overclaim risk detected.")
        elif overclaim_count >= 1:
            return ("low", "")
        else:
            return ("low", "")

    @staticmethod
    def _check_strength_appropriateness(
        context: dict[str, Any], interpretation: dict[str, Any]
    ) -> tuple[bool, str]:
        """Check that evidence strength claim matches available grounding."""
        strength = interpretation.get("evidence_strength", "unclear")
        completeness = context.get("context_completeness", {})
        grounding_count = sum(1 for v in completeness.values() if v)

        if strength == "strong" and grounding_count <= 1:
            return (False, "Evidence rated 'strong' but only 1 grounding source — possible overstatement.")
        if strength == "moderate" and grounding_count == 0:
            return (False, "Evidence rated 'moderate' but no grounding sources — strength may be inflated.")
        return (True, "")

    @staticmethod
    def _check_confidence_grounding(
        context: dict[str, Any], interpretation: dict[str, Any]
    ) -> tuple[bool, str]:
        """Check interpretation confidence against available grounding."""
        conf = interpretation.get("interpretation_confidence", 0)
        completeness = context.get("context_completeness", {})
        grounding_count = sum(1 for v in completeness.values() if v)

        mode = interpretation.get("mode", "rule")

        if mode in ("rule", "rule_fallback") and conf > 0.8:
            return (False, f"Rule-based interpretation confidence ({conf}) is unrealistically high.")
        if conf > 0.8 and grounding_count <= 1:
            return (False, f"High confidence ({conf}) with only {grounding_count} grounding sources.")
        if conf > 0.6 and grounding_count == 0:
            return (False, f"Moderate confidence ({conf}) with zero grounding sources.")
        return (True, "")
