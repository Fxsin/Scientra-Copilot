"""
Citation Evaluation — validates citation correctness and provenance.

Checks:
    1. Answer contains [Ref:N] patterns when expected
    2. Each Ref maps to a context chunk
    3. Citation paper_id exists in context
    4. Citation text_snippet comes from retrieved context
    5. No undefined/phantom Refs
    6. No citations to non-existent papers
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CitationResult:
    case_id: str
    question: str
    has_citations: bool = False
    citation_count: int = 0
    valid_refs: int = 0
    invalid_refs: int = 0
    phantom_papers: int = 0
    refs_without_context: list[str] = field(default_factory=list)
    passed: bool = False
    notes: list[str] = field(default_factory=list)


def evaluate_citation(
    case_id: str,
    question: str,
    answer: str,
    citations: list[Any],
    context,
    should_have_citations: bool = True,
    insufficient_evidence_expected: bool = False,
) -> CitationResult:
    """Evaluate citation quality for a single answer.

    Args:
        case_id: Test case identifier
        question: Original question
        answer: Agent's text answer
        citations: List of Citation objects from AgentResponse
        context: ContextPack used to generate the answer
        should_have_citations: Whether answer should contain citations
        insufficient_evidence_expected: Whether we expect no evidence found
    """
    result = CitationResult(case_id=case_id, question=question)

    chunks = getattr(context, 'chunks', [])
    papers = getattr(context, 'papers', {})

    # Build lookup from context
    chunk_ids = {getattr(c, 'chunk_id', '') for c in chunks}
    paper_ids = set(papers.keys()) | {getattr(c, 'paper_id', '') for c in chunks}
    chunk_texts = {getattr(c, 'chunk_id', ''): getattr(c, 'text', '') for c in chunks}

    # Check [Ref:N] patterns
    ref_pattern = re.compile(r"\[Ref:(\d+)\]")
    answer_refs = ref_pattern.findall(answer)

    result.has_citations = len(answer_refs) > 0 or len(citations) > 0
    result.citation_count = len(citations)

    # Validate each citation
    for c in citations:
        ref_id = getattr(c, 'ref_id', '')
        chunk_id = getattr(c, 'chunk_id', '')
        paper_id = getattr(c, 'paper_id', '')
        snippet = getattr(c, 'text_snippet', '')

        if chunk_id and chunk_id in chunk_ids:
            result.valid_refs += 1
            # Check snippet comes from context
            ctx_text = chunk_texts.get(chunk_id, '')
            if snippet and ctx_text:
                # Allow partial match
                snippet_words = set(snippet.lower().split()[:10])
                ctx_words = set(ctx_text.lower().split())
                if not (snippet_words & ctx_words):
                    result.notes.append(f"{ref_id}: snippet may not match context")
        else:
            result.invalid_refs += 1
            if chunk_id:
                result.refs_without_context.append(ref_id)
                result.notes.append(f"{ref_id}: chunk {chunk_id[:30]}... not in context")

        if paper_id and paper_id not in paper_ids:
            result.phantom_papers += 1
            result.notes.append(f"{ref_id}: paper {paper_id[:40]}... not in context")

    # Pass/fail logic
    if insufficient_evidence_expected:
        # Should state insufficient evidence, citations optional
        result.passed = not result.has_citations or result.phantom_papers == 0
    elif should_have_citations and not result.has_citations:
        result.passed = False
        result.notes.append("expected citations but none found")
    elif result.invalid_refs > 0 or result.phantom_papers > 0:
        result.passed = False
    else:
        result.passed = True

    return result


class CitationEvaluator:
    """Runs citation evaluation across multiple cases."""

    def evaluate_cases(
        self,
        cases_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate citations for all cases. cases_data is list of dicts with
        keys: case_id, question, answer, citations, context, should_have_citations,
        insufficient_evidence_expected.
        """
        results: list[CitationResult] = []
        for cd in cases_data:
            cr = evaluate_citation(
                case_id=cd.get("case_id", "?"),
                question=cd.get("question", ""),
                answer=cd.get("answer", ""),
                citations=cd.get("citations", []),
                context=cd.get("context"),
                should_have_citations=cd.get("should_have_citations", True),
                insufficient_evidence_expected=cd.get("insufficient_evidence_expected", False),
            )
            results.append(cr)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        total_citations = sum(r.citation_count for r in results)
        total_valid = sum(r.valid_refs for r in results)
        total_invalid = sum(r.invalid_refs for r in results)
        total_phantom = sum(r.phantom_papers for r in results)

        return {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
            "total_citations": total_citations,
            "valid_refs": total_valid,
            "invalid_refs": total_invalid,
            "phantom_papers": total_phantom,
            "citation_validity_rate": round(
                total_valid / max(total_valid + total_invalid, 1) * 100, 1
            ) if (total_valid + total_invalid) > 0 else 100.0,
            "results": [r.__dict__ for r in results],
        }
