"""Research Opportunity Ranking — deterministic multi-factor scoring (Phase 3.3).

Generates a ranked list of research opportunities by combining
cross-paper gap clusters with linked hypothesis clusters.

No LLM calls — all scoring is rule-based.

Output:
  05_Knowledge/research_opportunities/opportunity_ranking.json
  05_Knowledge/research_opportunities/opportunity_summary.json
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = None  # lazy init


def _root() -> Path:
    global PROJECT_ROOT
    if PROJECT_ROOT is None:
        candidate = Path(__file__).resolve().parent
        for _ in range(6):
            if (candidate / "Config" / "llm_config.yaml").exists():
                PROJECT_ROOT = candidate
                return PROJECT_ROOT
            candidate = candidate.parent
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
    return PROJECT_ROOT


DEFAULT_GAP_CLUSTERS = str(_root() / "05_Knowledge" / "cross_paper_gaps" / "gap_clusters.json")
DEFAULT_HYP_CLUSTERS = str(_root() / "05_Knowledge" / "cross_paper_hypotheses" / "hypothesis_clusters.json")
DEFAULT_OUTPUT_DIR = str(_root() / "05_Knowledge" / "research_opportunities")

# Scoring weights
W_EVIDENCE = 0.30
W_FEASIBILITY = 0.25
W_NOVELTY = 0.20
W_IMPACT = 0.15
W_CONFIDENCE = 0.10
W_RISK_PENALTY = 0.10


def _load_json(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── Scoring Functions ──


def _score_evidence(gc: dict, hcs: list[dict]) -> float:
    """Evidence score based on paper_count, gap_count, support_level, confidence, quality."""
    paper_count = gc.get("paper_count", 1)
    gap_count = gc.get("member_gap_count", 1)
    support = gc.get("support_level", "single_paper")
    confidence = gc.get("confidence_mean", 0.5)

    # Paper count: log scale, saturates at ~30
    paper_score = min(1.0, paper_count / 15.0)

    # Gap count bonus
    gap_bonus = min(0.15, gap_count * 0.005)

    # Support bonus
    support_bonus = {"strong_multi_paper": 0.15, "multi_paper": 0.08, "single_paper": 0.0}.get(support, 0)

    # Hypothesis quality mean
    hyp_quality = (
        sum(h.get("quality_score_mean", 0.5) for h in hcs) / len(hcs)
        if hcs else 0.5
    )

    score = paper_score * 0.35 + confidence * 0.25 + hyp_quality * 0.15 + gap_bonus + support_bonus
    return round(min(1.0, score), 3)


def _score_feasibility(gc: dict, hcs: list[dict]) -> float:
    """Feasibility based on risk distribution, testable predictions, experiments."""
    if not hcs:
        return 0.3

    # Aggregate risk distribution
    total_risk = Counter()
    for h in hcs:
        rd = h.get("risk_level_distribution", {})
        for k, v in rd.items():
            total_risk[k] += v

    total = sum(total_risk.values()) or 1
    low_ratio = total_risk.get("low", 0) / total
    med_ratio = total_risk.get("medium", 0) / total
    high_ratio = total_risk.get("high", 0) / total

    risk_score = low_ratio * 1.0 + med_ratio * 0.6 + high_ratio * 0.15

    # Has testable predictions?
    has_predictions = any(len(h.get("testable_predictions", []) or []) > 0 for h in hcs)
    has_experiments = any(len(h.get("suggested_experiments", []) or []) > 0 for h in hcs)

    pred_bonus = 0.1 if has_predictions else 0.0
    exp_bonus = 0.1 if has_experiments else 0.0

    score = risk_score * 0.5 + pred_bonus + exp_bonus + 0.2
    return round(min(1.0, score), 3)


def _score_novelty(gc: dict, hcs: list[dict]) -> float:
    """Novelty based on gap_type, paper_count, and whether gaps remain open."""
    gap_type = gc.get("gap_type", "unknown")
    paper_count = gc.get("paper_count", 1)

    # Type weights
    type_weights = {
        "mechanistic": 0.9,
        "contradiction": 0.95,
        "translation": 0.7,
        "evidence": 0.6,
        "unknown": 0.85,
        "methodological": 0.4,
        "scope": 0.3,
    }
    type_score = type_weights.get(gap_type, 0.5)

    # Multi-paper open gap = more novel (many papers see the same gap but can't close it)
    multi_bonus = min(0.3, paper_count * 0.02)

    score = type_score * 0.7 + multi_bonus
    return round(min(1.0, score), 3)


def _score_impact(gc: dict, hcs: list[dict]) -> float:
    """Impact based on paper_count, gap_type, support_level, why_it_matters."""
    paper_count = gc.get("paper_count", 1)
    support = gc.get("support_level", "single_paper")
    why = gc.get("why_it_matters_merged", "")
    gap_type = gc.get("gap_type", "unknown")

    # Paper breadth
    breadth = min(1.0, paper_count / 12.0)

    # Support level
    support_score = {"strong_multi_paper": 1.0, "multi_paper": 0.7, "single_paper": 0.3}.get(support, 0.3)

    # Why it matters length/detail
    why_score = min(1.0, len(why) / 200.0) if why else 0.3

    # Gap type impact: translation, mechanistic, contradiction are high impact
    type_impact = {
        "translation": 0.9, "mechanistic": 0.85, "contradiction": 0.9,
        "evidence": 0.7, "methodological": 0.5, "unknown": 0.6, "scope": 0.4,
    }.get(gap_type, 0.5)

    score = breadth * 0.25 + support_score * 0.3 + why_score * 0.15 + type_impact * 0.3
    return round(min(1.0, score), 3)


def _score_confidence(gc: dict, hcs: list[dict]) -> float:
    """Confidence from gap confidence and hypothesis quality."""
    gap_conf = gc.get("confidence_mean", 0.5)
    hyp_qual = (
        sum(h.get("quality_score_mean", 0.5) for h in hcs) / len(hcs)
        if hcs else 0.5
    )
    return round(gap_conf * 0.4 + hyp_qual * 0.6, 3)


def _score_risk_penalty(gc: dict, hcs: list[dict]) -> float:
    """Risk penalty from high-risk hyps, overclaim, safety warnings."""
    if not hcs:
        return 0.15

    total_risk = Counter()
    total_overclaim = 0
    for h in hcs:
        rd = h.get("risk_level_distribution", {})
        for k, v in rd.items():
            total_risk[k] += v
        total_overclaim += h.get("overclaim_risk_count", 0)

    total = sum(total_risk.values()) or 1
    high_ratio = total_risk.get("high", 0) / total

    # High risk penalty
    high_penalty = high_ratio * 0.4

    # Overclaim penalty
    overclaim_penalty = min(0.15, total_overclaim * 0.03)

    return round(min(0.5, high_penalty + overclaim_penalty), 3)


# ── Category Classification ──


def _classify_opportunity(gc: dict, hcs: list[dict], scores: dict) -> str:
    """Classify opportunity into a category."""
    gap_type = gc.get("gap_type", "unknown")
    support = gc.get("support_level", "single_paper")
    paper_count = gc.get("paper_count", 1)
    evidence = scores.get("evidence_score", 0.5)
    novelty = scores.get("novelty_score", 0.5)
    feasibility = scores.get("feasibility_score", 0.5)
    overall = scores.get("opportunity_score", 0.5)

    if gap_type == "contradiction":
        return "contradiction_to_resolve"
    if gap_type == "methodological":
        return "method_gap"
    if gap_type == "scope":
        return "broad_scope_gap"
    if gap_type == "translation":
        return "translation_gap"

    if gap_type == "mechanistic" and support in ("strong_multi_paper", "multi_paper"):
        return "underexplored_mechanism"

    if overall >= 0.7 and feasibility >= 0.7 and paper_count >= 2:
        return "high_confidence_next_step"

    if evidence >= 0.6 and novelty >= 0.7:
        return "high_impact_open_question"

    if novelty >= 0.8 and evidence < 0.5:
        return "speculative_hypothesis"

    return "high_impact_open_question"


# ── Suggested Next Steps ──


def _suggest_next_steps(gc: dict, hcs: list[dict], category: str) -> list[str]:
    """Generate suggested next steps based on category."""
    steps: list[str] = []
    gap_type = gc.get("gap_type", "")

    if category in ("underexplored_mechanism", "high_impact_open_question"):
        steps.append("Design targeted experiments to elucidate the molecular mechanism")
        if hcs and hcs[0].get("suggested_experiments"):
            steps.append(f"Test: {hcs[0]['suggested_experiments'][0][:150]}")

    if category == "translation_gap":
        steps.append("Validate laboratory findings in field or clinically relevant models")
        steps.append("Conduct comparative studies across species/conditions")

    if category == "contradiction_to_resolve":
        steps.append("Design head-to-head comparative experiments")
        steps.append("Meta-analysis of existing contradictory data")

    if category == "method_gap":
        steps.append("Develop or adopt improved methodology")
        steps.append("Validate existing findings with complementary techniques")

    if category == "broad_scope_gap":
        steps.append("Expand study to additional species/conditions/tissues")
        steps.append("Multi-center or multi-population replication study")

    if category == "speculative_hypothesis":
        steps.append("Generate preliminary data to assess hypothesis viability")
        steps.append("Computational modeling or in silico analysis first")

    if not steps:
        steps.append("Review literature for related work")
        steps.append("Formulate specific experimental plan")

    return steps[:4]


# ── Main Ranking ──


def rank_research_opportunities(
    gap_clusters_path: str = DEFAULT_GAP_CLUSTERS,
    hypothesis_clusters_path: str = DEFAULT_HYP_CLUSTERS,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    config: dict[str, Any] | None = None,
    top_k: int = 50,
    min_paper_count: int = 1,
) -> dict[str, Any]:
    """Generate ranked research opportunities.

    Links gap clusters with their hypothesis clusters, computes
    multi-factor scores, and produces a ranked opportunity list.

    Returns:
        dict with opportunities, summary, and metadata.
    """
    # Load data
    gc_data = _load_json(gap_clusters_path)
    hc_data = _load_json(hypothesis_clusters_path)

    if not gc_data or not hc_data:
        return _empty_result()

    gap_clusters = gc_data.get("clusters", []) or []
    hyp_clusters = hc_data.get("hypothesis_clusters", []) or []

    # Index hypotheses by linked gap cluster
    hyp_by_gap: dict[str, list[dict]] = {}
    for h in hyp_clusters:
        gc_id = h.get("linked_gap_cluster_id", "")
        if gc_id:
            hyp_by_gap.setdefault(gc_id, []).append(h)

    # Generate opportunities
    opportunities: list[dict] = []
    for gc in gap_clusters:
        if gc.get("paper_count", 0) < min_paper_count:
            continue

        gc_id = gc["cluster_id"]
        hcs = hyp_by_gap.get(gc_id, [])

        # Compute scores
        evidence = _score_evidence(gc, hcs)
        feasibility = _score_feasibility(gc, hcs)
        novelty = _score_novelty(gc, hcs)
        impact = _score_impact(gc, hcs)
        confidence = _score_confidence(gc, hcs)
        risk_penalty = _score_risk_penalty(gc, hcs)

        opportunity_score = round(
            evidence * W_EVIDENCE
            + feasibility * W_FEASIBILITY
            + novelty * W_NOVELTY
            + impact * W_IMPACT
            + confidence * W_CONFIDENCE
            - risk_penalty * W_RISK_PENALTY,
            3,
        )

        scores = {
            "evidence_score": evidence,
            "feasibility_score": feasibility,
            "novelty_score": novelty,
            "impact_score": impact,
            "confidence_score": confidence,
            "risk_penalty": risk_penalty,
            "opportunity_score": opportunity_score,
        }

        category = _classify_opportunity(gc, hcs, scores)

        # Risk level
        total_risk = Counter()
        for h in hcs:
            rd = h.get("risk_level_distribution", {})
            for k, v in rd.items():
                total_risk[k] += v
        total_r = sum(total_risk.values()) or 1
        if total_risk.get("high", 0) / total_r > 0.3:
            risk_level = "high"
        elif total_risk.get("medium", 0) / total_r > 0.5:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Evidence support level
        if gc.get("support_level") == "strong_multi_paper" and evidence >= 0.75:
            ev_support = "strong"
        elif gc.get("support_level") in ("multi_paper", "strong_multi_paper"):
            ev_support = "moderate"
        else:
            ev_support = "weak"

        # Testability
        has_preds = any(len(h.get("testable_predictions", []) or []) > 0 for h in hcs)
        has_exps = any(len(h.get("suggested_experiments", []) or []) > 0 for h in hcs)
        if has_preds and has_exps:
            testability = "high"
        elif has_preds or has_exps:
            testability = "medium"
        else:
            testability = "low"

        # Representative
        rep_hyp = hcs[0].get("unified_hypothesis_statement", "") if hcs else ""

        category_str = _classify_opportunity(gc, hcs, scores)

        opp = {
            "opportunity_id": f"opp_{len(opportunities) + 1:04d}",
            "linked_gap_cluster_id": gc_id,
            "linked_hypothesis_cluster_ids": [h.get("hypothesis_cluster_id", "") for h in hcs],
            "title": gc.get("unified_gap_statement", "")[:150],
            "opportunity_statement": gc.get("unified_gap_statement", ""),
            "why_it_matters": gc.get("why_it_matters_merged", ""),
            "supporting_paper_count": gc.get("paper_count", 0),
            "supporting_gap_count": gc.get("member_gap_count", 0),
            "supporting_hypothesis_count": len(hcs),
            "evidence_support_level": ev_support,
            "testability": testability,
            "risk_level": risk_level,
            **scores,
            "category": category_str,
            "representative_gap": gc.get("representative_gap", ""),
            "representative_hypothesis": rep_hyp,
            "suggested_next_steps": _suggest_next_steps(gc, hcs, category_str),
            "member_papers": gc.get("paper_ids", []),
            "warnings": [],
        }
        opportunities.append(opp)

    # Sort by opportunity_score descending
    opportunities.sort(key=lambda o: -o["opportunity_score"])

    # Apply top_k
    top_opportunities = opportunities[:top_k] if top_k > 0 else opportunities

    # Category distribution
    cat_dist = Counter(o["category"] for o in top_opportunities)

    # Score stats
    scores_list = [o["opportunity_score"] for o in top_opportunities]
    avg_score = round(sum(scores_list) / len(scores_list), 3) if scores_list else 0.0

    summary = {
        "total_opportunities": len(opportunities),
        "top_k": len(top_opportunities),
        "min_paper_count": min_paper_count,
        "category_distribution": dict(cat_dist.most_common()),
        "average_opportunity_score": avg_score,
        "score_min": round(min(scores_list), 3) if scores_list else 0.0,
        "score_max": round(max(scores_list), 3) if scores_list else 0.0,
        "high_confidence_next_step": cat_dist.get("high_confidence_next_step", 0),
        "high_impact_open_question": cat_dist.get("high_impact_open_question", 0),
        "underexplored_mechanism": cat_dist.get("underexplored_mechanism", 0),
        "translation_gap": cat_dist.get("translation_gap", 0),
        "contradiction_to_resolve": cat_dist.get("contradiction_to_resolve", 0),
        "scoring_weights": {
            "evidence": W_EVIDENCE, "feasibility": W_FEASIBILITY,
            "novelty": W_NOVELTY, "impact": W_IMPACT,
            "confidence": W_CONFIDENCE, "risk_penalty": W_RISK_PENALTY,
        },
    }

    result = {
        "status": "generated",
        "total_opportunities": len(opportunities),
        "opportunities": top_opportunities,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_output(Path(output_dir), result)
    return result


def _empty_result() -> dict:
    return {
        "status": "no_data",
        "total_opportunities": 0,
        "opportunities": [],
        "summary": {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_output(output_path: Path, result: dict) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "opportunity_ranking.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path / "opportunity_summary.json").write_text(
        json.dumps(result.get("summary", {}), ensure_ascii=False, indent=2), encoding="utf-8")


def load_opportunities(output_dir: str | None = None) -> dict | None:
    path = Path(output_dir or DEFAULT_OUTPUT_DIR) / "opportunity_ranking.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
