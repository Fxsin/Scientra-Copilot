"""Opportunity Expert Review — AI-powered critical review of top research opportunities (Phase 3.5).

Uses LLM to perform structured expert review of the highest-ranked research
opportunities, evaluating scientific importance, evidence strength, feasibility,
novelty, and risks.

Output:
  05_Knowledge/research_opportunity_reviews/opportunity_reviews.json
  05_Knowledge/research_opportunity_reviews/opportunity_review_summary.json
"""

from __future__ import annotations

import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _detect_project_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "Config" / "llm_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

DEFAULT_OPPORTUNITIES = str(PROJECT_ROOT / "05_Knowledge" / "research_opportunities" / "opportunity_ranking.json")
DEFAULT_GAP_CLUSTERS = str(PROJECT_ROOT / "05_Knowledge" / "cross_paper_gaps" / "gap_clusters.json")
DEFAULT_HYP_CLUSTERS = str(PROJECT_ROOT / "05_Knowledge" / "cross_paper_hypotheses" / "hypothesis_clusters.json")
DEFAULT_EVOLUTION = str(PROJECT_ROOT / "05_Knowledge" / "research_evolution" / "research_evolution.json")
DEFAULT_OUTPUT_DIR = str(PROJECT_ROOT / "05_Knowledge" / "research_opportunity_reviews")

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "top_k": 10,
    "min_opportunity_score": 0.65,
    "max_context_chars": 12000,
    "include_evolution_context": True,
}


# ── Helpers ──


