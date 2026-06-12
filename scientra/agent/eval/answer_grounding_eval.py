"""
Answer Grounding Evaluation — checks whether answers are evidence-based.

Without LLM (use_llm=false): rule-based checks only.
With LLM (use_llm=true): full answer evaluation.

Rules:
    1. Citation keys must come from context
    2. No unsupported absolute phrases in answer
    3. Distinguish evidence-based vs inference vs insufficient
    4. Negative controls must return insufficient evidence
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# Phrases that suggest overconfidence or fabrication
UNSUPPORTED_PHRASES = [
    "definitely proves",
    "all studies show",
    "completely confirms",
    "without any doubt",
    "without doubt",
    "it is definitively proven",
    "the DOI is",  # DOI should only come from context, never invented
    "this paper proves",  # scientific papers don't "prove"
    "clearly demonstrates beyond question",
    "absolutely certain",
]

# Phrases indicating appropriate scientific caution (positive signals)
CAUTION_PHRASES = [
    "evidence suggests",
    "may indicate",
    "is associated with",
    "has been observed",
    "studies report",
    "according to",
    "the data show",
    "results suggest",
    "insufficient evidence",
    "no evidence",
    "not found in",
    "no mention of",
    "no data",
    "unknown",
    "not studied",
    "further research",
]


@dataclass
class GroundingResult:
    case_id: str
    question: str
    answer: str = ""
    has_unsupported_phrase: bool = False
    unsupported_phrases_found: list[str] = field(default_factory=list)
    has_caution_phrase: bool = False
    caution_phrases_found: list[str] = field(default_factory=list)
    states_insufficient_evidence: bool = False
    distinguishes_inference: bool = False
    answer_length: int = 0
    passed: bool = False
    notes: list[str] = field(default_factory=list)


def evaluate_grounding(
    case_id: str,
    question: str,
    answer: str,
    insufficient_evidence_expected: bool = False,
    is_negative_control: bool = False,
    is_out_of_scope: bool = False,
) -> GroundingResult:
    """Evaluate answer grounding with rule-based checks."""
    result = GroundingResult(
        case_id=case_id,
        question=question,
        answer=answer,
        answer_length=len(answer),
    )

    answer_lower = answer.lower()

    # Check unsupported phrases
    for phrase in UNSUPPORTED_PHRASES:
        if phrase.lower() in answer_lower:
            result.has_unsupported_phrase = True
            result.unsupported_phrases_found.append(phrase)

    # Check caution phrases
    for phrase in CAUTION_PHRASES:
        if phrase.lower() in answer_lower:
            result.has_caution_phrase = True
            result.caution_phrases_found.append(phrase)

    # Check insufficient evidence
    insufficient_patterns = [
        r"insufficient\s+evidence",
        r"no\s+evidence\s+(?:was\s+)?found",
        r"not\s+(?:found|mentioned|present)\s+in\s+(?:the\s+)?(?:current\s+)?(?:database|context|literature)",
        r"does\s+not\s+(?:contain|include|mention)",
        r"no\s+(?:data|information|papers?|studies?|results?)\s+(?:was\s+)?found",
        r"unable\s+to\s+(?:find|locate|identify)",
    ]
    for pat in insufficient_patterns:
        if re.search(pat, answer_lower):
            result.states_insufficient_evidence = True
            break

    # Check distinguishes inference
    if re.search(r"\b(?:inference|may|might|could|possibly|potentially|hypothesize|speculate)\b", answer_lower):
        result.distinguishes_inference = True

    # Pass/fail
    if is_out_of_scope:
        # Should redirect, not answer from literature with citations
        # Accept if answer says "out of scope" or doesn't use [Ref:N] citations
        has_citations = bool(re.search(r'\[Ref:', answer))
        states_out_of_scope = any(
            phrase in answer_lower for phrase in [
                "outside the scope", "out of scope", "cannot answer",
                "not able to", "i can help with questions about",
                "this question is outside",
            ]
        )
        result.passed = states_out_of_scope or not has_citations
        if not result.passed:
            result.notes.append("out-of-scope question received literature-based answer with citations")
    elif is_negative_control or insufficient_evidence_expected:
        # Must state insufficient evidence, must not fabricate
        result.passed = (
            result.states_insufficient_evidence
            and not result.has_unsupported_phrase
        )
        if not result.states_insufficient_evidence:
            result.notes.append("should state insufficient evidence but did not")
        if result.has_unsupported_phrase:
            result.notes.append(f"contains unsupported phrases: {result.unsupported_phrases_found}")
    else:
        # Normal case: should not have unsupported phrases
        result.passed = not result.has_unsupported_phrase
        if result.has_unsupported_phrase:
            result.notes.append(f"contains unsupported phrases: {result.unsupported_phrases_found}")

    return result


def _contains_literature_answer(text: str) -> bool:
    """Check if answer appears to answer from literature context."""
    literature_signals = [
        r"\b(?:paper|study|research|evidence|data|result|finding|author)\b",
        r"\b(?:vip3|bt\s*toxin|cry\d|insecticidal|protein|receptor)\b",
        r"\[Ref:",
    ]
    return any(re.search(p, text) for p in literature_signals)


class GroundingEvaluator:
    """Runs grounding evaluation across multiple cases."""

    def evaluate_cases(
        self,
        cases_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate grounding for all cases."""
        results: list[GroundingResult] = []
        for cd in cases_data:
            gr = evaluate_grounding(
                case_id=cd.get("case_id", "?"),
                question=cd.get("question", ""),
                answer=cd.get("answer", ""),
                insufficient_evidence_expected=cd.get("insufficient_evidence_expected", False),
                is_negative_control=cd.get("category", "") == "negative_control_query",
                is_out_of_scope=cd.get("category", "") == "out_of_scope_query",
            )
            results.append(gr)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        unsupported_count = sum(1 for r in results if r.has_unsupported_phrase)
        insufficient_count = sum(1 for r in results if r.states_insufficient_evidence)

        return {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
            "cases_with_unsupported_phrases": unsupported_count,
            "cases_stating_insufficient_evidence": insufficient_count,
            "results": [r.__dict__ for r in results],
        }
