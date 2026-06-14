"""Table Quality Checker — evaluate interpretation quality and detect overclaim risk."""

from __future__ import annotations

from typing import Any

OVERCLAIM_PATTERNS = [
    "demonstrate", "prove", "confirm", "establish", "validate",
    "definitively", "conclusively", "undoubtedly", "unequivocally",
    "first time", "novel", "breakthrough",
]


class TableQualityChecker:
    """Check and score table interpretation quality."""

    def check(
        self,
        context: dict[str, Any],
        structure: dict[str, Any] | None,
        interpretation: dict[str, Any],
    ) -> dict[str, Any]:
        table_id = context.get("table_id", "")
        warnings: list[str] = []
        issues: list[str] = []

        caption_score = self._score_caption(context)
        body_score = self._score_body(context)
        evidence_score = self._score_evidence(context)
        structure_score = self._score_structure(structure)
        overclaim_risk, overclaim_detail = self._check_overclaim(context, interpretation)
        is_large = interpretation.get("is_large_table", False)

        if caption_score < 0.7:
            warnings.append("Table has no or short caption.")
            issues.append("caption_missing_or_short")
        if body_score < 0.5:
            warnings.append("Table not cited in body text.")
            issues.append("no_body_citation")
        if evidence_score < 0.5:
            warnings.append("No evidence chunks linked.")
            issues.append("no_linked_evidence")
        if structure_score < 0.5:
            warnings.append("Table structure could not be parsed.")
            issues.append("structure_unparseable")
        if is_large:
            warnings.append("Interpretation based on sample rows only — may miss details.")
            issues.append("large_table_sampled")
        if overclaim_risk != "low":
            warnings.append(f"Overclaim risk: {overclaim_risk} — {overclaim_detail}")
            issues.append(f"overclaim_{overclaim_risk}")

        if not interpretation.get("statistical_fields_summary"):
            warnings.append("No statistical fields detected — table may be purely descriptive.")

        scores = [caption_score, body_score, evidence_score, structure_score]
        scores.append(0.3 if overclaim_risk == "high" else (0.6 if overclaim_risk == "medium" else 0.9))
        quality_score = round(sum(scores) / len(scores), 2)

        return {
            "table_id": table_id,
            "quality_score": quality_score,
            "warnings": warnings,
            "issues": issues,
            "overclaim_risk": overclaim_risk,
            "overclaim_details": overclaim_detail,
            "caption_score": round(caption_score, 2),
            "body_citation_score": round(body_score, 2),
            "evidence_score": round(evidence_score, 2),
            "structure_score": round(structure_score, 2),
        }

    def check_all(self, contexts, structures, interpretations):
        sid = {s.get("table_id", s.get("asset_id", "")): s for s in (structures or [])}
        iid = {i.get("table_id", ""): i for i in (interpretations or [])}
        return [self.check(c, sid.get(c.get("table_id", "")), iid.get(c.get("table_id", ""), {})) for c in contexts]

    @staticmethod
    def _score_caption(ctx):
        c = ctx.get("caption", "")
        return 0.1 if not c else (0.4 if len(c) < 30 else (0.7 if len(c) < 80 else 0.95))

    @staticmethod
    def _score_body(ctx):
        m = ctx.get("body_mentions", [])
        return 0.1 if not m else (0.6 if len(m) == 1 else 0.9)

    @staticmethod
    def _score_evidence(ctx):
        e = ctx.get("linked_evidence", [])
        return 0.1 if not e else (0.65 if len(e) == 1 else 0.9)

    @staticmethod
    def _score_structure(structure):
        if not structure:
            return 0.1
        if structure.get("parse_status") == "parsed" and structure.get("sheets"):
            return 0.9
        if structure.get("parse_status") == "unsupported":
            return 0.3
        return 0.1

    @staticmethod
    def _check_overclaim(ctx, interp):
        text = f"{interp.get('table_summary', '')} {interp.get('key_finding', '')}".lower()
        completeness = ctx.get("context_completeness", {})
        grounding = sum(1 for v in completeness.values() if v)
        count = sum(1 for kw in OVERCLAIM_PATTERNS if kw in text)
        if count >= 3 and grounding <= 1:
            return ("high", f"Strong language ({count} terms) with only {grounding} sources.")
        if count >= 2 and grounding <= 1:
            return ("medium", f"Some strong claims with limited grounding.")
        if count >= 1 and grounding <= 1:
            return ("medium", "Assertive language without sufficient grounding.")
        return ("low", "")
