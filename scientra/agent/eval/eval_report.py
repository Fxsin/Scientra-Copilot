"""
Eval Report Generator — produces Markdown evaluation report.

Output: 06_PDF_DataAssets/00_registry/agent_eval_report.md
"""

from __future__ import annotations

from typing import Any


def generate_report(result: dict[str, Any]) -> str:
    """Generate a Markdown evaluation report from runner results."""
    lines: list[str] = []
    lines.append("# Scientra Literature Agent V1 — Evaluation Report")
    lines.append("")
    lines.append(f"**Phase:** 0.7B — Evaluation, Safety & Anti-Hallucination")
    lines.append(f"**Mode:** {result.get('mode', 'unknown')}")
    lines.append(f"**Timestamp:** {result.get('timestamp', 'unknown')}")
    lines.append(f"**Total cases:** {result.get('total_cases', 0)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Overview
    lines.append("## 1. Overall Results")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Overall pass rate | **{result.get('overall_pass_rate', 0)}%** |")
    lines.append(f"| Intent accuracy | **{result.get('intent_accuracy', 0)}%** |")
    lines.append("")

    # 2. Retrieval
    ret = result.get("retrieval", {})
    lines.append("## 2. Retrieval Evaluation")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Pass rate | **{ret.get('pass_rate', 0)}%** |")
    lines.append(f"| Cases passed | {ret.get('passed', 0)}/{ret.get('total_cases', 0)} |")
    lines.append(f"| Empty context rate | {ret.get('empty_context_rate', 0)}% |")
    lines.append(f"| Avg chunks per case | {ret.get('avg_chunks_per_case', 0)} |")
    lines.append(f"| Avg unique papers | {ret.get('avg_unique_papers', 0)} |")
    lines.append(f"| Avg latency | {ret.get('avg_latency_ms', 0)}ms |")
    lines.append("")

    # 3. Citation
    cit = result.get("citation", {})
    lines.append("## 3. Citation Validity")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Pass rate | **{cit.get('pass_rate', 0)}%** |")
    lines.append(f"| Total citations | {cit.get('total_citations', 0)} |")
    lines.append(f"| Valid refs | {cit.get('valid_refs', 0)} |")
    lines.append(f"| Invalid refs | {cit.get('invalid_refs', 0)} |")
    lines.append(f"| Phantom papers | {cit.get('phantom_papers', 0)} |")
    lines.append(f"| Citation validity rate | {cit.get('citation_validity_rate', 0)}% |")
    lines.append("")

    # 4. Grounding
    grd = result.get("grounding", {})
    lines.append("## 4. Answer Grounding")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Pass rate | **{grd.get('pass_rate', 0)}%** |")
    lines.append(f"| Cases with unsupported phrases | {grd.get('cases_with_unsupported_phrases', 0)} |")
    lines.append(f"| Cases stating insufficient evidence | {grd.get('cases_stating_insufficient_evidence', 0)} |")
    lines.append("")

    # 5. Hallucination
    hal = result.get("hallucination", {})
    lines.append("## 5. Hallucination Control")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Pass rate | **{hal.get('pass_rate', 0)}%** |")
    lines.append(f"| Negative control total | {hal.get('negative_control_total', 0)} |")
    lines.append(f"| Negative control pass rate | **{hal.get('negative_control_pass_rate', 0)}%** |")
    lines.append(f"| Fabricated DOI count | {hal.get('fabricated_doi_count', 0)} |")
    lines.append(f"| Fabricated entity count | {hal.get('fabricated_entity_count', 0)} |")
    lines.append(f"| Overconfident claim count | {hal.get('overconfident_claim_count', 0)} |")
    lines.append(f"| Insufficient evidence statements | {hal.get('insufficient_evidence_count', 0)} |")
    lines.append("")

    # 6. Failed cases
    lines.append("## 6. Failed Cases")
    lines.append("")
    failed = _collect_failed(result)
    if failed:
        for f in failed[:15]:
            lines.append(f"- **{f['case_id']}** ({f['dimension']}): {f['reason'][:120]}")
        if len(failed) > 15:
            lines.append(f"- ... and {len(failed) - 15} more failures")
    else:
        lines.append("> No failures detected.")
    lines.append("")

    # 7. Risk assessment
    lines.append("## 7. Risk Assessment")
    lines.append("")
    risks: list[str] = []

    if ret.get("empty_context_rate", 0) > 30:
        risks.append(f"- High empty context rate ({ret['empty_context_rate']}%). May indicate poor retrieval coverage.")
    if cit.get("phantom_papers", 0) > 0:
        risks.append(f"- {cit['phantom_papers']} phantom paper citations detected. Citation provenance needs review.")
    if hal.get("fabricated_doi_count", 0) > 0:
        risks.append(f"- {hal['fabricated_doi_count']} fabricated DOIs. Anti-hallucination guardrails needed.")
    if hal.get("negative_control_pass_rate", 100) < 80:
        risks.append(f"- Low negative control pass rate ({hal['negative_control_pass_rate']}%). Agent may fabricate under uncertainty.")
    if result.get("overall_pass_rate", 100) < 70:
        risks.append(f"- Overall pass rate below 70%. Significant quality issues.")

    if risks:
        for r in risks:
            lines.append(r)
    else:
        lines.append("> No critical risks detected.")
    lines.append("")

    # 8. Recommendations
    lines.append("## 8. Phase 0.8 Readiness")
    lines.append("")
    overall = result.get("overall_pass_rate", 0)
    neg_pass = hal.get("negative_control_pass_rate", 0)
    if overall >= 80 and neg_pass >= 80:
        lines.append("**Recommendation: Ready for Phase 0.8 — Web Chat & query/assets API.**")
        lines.append("")
        lines.append("All critical safety gates passed:")
        lines.append(f"- Overall pass rate: {overall}% >= 80%")
        lines.append(f"- Negative control pass rate: {neg_pass}% >= 80%")
        lines.append(f"- No fabricated DOIs: {hal.get('fabricated_doi_count', 0)}")
        lines.append(f"- No phantom papers: {cit.get('phantom_papers', 0)}")
    else:
        lines.append("**Recommendation: Address risks before Phase 0.8.**")
        lines.append("")
        lines.append("Critical issues to resolve:")
        if overall < 80:
            lines.append(f"- Overall pass rate ({overall}%) below 80% threshold")
        if neg_pass < 80:
            lines.append(f"- Negative control pass rate ({neg_pass}%) below 80% threshold")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by Scientra Copilot Phase 0.7B — Agent Evaluation Framework*")

    return "\n".join(lines)


def _collect_failed(result: dict[str, Any]) -> list[dict[str, str]]:
    """Collect all failed cases across dimensions."""
    failed: list[dict[str, str]] = []

    for dim_key, dim_label in [
        ("retrieval", "retrieval"),
        ("citation", "citation"),
        ("grounding", "answer_grounding"),
        ("hallucination", "hallucination"),
    ]:
        dim = result.get(dim_key, {})
        for r in dim.get("results", []):
            if not r.get("passed", False):
                notes = r.get("notes", [])
                failed.append({
                    "case_id": r.get("case_id", "?"),
                    "dimension": dim_label,
                    "reason": "; ".join(notes) if notes else "no specific reason",
                })

    return failed
