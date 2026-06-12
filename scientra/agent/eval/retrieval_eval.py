"""
Retrieval Evaluation — measures context retrieval quality per test case.

Metrics:
    - asset_hits: chunks from pdf_asset_chunks
    - evidence_hits: chunks from evidence_chunks
    - unique_papers: distinct paper_ids
    - empty_context_rate: cases with 0 chunks
    - source_balance: asset/evidence ratio
    - chunk_type_distribution
    - retrieval_latency_ms
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from scientra.agent.eval.eval_cases import EvalCase


@dataclass
class RetrievalResult:
    case_id: str
    question: str
    total_chunks: int = 0
    asset_hits: int = 0
    evidence_hits: int = 0
    unique_papers: int = 0
    is_empty: bool = True
    source_balance: float = 0.0
    chunk_types: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    top_scores: list[float] = field(default_factory=list)
    passed: bool = False
    notes: list[str] = field(default_factory=list)


def evaluate_retrieval(case: EvalCase, context) -> RetrievalResult:
    """Evaluate retrieval quality for a single test case.

    Args:
        case: The test case definition
        context: ContextPack from ContextBuilder.build_context()

    Returns:
        RetrievalResult with all metrics
    """
    result = RetrievalResult(
        case_id=case.case_id,
        question=case.question,
        latency_ms=getattr(context, 'elapsed_ms', 0.0),
    )

    chunks = getattr(context, 'chunks', [])
    result.total_chunks = len(chunks)
    result.is_empty = len(chunks) == 0

    if result.is_empty:
        if case.should_retrieve_context and case.category not in ("out_of_scope_query",):
            result.notes.append("expected context but got empty")
        result.passed = not case.should_retrieve_context or case.category == "out_of_scope_query"
        return result

    # Count by source
    for c in chunks:
        src = getattr(c, 'source', 'unknown')
        if src == 'pdf_asset_chunks':
            result.asset_hits += 1
        elif src == 'evidence_chunks':
            result.evidence_hits += 1

    # Unique papers
    papers = set()
    for c in chunks:
        pid = getattr(c, 'paper_id', '')
        if pid:
            papers.add(pid)
    result.unique_papers = len(papers)

    # Source balance
    if result.evidence_hits > 0:
        result.source_balance = round(result.asset_hits / result.evidence_hits, 2)

    # Chunk type distribution
    for c in chunks:
        ct = getattr(c, 'chunk_type', 'unknown')
        result.chunk_types[ct] = result.chunk_types.get(ct, 0) + 1

    # Top scores
    result.top_scores = [getattr(c, 'score', 0.0) for c in chunks[:5]]

    # Pass/fail
    if case.should_retrieve_context:
        result.passed = result.total_chunks > 0
    else:
        result.passed = True  # out-of-scope may legitimately have no context

    if not result.passed:
        result.notes.append("failed: no context retrieved when expected")

    return result


class RetrievalEvaluator:
    """Runs retrieval evaluation across multiple cases."""

    def __init__(self, context_builder=None):
        from scientra.agent.context_builder import ContextBuilder
        self.context_builder = context_builder or ContextBuilder()

    def evaluate_cases(
        self, cases: list[EvalCase], top_k: int = 5
    ) -> dict[str, Any]:
        """Evaluate retrieval for all cases. Returns summary dict."""
        results: list[RetrievalResult] = []
        empty_count = 0
        total_latency = 0.0

        for case in cases:
            t0 = time.time()
            context = self.context_builder.build_context(
                question=case.question,
                top_k=top_k,
            )
            rt = evaluate_retrieval(case, context)
            if not hasattr(context, 'elapsed_ms') or rt.latency_ms == 0:
                rt.latency_ms = (time.time() - t0) * 1000
            results.append(rt)

            if rt.is_empty and case.should_retrieve_context and case.category != "out_of_scope_query":
                empty_count += 1
            total_latency += rt.latency_ms

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        total_chunks = sum(r.total_chunks for r in results)
        avg_papers = sum(r.unique_papers for r in results) / max(total, 1)

        return {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
            "empty_context_count": empty_count,
            "empty_context_rate": round(empty_count / max(total, 1) * 100, 1),
            "total_chunks_retrieved": total_chunks,
            "avg_chunks_per_case": round(total_chunks / max(total, 1), 1),
            "avg_unique_papers": round(avg_papers, 1),
            "avg_latency_ms": round(total_latency / max(total, 1), 0),
            "results": [r.__dict__ for r in results],
        }