def _load_json(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_prompt_template() -> str:
    path = PROMPT_DIR / "opportunity_expert_review.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _extract_json_from_response(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response with repair strategies."""
    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try code block
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try brace extraction
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _simple_template(text: str, variables: dict[str, str]) -> str:
    """Simple {{var}} template replacement.

    Also handles {% if var %}...{% endif %} blocks.
    """
    result = text

    # Handle if/endif blocks
    if_pattern = re.compile(r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}', re.DOTALL)
    for match in if_pattern.finditer(result):
        var_name = match.group(1).strip()
        block_content = match.group(2)
        if variables.get(var_name):
            result = result.replace(match.group(0), block_content)
        else:
            result = result.replace(match.group(0), "")

    # Handle {{var}} replacements
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", value)

    return result


def _build_evolution_context(opp: dict, evolution_data: dict) -> dict | None:
    """Build evolution context for an opportunity from evolution data."""
    gc_id = opp.get("linked_gap_cluster_id", "")
    gap_evolution = evolution_data.get("gap_evolution", [])
    opp_evolution = evolution_data.get("opportunity_evolution", [])

    ge = next((g for g in gap_evolution if g.get("cluster_id") == gc_id), None)
    oe = next((o for o in opp_evolution if o.get("opportunity_id") == opp.get("opportunity_id", "")), None)

    if not ge and not oe:
        return None

    return {
        "gap_trend": ge.get("trend", "unknown") if ge else "unknown",
        "gap_first_seen": ge.get("first_seen_year", 0) if ge else 0,
        "gap_last_seen": ge.get("last_seen_year", 0) if ge else 0,
        "gap_active_span": ge.get("active_year_span", 0) if ge else 0,
        "gap_persistence_score": ge.get("persistence_score", 0) if ge else 0,
        "gap_closure_signal": ge.get("closure_signal", "unknown") if ge else "unknown",
        "opportunity_trend": oe.get("trend", "unknown") if oe else "unknown",
        "priority_trajectory": oe.get("priority_trajectory", "unknown") if oe else "unknown",
    }


def _render_review_prompt(
    opportunity: dict,
    gap_cluster: dict | None,
    hypothesis_clusters: list[dict],
    evolution_context: dict | None,
    max_context_chars: int = 12000,
) -> str:
    """Render the expert review prompt for one opportunity."""
    template = _load_prompt_template()

    opp_str = json.dumps(opportunity, ensure_ascii=False, indent=2)
    gc_str = json.dumps(gap_cluster, ensure_ascii=False, indent=2) if gap_cluster else "{}"
    hc_str = json.dumps(hypothesis_clusters, ensure_ascii=False, indent=2)
    evo_str = json.dumps(evolution_context, ensure_ascii=False, indent=2) if evolution_context else ""

    # Truncate if needed
    total_len = len(opp_str) + len(gc_str) + len(hc_str) + len(evo_str) + len(template)
    if total_len > max_context_chars * 2:
        # Truncate hypothesis clusters — keep top 3
        if len(hypothesis_clusters) > 3:
            truncated_hcs = hypothesis_clusters[:3]
            hc_str = json.dumps(truncated_hcs, ensure_ascii=False, indent=2)
        # Truncate gap cluster details
        if gap_cluster and len(gc_str) > 3000:
            gc_compact = {
                k: gap_cluster.get(k) for k in
                ["cluster_id", "unified_gap_statement", "gap_type", "paper_count",
                 "member_gap_count", "support_level", "representative_gap"]
                if k in gap_cluster
            }
            gc_str = json.dumps(gc_compact, ensure_ascii=False, indent=2)

    variables = {
        "opportunity": opp_str,
        "gap_cluster": gc_str,
        "hypothesis_clusters": hc_str,
        "evolution_context": evo_str,
        "opportunity_id": opportunity.get("opportunity_id", ""),
    }

    return _simple_template(template, variables)


# ── Single Review ──


def _review_one_opportunity(
    opportunity: dict,
    gap_cluster: dict | None,
    hypothesis_clusters: list[dict],
    evolution_context: dict | None,
    rank: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Review a single opportunity via LLM."""
    from scientra.ai import call_llm

    prompt = _render_review_prompt(
        opportunity, gap_cluster, hypothesis_clusters,
        evolution_context, config.get("max_context_chars", 12000),
    )

    system = (
        "You are a senior research scientist performing expert peer review of research opportunities. "
        "You evaluate strictly based on provided evidence. Do not invent information. "
        "Return ONLY valid JSON, no markdown, no prose outside JSON."
    )

    response = call_llm(
        prompt=prompt,
        task_name="opportunity_review",
        system_prompt=system,
        temperature=0.3,
        max_tokens=3072,
        paper_id=opportunity.get("opportunity_id", ""),
    )

    review: dict[str, Any] = {
        "opportunity_id": opportunity.get("opportunity_id", ""),
        "rank": rank,
        "title": opportunity.get("title", ""),
        "opportunity_score": opportunity.get("opportunity_score", 0.0),
        "review_status": "error",
        "scientific_importance": "",
        "evidence_strength_assessment": "",
        "technical_feasibility": "",
        "novelty_assessment": "",
        "major_risks": [],
        "key_missing_evidence": [],
        "recommended_next_steps": [],
        "possible_experimental_routes": [],
        "expected_impact": "",
        "review_confidence": 0.0,
        "review_warnings": [],
        "usage": {
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "cost_estimate": response.cost_estimate,
            "success": response.success,
            "error": response.error if not response.success else "",
        },
    }

    if not response.success:
        review["review_status"] = "error"
        review["review_warnings"].append(f"LLM call failed: {response.error}")
        return review

    parsed = _extract_json_from_response(response.text)
    if parsed is None:
        review["review_status"] = "error"
        review["review_warnings"].append("Failed to parse LLM JSON response")
        review["scientific_importance"] = response.text[:500]
        return review

    # Merge parsed fields
    review["review_status"] = parsed.get("review_status", "unknown")
    review["scientific_importance"] = parsed.get("scientific_importance", "")
    review["evidence_strength_assessment"] = parsed.get("evidence_strength_assessment", "")
    review["technical_feasibility"] = parsed.get("technical_feasibility", "")
    review["novelty_assessment"] = parsed.get("novelty_assessment", "")
    review["major_risks"] = parsed.get("major_risks", []) or []
    review["key_missing_evidence"] = parsed.get("key_missing_evidence", []) or []
    review["recommended_next_steps"] = parsed.get("recommended_next_steps", []) or []
    review["possible_experimental_routes"] = parsed.get("possible_experimental_routes", []) or []
    review["expected_impact"] = parsed.get("expected_impact", "")
    review["review_confidence"] = float(parsed.get("review_confidence", 0.0))
    review["review_warnings"] = (parsed.get("review_warnings", []) or []) + review["review_warnings"]

    # Validate review_status
    valid_statuses = {"accept", "revise", "reject", "insufficient_data", "unknown"}
    if review["review_status"] not in valid_statuses:
        review["review_status"] = "unknown"

    return review


# ── Main Function ──


def review_research_opportunities(
    opportunities_path: str = DEFAULT_OPPORTUNITIES,
    gap_clusters_path: str = DEFAULT_GAP_CLUSTERS,
    hypothesis_clusters_path: str = DEFAULT_HYP_CLUSTERS,
    evolution_path: str = DEFAULT_EVOLUTION,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    top_k: int = 10,
    config: dict | None = None,
) -> dict[str, Any]:
    """Review top research opportunities via LLM expert review.

    Args:
        opportunities_path: Path to opportunity_ranking.json.
        gap_clusters_path: Path to gap_clusters.json.
        hypothesis_clusters_path: Path to hypothesis_clusters.json.
        evolution_path: Path to research_evolution.json.
        output_dir: Output directory for reviews.
        top_k: Number of top opportunities to review.
        config: Configuration overrides.

    Returns:
        dict with reviews, summary, and metadata.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    effective_top_k = top_k if top_k > 0 else cfg.get("top_k", 10)
    min_score = cfg.get("min_opportunity_score", 0.65)

    # ── Load data ──
    opp_data = _load_json(opportunities_path)
    gc_data = _load_json(gap_clusters_path)
    hc_data = _load_json(hypothesis_clusters_path)
    evo_data = _load_json(evolution_path)

    if not opp_data or not opp_data.get("opportunities"):
        return _empty_result("No opportunities found")

    opportunities = opp_data.get("opportunities", [])
    gap_clusters_list = gc_data.get("clusters", []) if gc_data else []
    hyp_clusters_list = hc_data.get("hypothesis_clusters", []) if hc_data else []

    # Index gap clusters and hypothesis clusters
    gc_map: dict[str, dict] = {gc.get("cluster_id", ""): gc for gc in gap_clusters_list}
    hc_by_gap: dict[str, list[dict]] = {}
    for hc in hyp_clusters_list:
        gc_id = hc.get("linked_gap_cluster_id", "")
        if gc_id:
            hc_by_gap.setdefault(gc_id, []).append(hc)

    # ── Filter and select top opportunities ──
    eligible = [
        o for o in opportunities
        if o.get("opportunity_score", 0) >= min_score
    ]
    targets = eligible[:effective_top_k]

    if not targets:
        return _empty_result(f"No opportunities meet min_score >= {min_score}")

    # ── Check if task is enabled ──
    from scientra.ai import get_config
    llm_cfg = get_config()
    if not llm_cfg.is_task_enabled("opportunity_review"):
        return {
            "status": "skipped",
            "message": "Task 'opportunity_review' is disabled in llm_config.yaml → enabled_tasks",
            "eligible_count": len(eligible),
            "target_count": len(targets),
            "reviews": [],
            "summary": _build_summary([], 0.0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Review each opportunity ──
    reviews: list[dict] = []
    total_cost = 0.0

    for i, opp in enumerate(targets, 1):
        gc_id = opp.get("linked_gap_cluster_id", "")
        gap_cluster = gc_map.get(gc_id)
        hyps = hc_by_gap.get(gc_id, [])

        # Build evolution context
        evo_context = None
        if cfg.get("include_evolution_context") and evo_data:
            evo_context = _build_evolution_context(opp, evo_data)

        review = _review_one_opportunity(
            opp, gap_cluster, hyps, evo_context, i, cfg,
        )
        reviews.append(review)
        if review.get("usage", {}).get("cost_estimate", 0) > 0:
            total_cost += review["usage"]["cost_estimate"]

    # ── Build summary ──
    summary = _build_summary(reviews, total_cost)

    # ── Save output ──
    result = {
        "status": "generated",
        "reviews": reviews,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_output(Path(output_dir), result)
    return result


def _build_summary(reviews: list[dict], total_cost: float) -> dict[str, Any]:
    """Build review summary statistics."""
    from collections import Counter

    status_counts = Counter(r.get("review_status", "unknown") for r in reviews)
    confidences = [r.get("review_confidence", 0) for r in reviews]

    return {
        "reviewed_count": len(reviews),
        "accept_count": status_counts.get("accept", 0),
        "revise_count": status_counts.get("revise", 0),
        "reject_count": status_counts.get("reject", 0),
        "insufficient_data_count": status_counts.get("insufficient_data", 0),
        "error_count": status_counts.get("error", 0),
        "unknown_count": status_counts.get("unknown", 0),
        "status_distribution": dict(status_counts),
        "average_review_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        "min_confidence": round(min(confidences), 3) if confidences else 0.0,
        "max_confidence": round(max(confidences), 3) if confidences else 0.0,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_review_usd": round(total_cost / len(reviews), 6) if reviews else 0.0,
    }


def _empty_result(message: str = "No data available") -> dict:
    return {
        "status": "no_data",
        "message": message,
        "reviews": [],
        "summary": _build_summary([], 0.0),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_output(output_path: Path, result: dict) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "opportunity_reviews.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path / "opportunity_review_summary.json").write_text(
        json.dumps(result.get("summary", {}), ensure_ascii=False, indent=2), encoding="utf-8")


def load_reviews(output_dir: str | None = None) -> dict | None:
    path = Path(output_dir or DEFAULT_OUTPUT_DIR) / "opportunity_reviews.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
