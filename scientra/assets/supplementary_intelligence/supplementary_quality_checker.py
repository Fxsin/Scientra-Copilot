"""Supplementary Quality Checker — evaluate parse and interpretation quality."""

from __future__ import annotations

from typing import Any

OVERCLAIM_WORDS = ["prove", "confirm", "establish", "breakthrough", "novel", "first time", "definitively"]


class SupplementaryQualityChecker:
    """Check supplementary intelligence quality."""

    def check(
        self,
        parse_result: dict[str, Any],
        sections: list[dict[str, Any]] | None,
        interpretation: dict[str, Any],
    ) -> dict[str, Any]:
        supp_id = parse_result.get("supplementary_id", "")
        warnings: list[str] = []
        issues: list[str] = []

        # Parse quality
        ps = parse_result.get("parse_status", "failed")
        if ps == "unsupported":
            warnings.append("File format not supported for parsing.")
            issues.append("unsupported_format")
        elif ps == "failed":
            warnings.append("File parsing failed.")
            issues.append("parse_failed")
        elif ps == "empty":
            warnings.append("File parsed but contains no text.")
            issues.append("empty_content")

        text_len = parse_result.get("text_length", 0)
        if ps == "parsed" and text_len < 200:
            warnings.append("Very short content — may contain limited information.")
            issues.append("low_information")

        # Section quality
        n_sec = len(sections or [])
        if ps == "parsed" and n_sec == 0:
            warnings.append("No sections detected in parsed text.")
            issues.append("no_sections")

        # Check for references-only content
        if sections:
            ref_only = all(s.get("section_type") in ("supplementary_references", "unknown") for s in sections)
            if ref_only and n_sec <= 2:
                warnings.append("Content appears to be only references or unstructured text.")
                issues.append("references_only")

        # Evidence quality
        if interpretation:
            ev_count = len(interpretation.get("main_evidence_types", []))
            if ev_count == 0 and ps == "parsed":
                warnings.append("No evidence types detected in supplementary content.")
                issues.append("no_evidence_types")

        # Overclaim detection
        overclaim_risk, overclaim_detail = self._check_overclaim(interpretation)

        if overclaim_risk != "low":
            warnings.append(f"Overclaim risk: {overclaim_risk} — {overclaim_detail}")
            issues.append(f"overclaim_{overclaim_risk}")

        # Quality score
        scores = []
        scores.append(0.9 if ps == "parsed" else (0.4 if ps == "unsupported" else 0.1))
        scores.append(0.9 if n_sec > 1 else (0.5 if n_sec == 1 else 0.2))
        scores.append(0.3 if overclaim_risk == "high" else (0.6 if overclaim_risk == "medium" else 0.9))
        scores.append(0.8 if text_len > 500 else (0.5 if text_len > 100 else 0.2))
        quality_score = round(sum(scores) / len(scores), 2)

        return {
            "supplementary_id": supp_id,
            "quality_score": quality_score,
            "warnings": warnings,
            "issues": issues,
            "overclaim_risk": overclaim_risk,
            "overclaim_details": overclaim_detail,
        }

    def check_all(self, parse_results, sections_list, interpretations):
        return [self.check(p, s, i) for p, s, i in zip(parse_results, sections_list or [], interpretations)]

    @staticmethod
    def _check_overclaim(interp: dict) -> tuple[str, str]:
        text = f"{interp.get('supplementary_summary', '')} {' '.join(interp.get('key_contents', []))}".lower()
        grounding = len(interp.get("grounding_sources", []))
        count = sum(1 for w in OVERCLAIM_WORDS if w in text)
        if count >= 2 and grounding <= 1:
            return ("high", f"Strong language with only {grounding} grounding source(s).")
        if count >= 1 and grounding <= 1:
            return ("medium", "Assertive language without sufficient grounding.")
        return ("low", "")
