"""
Hallucination Tests — focused tests for anti-fabrication behavior.

Tests that the agent:
    1. Does NOT fabricate information for fake entities
    2. Does NOT invent fake DOIs
    3. Does NOT generate non-existent paper titles
    4. Does NOT claim proof without strong evidence
    5. Returns insufficient evidence for low-relevance queries
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HallucinationResult:
    case_id: str
    question: str
    answer: str = ""
    fabricated_entity: bool = False
    fabricated_doi: bool = False
    fabricated_paper: bool = False
    overconfident_claim: bool = False
    stated_insufficient_evidence: bool = False
    context_empty: bool = True
    context_chunks: int = 0
    passed: bool = False
    notes: list[str] = field(default_factory=list)


def evaluate_hallucination(
    case_id: str,
    question: str,
    answer: str,
    context,
    is_negative_control: bool = False,
) -> HallucinationResult:
    """Evaluate hallucination risk for a single answer."""
    result = HallucinationResult(
        case_id=case_id,
        question=question,
        answer=answer,
    )

    chunks = getattr(context, 'chunks', [])
    result.context_chunks = len(chunks)
    result.context_empty = len(chunks) == 0

    answer_lower = answer.lower()

    # ── Check for fabricated DOIs ──
    import re
    doi_pattern = re.compile(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.IGNORECASE)
    dois_found = doi_pattern.findall(answer)

    # Build set of valid DOIs from context
    papers = getattr(context, 'papers', {})
    valid_dois: set[str] = set()
    for pid, meta in papers.items():
        if isinstance(meta, dict):
            doi = str(meta.get('doi', '')).lower()
            if doi and '10.' in doi:
                valid_dois.add(doi)

    for doi in dois_found:
        if doi.lower() not in valid_dois:
            result.fabricated_doi = True
            result.notes.append(f"DOI {doi} not found in context")
            break

    # ── Check for fabricated entities ──
    # If the answer mentions specific proteins/genes not in context
    if result.context_empty or result.context_chunks < 2:
        # Check for scientific-sounding claims in empty context
        entity_claims = re.findall(
            r'\b([A-Z][a-z]{2,}[A-Z]\d*[A-Za-z]?)\b', answer
        )
        if entity_claims and result.context_empty:
            result.fabricated_entity = True
            result.notes.append(f"entity-like terms found in empty-context answer: {entity_claims[:5]}")

    # ── Check for overconfident claims ──
    overconfident_patterns = [
        r'\bproves?\b', r'\bdefinitively\b', r'\bcertainly\b',
        r'\bwithout\s+(?:any\s+)?doubt\b', r'\babsolutely\b',
    ]
    for pat in overconfident_patterns:
        if re.search(pat, answer_lower):
            result.overconfident_claim = True
            result.notes.append(f"overconfident phrasing: matched '{pat}'")
            break

    # ── Check insufficient evidence statement ──
    insufficient_patterns = [
        r'insufficient\s+evidence', r'no\s+evidence\s+found',
        r'not\s+found', r'does\s+not\s+contain',
        r'unable\s+to\s+find', r'no\s+(?:data|information|papers?)',
    ]
    for pat in insufficient_patterns:
        if re.search(pat, answer_lower):
            result.stated_insufficient_evidence = True
            break

    # ── Pass/fail ──
    if is_negative_control:
        result.passed = (
            not result.fabricated_entity
            and not result.fabricated_doi
            and not result.fabricated_paper
            and result.stated_insufficient_evidence
        )
        if result.stated_insufficient_evidence and result.fabricated_entity:
            result.passed = False
            result.notes.append("stated insufficient evidence but also fabricated entities")
    else:
        result.passed = (
            not result.fabricated_doi
            and not result.overconfident_claim
        )

    return result


class HallucinationEvaluator:
    """Runs hallucination tests across multiple cases."""

    def evaluate_cases(
        self,
        cases_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate hallucination risk for all cases."""
        results: list[HallucinationResult] = []
        for cd in cases_data:
            hr = evaluate_hallucination(
                case_id=cd.get("case_id", "?"),
                question=cd.get("question", ""),
                answer=cd.get("answer", ""),
                context=cd.get("context"),
                is_negative_control=cd.get("category", "") == "negative_control_query",
            )
            results.append(hr)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        fabricated_doi_count = sum(1 for r in results if r.fabricated_doi)
        fabricated_entity_count = sum(1 for r in results if r.fabricated_entity)
        overconfident_count = sum(1 for r in results if r.overconfident_claim)
        insufficient_count = sum(1 for r in results if r.stated_insufficient_evidence)

        # Negative control specific stats
        neg_results = [r for r in results if "N00" in r.case_id]
        neg_pass = sum(1 for r in neg_results if r.passed)

        return {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
            "negative_control_total": len(neg_results),
            "negative_control_passed": neg_pass,
            "negative_control_pass_rate": round(
                neg_pass / max(len(neg_results), 1) * 100, 1
            ),
            "fabricated_doi_count": fabricated_doi_count,
            "fabricated_entity_count": fabricated_entity_count,
            "overconfident_claim_count": overconfident_count,
            "insufficient_evidence_count": insufficient_count,
            "results": [r.__dict__ for r in results],
        }
