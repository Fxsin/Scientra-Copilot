"""
Regression Runner — CLI harness for Literature Agent evaluation.

Usage:
    python -m scientra.agent.eval.regression_runner --use-llm false --case-type all
    python -m scientra.agent.eval.regression_runner --use-llm true --limit 10
    python -m scientra.agent.eval.regression_runner --use-llm false --case-type negative_control_query
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from scientra.agent.eval.eval_cases import get_cases, EvalCase
from scientra.agent.eval.retrieval_eval import RetrievalEvaluator, evaluate_retrieval
from scientra.agent.eval.citation_eval import CitationEvaluator, evaluate_citation
from scientra.agent.eval.answer_grounding_eval import GroundingEvaluator, evaluate_grounding
from scientra.agent.eval.hallucination_tests import HallucinationEvaluator, evaluate_hallucination
from scientra.agent.eval.eval_report import generate_report


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def run_without_llm(cases: list[EvalCase], limit: int = 0) -> dict[str, Any]:
    """Run evaluation without calling Claude — tests retrieval + rules."""
    if limit > 0:
        cases = cases[:limit]

    print(f"\nRunning {len(cases)} cases (use_llm=false)...\n")

    from scientra.agent.context_builder import ContextBuilder

    cb = ContextBuilder()
    ret_evaluator = RetrievalEvaluator(cb)
    cit_evaluator = CitationEvaluator()
    grd_evaluator = GroundingEvaluator()
    hal_evaluator = HallucinationEvaluator()

    # Phase 1: Retrieval
    print("[1/3] Evaluating retrieval...")
    retrieval_summary = ret_evaluator.evaluate_cases(cases, top_k=5)
    print(f"      Pass: {retrieval_summary['passed']}/{retrieval_summary['total_cases']} "
          f"({retrieval_summary['pass_rate']}%) | "
          f"Avg latency: {retrieval_summary['avg_latency_ms']}ms | "
          f"Avg chunks: {retrieval_summary['avg_chunks_per_case']}")

    # Build context for each case
    contexts = {}
    for case in cases:
        contexts[case.case_id] = cb.build_context(question=case.question, top_k=5)

    # Phase 2: Citation + hallucination (use no-LLM answer based on context)
    print("[2/3] Evaluating citations & grounding...")
    cit_data: list[dict[str, Any]] = []
    grd_data: list[dict[str, Any]] = []
    hal_data: list[dict[str, Any]] = []

    for case in cases:
        ctx = contexts.get(case.case_id)
        chunks = getattr(ctx, 'chunks', [])

        # Build a no-LLM answer stub for rule-based evaluation
        if case.category == "out_of_scope_query":
            answer = "This question is outside the scope of this literature database. I can help with questions about Bt insecticidal proteins, particularly Vip3A toxins."
        elif case.insufficient_evidence_expected:
            answer = "Insufficient evidence in current database. No relevant context found for this question."
        elif not chunks:
            answer = "Insufficient evidence in current database. No relevant context found."
        else:
            snippet_lines = []
            for i, c in enumerate(chunks[:5], 1):
                snippet_lines.append(f"[Ref:{i}] {getattr(c, 'text', '')[:200]}")
            answer = "Context retrieved:\n" + "\n".join(snippet_lines)

        cit_data.append({
            "case_id": case.case_id,
            "question": case.question,
            "answer": answer,
            "citations": [],
            "context": ctx,
            "should_have_citations": case.should_have_citations,
            "insufficient_evidence_expected": case.insufficient_evidence_expected,
        })

        grd_data.append({
            "case_id": case.case_id,
            "question": case.question,
            "answer": answer,
            "insufficient_evidence_expected": case.insufficient_evidence_expected,
            "category": case.category,
        })

        hal_data.append({
            "case_id": case.case_id,
            "question": case.question,
            "answer": answer,
            "context": ctx,
            "category": case.category,
        })

    citation_summary = cit_evaluator.evaluate_cases(cit_data)
    grounding_summary = grd_evaluator.evaluate_cases(grd_data)
    hallucination_summary = hal_evaluator.evaluate_cases(hal_data)

    print(f"      Citation pass: {citation_summary['pass_rate']}%")
    print(f"      Grounding pass: {grounding_summary['pass_rate']}%")
    print(f"      Hallucination pass: {hallucination_summary['pass_rate']}%")
    print(f"      Negative control pass: {hallucination_summary['negative_control_pass_rate']}%")

    # Phase 3: Intent accuracy
    print("[3/3] Evaluating intent accuracy...")
    intent_correct = 0
    for case in cases:
        from scientra.agent.literature_agent import LiteratureAgent
        agent = LiteratureAgent()
        detected = agent._detect_intent(case.question)
        if detected == case.expected_intent:
            intent_correct += 1

    intent_accuracy = round(intent_correct / max(len(cases), 1) * 100, 1)
    print(f"      Intent accuracy: {intent_accuracy}% ({intent_correct}/{len(cases)})")

    # Aggregate
    total_pass = (
        retrieval_summary['passed']
        + citation_summary['passed']
        + grounding_summary['passed']
        + hallucination_summary['passed']
    )
    total_checks = len(cases) * 4
    overall_pass_rate = round(total_pass / max(total_checks, 1) * 100, 1)

    return {
        "mode": "no_llm",
        "total_cases": len(cases),
        "overall_pass_rate": overall_pass_rate,
        "intent_accuracy": intent_accuracy,
        "retrieval": retrieval_summary,
        "citation": citation_summary,
        "grounding": grounding_summary,
        "hallucination": hallucination_summary,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run_with_llm(cases: list[EvalCase], limit: int = 10) -> dict[str, Any]:
    """Run evaluation WITH Claude — tests real answers."""
    if limit > 0:
        cases = cases[:limit]

    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set. Falling back to use_llm=false mode.")
        return run_without_llm(cases, limit)

    print(f"\nRunning {len(cases)} cases (use_llm=true)...\n")

    from scientra.agent.literature_agent import LiteratureAgent
    from scientra.agent.context_builder import ContextBuilder

    agent = LiteratureAgent()
    cb = ContextBuilder()
    cit_evaluator = CitationEvaluator()
    grd_evaluator = GroundingEvaluator()
    hal_evaluator = HallucinationEvaluator()

    cit_data: list[dict[str, Any]] = []
    grd_data: list[dict[str, Any]] = []
    hal_data: list[dict[str, Any]] = []
    retrieval_results: list[dict[str, Any]] = []
    intent_correct = 0

    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case.case_id}: {case.question[:60]}...")
        t0 = time.time()

        # Run full agent
        response = agent.ask(question=case.question, top_k=5)
        ctx = response.raw_context
        elapsed = (time.time() - t0) * 1000

        # Intent
        detected = agent._detect_intent(case.question)
        if detected == case.expected_intent:
            intent_correct += 1

        # Retrieval
        rt = evaluate_retrieval(case, ctx)
        rt.latency_ms = elapsed
        retrieval_results.append(rt.__dict__)

        # Citation
        cit_data.append({
            "case_id": case.case_id,
            "question": case.question,
            "answer": response.answer,
            "citations": response.citations,
            "context": ctx,
            "should_have_citations": case.should_have_citations,
            "insufficient_evidence_expected": case.insufficient_evidence_expected,
        })

        # Grounding
        grd_data.append({
            "case_id": case.case_id,
            "question": case.question,
            "answer": response.answer,
            "insufficient_evidence_expected": case.insufficient_evidence_expected,
            "category": case.category,
        })

        # Hallucination
        hal_data.append({
            "case_id": case.case_id,
            "question": case.question,
            "answer": response.answer,
            "context": ctx,
            "category": case.category,
        })

    # Summarize
    citation_summary = cit_evaluator.evaluate_cases(cit_data)
    grounding_summary = grd_evaluator.evaluate_cases(grd_data)
    hallucination_summary = hal_evaluator.evaluate_cases(hal_data)

    ret_passed = sum(1 for r in retrieval_results if r.get("passed", False))
    intent_accuracy = round(intent_correct / max(len(cases), 1) * 100, 1)

    total_pass = ret_passed + citation_summary['passed'] + grounding_summary['passed'] + hallucination_summary['passed']
    total_checks = len(cases) * 4
    overall_pass_rate = round(total_pass / max(total_checks, 1) * 100, 1)

    return {
        "mode": "with_llm",
        "total_cases": len(cases),
        "overall_pass_rate": overall_pass_rate,
        "intent_accuracy": intent_accuracy,
        "retrieval": {
            "total_cases": len(cases),
            "passed": ret_passed,
            "failed": len(cases) - ret_passed,
            "pass_rate": round(ret_passed / max(len(cases), 1) * 100, 1),
            "results": retrieval_results,
        },
        "citation": citation_summary,
        "grounding": grounding_summary,
        "hallucination": hallucination_summary,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scientra Literature Agent Evaluation — Phase 0.7B",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scientra.agent.eval.regression_runner --use-llm false --case-type all
  python -m scientra.agent.eval.regression_runner --use-llm true --limit 10
  python -m scientra.agent.eval.regression_runner --use-llm false --case-type negative_control_query
        """,
    )
    parser.add_argument("--use-llm", type=str, default="false", choices=["true", "false"],
                        help="Whether to call Claude (default: false)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max cases to run (0 = all)")
    parser.add_argument("--case-type", type=str, default="all",
                        help="Category filter: method_query, negative_control_query, all, etc.")
    parser.add_argument("--output", type=str,
                        default="06_PDF_DataAssets/00_registry/agent_eval_report.json",
                        help="Output JSON path")
    parser.add_argument("--report", type=str,
                        default="06_PDF_DataAssets/00_registry/agent_eval_report.md",
                        help="Output Markdown report path")

    args = parser.parse_args()
    use_llm = args.use_llm == "true"
    root = _get_project_root()

    cases = get_cases(args.case_type)
    if not cases:
        print(f"No cases found for category: {args.case_type}")
        return 1

    print(f"Loaded {len(cases)} test cases (category={args.case_type})")

    if use_llm:
        result = run_with_llm(cases, args.limit)
    else:
        result = run_without_llm(cases, args.limit)

    # Save JSON
    json_path = root / args.output
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = json_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(json_path)
    print(f"\nJSON report saved: {json_path}")

    # Generate Markdown
    md_path = root / args.report
    md = generate_report(result)
    tmp_md = md_path.with_suffix(".tmp")
    tmp_md.write_text(md, encoding="utf-8")
    tmp_md.replace(md_path)
    print(f"Markdown report saved: {md_path}")

    # Summary
    print(f"\n=== Evaluation Summary ===")
    print(f"Mode:           {result['mode']}")
    print(f"Total cases:    {result['total_cases']}")
    print(f"Overall pass:   {result['overall_pass_rate']}%")
    print(f"Intent acc:     {result.get('intent_accuracy', 'N/A')}%")
    r = result.get('retrieval', {})
    print(f"Retrieval:      {r.get('pass_rate', 'N/A')}%")
    h = result.get('hallucination', {})
    print(f"Hallucination:  {h.get('pass_rate', 'N/A')}%")
    print(f"Neg control:    {h.get('negative_control_pass_rate', 'N/A')}%")
    print(f"Citation:       {result.get('citation', {}).get('pass_rate', 'N/A')}%")
    print(f"Grounding:      {result.get('grounding', {}).get('pass_rate', 'N/A')}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
