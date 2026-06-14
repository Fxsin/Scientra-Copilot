"""Gap-Hypothesis Quality Check — deterministic rule-based evaluation (Phase 2.3.1).

Scores gap extraction and hypothesis generation outputs without LLM calls.
Uses structural heuristics: grounding depth, specificity, testability,
overclaim detection, safety/ethics scanning.

Output: 03_Assets/ai/quality/gap_hypothesis/{paper_id}.json
Summary: 03_Assets/ai/quality/gap_hypothesis/summary.json
"""

from __future__ import annotations

import json
import re
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
OUTPUT_DIR = PROJECT_ROOT / "03_Assets" / "ai" / "quality" / "gap_hypothesis"

# ── Weight configuration ──

GAP_WEIGHTS = {
    "evidence_grounding": 0.40,
    "specificity": 0.35,
    "novelty": 0.25,
}

HYPOTHESIS_WEIGHTS = {
    "testability": 0.35,
    "rationale_grounding": 0.30,
    "experiment_feasibility": 0.35,
}

# ── Safety / ethics keyword patterns ──

DANGEROUS_KEYWORDS = [
    r"\bhuman\s+subject\b", r"\bclinical\s+trial\b", r"\bpatient\b",
    r"\bBSL-?3\b", r"\bBSL-?4\b", r"\bselect\s+agent\b",
    r"\bcontrolled\s+substance\b", r"\bnarcotic\b",
    r"\bweaponiz", r"\bbioterror", r"\bgain\s+of\s+function\b",
    r"\blethal\s+dose\b", r"\bLD50\b",
]

OVER_SPECIFIC_KEYWORDS = [
    r"\b[a-z]+\s+\d+\s*(mg|g|ml|ul|L)\s*/\s*(kg|g|ml|L)\b",  # specific dosages
    r"\b\d{2,3}\s*%\s*\(?(v/v|w/v|w/w)\)?",  # specific concentrations
    r"\bpH\s*\d+\.\d+\b",  # specific pH
    r"\bincubat(e|ion).*?\d+\s*(min|h|hr|hour)",  # specific incubation times
    r"\bvendor.*?(Sigma|Thermo|Invitrogen|Abcam|Cell Signaling)",  # vendor names
]

VAGUE_GAP_PATTERNS = [
    r"^(more|further|additional)\s+(research|studies|work|investigation)\s+(is|are)\s+(needed|required)",
    r"^the\s+(mechanism|role|function|effect)\s+(is|remains|are)\s+(unclear|unknown|not\s+well\s+understood)",
    r"^little\s+is\s+known",
    r"^future\s+studies\s+should",
]

# ── Gap Scoring ──


def _score_gap(gap: dict[str, Any], all_gap_ids: set[str]) -> dict[str, Any]:
    """Score a single gap."""
    evidence = gap.get("based_on_evidence", []) or []
    statement = gap.get("gap_statement", "") or ""
    confidence = float(gap.get("confidence", 0.5))
    warnings = list(gap.get("warnings", []) or [])

    # --- Evidence Grounding ---
    if len(evidence) == 0:
        evidence_score = 0.1
    elif len(evidence) == 1:
        evidence_score = 0.5
    elif len(evidence) >= 3:
        evidence_score = 0.9
    else:
        evidence_score = 0.7

    # Penalize if evidence items are too short / generic
    short_evidence = sum(1 for e in evidence if len(str(e)) < 20)
    if short_evidence > 0:
        evidence_score -= 0.2 * min(short_evidence / len(evidence), 1)

    evidence_score = max(0.0, min(1.0, evidence_score))

    # --- Specificity ---
    specificity_score = 0.5
    stmt_lower = statement.lower()
    stmt_len = len(statement)

    if stmt_len < 30:
        specificity_score = 0.2
    elif stmt_len > 100:
        specificity_score = 0.8

    # Check for vague patterns
    for pattern in VAGUE_GAP_PATTERNS:
        if re.search(pattern, stmt_lower):
            specificity_score -= 0.3
            break

    # Bonus for specific entities (gene names, pathway names)
    if re.search(r"\b[A-Z][a-z]{2,}[A-Z0-9]+\b", statement):  # Likely protein/gene name
        specificity_score += 0.15
    if re.search(r"\b(pathway|signaling|cascade|axis)\b", stmt_lower):
        specificity_score += 0.1

    specificity_score = max(0.0, min(1.0, specificity_score))

    # --- Novelty ---
    novelty_score = 0.6
    gap_type = gap.get("gap_type", "").lower()

    if gap_type == "unknown":
        novelty_score = 0.8  # Genuine open questions are novel
    elif gap_type == "mechanistic":
        novelty_score = 0.75
    elif gap_type == "contradiction":
        novelty_score = 0.85
    elif gap_type == "evidence":
        novelty_score = 0.5
    elif gap_type == "methodological":
        novelty_score = 0.4
    elif gap_type == "scope":
        novelty_score = 0.35  # Scope limitations are often acknowledged
    elif gap_type == "translation":
        novelty_score = 0.55

    # Penalize if it's just restating the paper's limitation
    missing_info = gap.get("missing_information", "") or ""
    why = gap.get("why_it_matters", "") or ""
    if len(missing_info) < 10 or len(why) < 10:
        novelty_score -= 0.2

    novelty_score = max(0.0, min(1.0, novelty_score))

    # --- Overclaim Risk ---
    # Use raw evidence_score (not weight-adjusted) for overclaim detection
    if confidence > 0.85 and evidence_score < 0.4:
        overclaim_risk = "high"
    elif confidence > 0.7 and evidence_score < 0.3:
        overclaim_risk = "high"
    elif confidence > 0.8 and evidence_score < 0.6:
        overclaim_risk = "medium"
    elif confidence > 0.7 and evidence_score < 0.5:
        overclaim_risk = "medium"
    else:
        overclaim_risk = "low"

    # --- Gap Score ---
    gap_score = (
        evidence_score * GAP_WEIGHTS["evidence_grounding"]
        + specificity_score * GAP_WEIGHTS["specificity"]
        + novelty_score * GAP_WEIGHTS["novelty"]
    )

    return {
        "gap_id": gap.get("gap_id", ""),
        "evidence_grounding_score": round(evidence_score, 3),
        "specificity_score": round(specificity_score, 3),
        "novelty_score": round(novelty_score, 3),
        "overclaim_risk": overclaim_risk,
        "weighted_score": round(gap_score, 3),
        "warnings": warnings,
    }


# ── Hypothesis Scoring ──


def _score_hypothesis(
    hyp: dict[str, Any],
    all_gap_ids: set[str],
) -> dict[str, Any]:
    """Score a single hypothesis."""
    hyp_id = hyp.get("hypothesis_id", "")
    linked_gap = hyp.get("linked_gap_id", "") or ""
    testable_pred = hyp.get("testable_prediction", "") or ""
    suggested_exp = hyp.get("suggested_experiment", "") or ""
    rationale = hyp.get("rationale", "") or ""
    supporting_evidence = hyp.get("supporting_evidence", []) or []
    confidence = float(hyp.get("confidence", 0.5))
    risk_level = hyp.get("risk_level", "medium").lower()
    warnings = list(hyp.get("warnings", []) or [])

    # --- Linked Gap Valid ---
    linked_gap_valid = linked_gap in all_gap_ids
    if not linked_gap:
        linked_gap_valid = False

    # --- Testability ---
    testability_score = 0.3
    if len(testable_pred) > 30:
        testability_score = 0.6
    if len(testable_pred) > 80:
        testability_score = 0.8
    # Check for measurable / quantifiable language
    if re.search(r"\b(increas|decreas|reduc|elevat|higher|lower|chang|alter)\b", testable_pred.lower()):
        testability_score += 0.1
    if re.search(r"\b(significant|measurable|detectable|quantif)\b", testable_pred.lower()):
        testability_score += 0.1
    testability_score = max(0.0, min(1.0, testability_score))

    # --- Rationale Grounding ---
    rationale_score = 0.3
    if len(rationale) > 30:
        rationale_score = 0.5
    if len(rationale) > 80:
        rationale_score = 0.7
    if len(supporting_evidence) >= 2:
        rationale_score += 0.15
    if len(supporting_evidence) >= 1:
        rationale_score += 0.1
    if linked_gap_valid:
        rationale_score += 0.1
    rationale_score = max(0.0, min(1.0, rationale_score))

    # --- Experiment Feasibility ---
    feasibility_score = 0.3
    if len(suggested_exp) > 40:
        feasibility_score = 0.5
    if len(suggested_exp) > 100:
        feasibility_score = 0.7
    # Method mention is good
    if re.search(r"\b(RNA-seq|RNAi|CRISPR|knockout|knockdown|overexpression|inhibitor|siRNA|shRNA|qPCR|western|ELISA|microscopy|TEM|SEM|flow\s+cytometry)\b", suggested_exp, re.IGNORECASE):
        feasibility_score += 0.15
    # Model system mention
    if re.search(r"\b(cell|mice|mouse|rat|zebrafish|drosophila|c\.\s*elegans|yeast|arabidopsis|in\s+vitro|in\s+vivo|ex\s+vivo)\b", suggested_exp.lower()):
        feasibility_score += 0.1
    feasibility_score = max(0.0, min(1.0, feasibility_score))

    # --- Over-Specificity Risk ---
    over_spec_score = 0
    for pattern in OVER_SPECIFIC_KEYWORDS:
        if re.search(pattern, suggested_exp, re.IGNORECASE):
            over_spec_score += 1

    if over_spec_score >= 2:
        over_specificity_risk = "high"
    elif over_spec_score >= 1:
        over_specificity_risk = "medium"
    else:
        over_specificity_risk = "low"

    # --- Safety / Ethics Warning ---
    safety_warnings: list[str] = []
    combined_text = f"{hyp.get('hypothesis_statement','')} {suggested_exp} {testable_pred}"
    for pattern in DANGEROUS_KEYWORDS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            safety_warnings.append(f"Potential safety/ethics concern: matches '{pattern}'")

    # --- Hypothesis Score ---
    hyp_score = (
        testability_score * HYPOTHESIS_WEIGHTS["testability"]
        + rationale_score * HYPOTHESIS_WEIGHTS["rationale_grounding"]
        + feasibility_score * HYPOTHESIS_WEIGHTS["experiment_feasibility"]
    )

    return {
        "hypothesis_id": hyp_id,
        "linked_gap_valid": linked_gap_valid,
        "testability_score": round(testability_score, 3),
        "rationale_grounding_score": round(rationale_score, 3),
        "experiment_feasibility_score": round(feasibility_score, 3),
        "over_specificity_risk": over_specificity_risk,
        "safety_or_ethics_warning": safety_warnings,
        "weighted_score": round(hyp_score, 3),
        "warnings": warnings,
    }


# ── Main Evaluation ──


def evaluate_gap_hypothesis_quality(
    paper_id: str,
    gaps_path: str | None = None,
    hypotheses_path: str | None = None,
    summary_v2_path: str | None = None,
    evidence_enrichment_path: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate quality of gap extraction and hypothesis generation outputs.

    All scoring is deterministic and rule-based. No LLM calls.

    Returns:
        dict with gap_scores, hypothesis_scores, overall_quality_score,
        and recommendation.
    """
    # Load gaps
    gaps_data = _load_json(
        gaps_path or str(PROJECT_ROOT / "03_Assets" / "ai" / "gaps" / f"{paper_id}.json")
    )
    gaps = (gaps_data or {}).get("gaps", []) or []

    # Load hypotheses
    hyp_data = _load_json(
        hypotheses_path or str(PROJECT_ROOT / "03_Assets" / "ai" / "hypotheses" / f"{paper_id}.json")
    )
    hypotheses = (hyp_data or {}).get("hypotheses", []) or []

    if not gaps and not hypotheses:
        result = {
            "paper_id": paper_id,
            "status": "insufficient_data",
            "gap_count": 0,
            "hypothesis_count": 0,
            "gap_scores": [],
            "hypothesis_scores": [],
            "overall_quality_score": 0.0,
            "recommendation": "insufficient_data",
            "warnings": ["No gaps or hypotheses found for evaluation."],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_output(paper_id, result)
        return result

    # Collect all gap IDs for linkage validation
    all_gap_ids = {g.get("gap_id", "") for g in gaps}

    # Score gaps
    gap_scores = [_score_gap(g, all_gap_ids) for g in gaps]

    # Score hypotheses
    hyp_scores = [_score_hypothesis(h, all_gap_ids) for h in hypotheses]

    # Calculate overall
    avg_gap_score = (
        sum(s["weighted_score"] for s in gap_scores) / len(gap_scores)
        if gap_scores else 1.0
    )
    avg_hyp_score = (
        sum(s["weighted_score"] for s in hyp_scores) / len(hyp_scores)
        if hyp_scores else 1.0
    )

    # Weights: gaps 40%, hypotheses 60% (hypotheses depend on gaps)
    overall = round(avg_gap_score * 0.4 + avg_hyp_score * 0.6, 3)

    # Recommendation
    invalid_links = sum(1 for s in hyp_scores if not s["linked_gap_valid"])
    high_overclaim = sum(1 for s in gap_scores if s["overclaim_risk"] == "high")
    safety_issues = sum(1 for s in hyp_scores if s["safety_or_ethics_warning"])

    if not gaps or not hypotheses:
        recommendation = "insufficient_data"
    elif overall >= 0.7 and invalid_links == 0 and high_overclaim == 0 and safety_issues == 0:
        recommendation = "accept"
    elif overall >= 0.5 and invalid_links <= 1 and high_overclaim <= 2:
        recommendation = "manual_review"
    else:
        recommendation = "reject"

    # Collect top warnings
    top_warnings: list[str] = []
    for s in gap_scores:
        if s["overclaim_risk"] == "high":
            top_warnings.append(f"Gap {s['gap_id'][-12:]}: high overclaim risk")
    for s in hyp_scores:
        if not s["linked_gap_valid"]:
            top_warnings.append(f"Hyp {s['hypothesis_id'][-12:]}: invalid linked_gap_id")
        if s["over_specificity_risk"] == "high":
            top_warnings.append(f"Hyp {s['hypothesis_id'][-12:]}: over-specific experiment")
        for sw in s["safety_or_ethics_warning"]:
            top_warnings.append(f"Hyp {s['hypothesis_id'][-12:]}: {sw[:80]}")

    result = {
        "paper_id": paper_id,
        "status": "evaluated",
        "gap_count": len(gaps),
        "hypothesis_count": len(hypotheses),
        "gap_scores": gap_scores,
        "hypothesis_scores": hyp_scores,
        "overall_quality_score": overall,
        "recommendation": recommendation,
        "metrics": {
            "invalid_linked_gap_count": invalid_links,
            "high_overclaim_risk_count": high_overclaim,
            "safety_ethics_warnings": safety_issues,
        },
        "top_warnings": top_warnings[:10],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_output(paper_id, result)
    return result


def evaluate_all_papers(limit: int = 0) -> dict[str, Any]:
    """Run quality evaluation on all papers with gaps and hypotheses.

    Args:
        limit: Max papers to evaluate (0 = all).

    Returns:
        Summary dict, also saved to OUTPUT_DIR/summary.json.
    """
    gaps_dir = PROJECT_ROOT / "03_Assets" / "ai" / "gaps"
    if not gaps_dir.exists():
        return _empty_summary()

    gap_files = sorted(gaps_dir.glob("*.json"))
    if limit > 0:
        gap_files = gap_files[:limit]

    results: list[dict[str, Any]] = []
    for gf in gap_files:
        paper_id = gf.stem
        try:
            result = evaluate_gap_hypothesis_quality(paper_id=paper_id)
            results.append(result)
        except Exception:
            results.append({
                "paper_id": paper_id,
                "status": "error",
                "recommendation": "manual_review",
            })

    if not results:
        return _empty_summary()

    accept = sum(1 for r in results if r.get("recommendation") == "accept")
    manual = sum(1 for r in results if r.get("recommendation") == "manual_review")
    reject = sum(1 for r in results if r.get("recommendation") == "reject")
    insufficient = sum(1 for r in results if r.get("recommendation") == "insufficient_data")

    avg_score = sum(r.get("overall_quality_score", 0) for r in results) / len(results)

    total_invalid_links = sum(
        r.get("metrics", {}).get("invalid_linked_gap_count", 0) for r in results
    )
    total_overclaim = sum(
        r.get("metrics", {}).get("high_overclaim_risk_count", 0) for r in results
    )

    all_warnings: list[str] = []
    for r in results:
        all_warnings.extend(r.get("top_warnings", []))

    # Deduplicate top warnings
    seen: set[str] = set()
    unique_warnings: list[str] = []
    for w in all_warnings:
        key = w[:60]
        if key not in seen:
            seen.add(key)
            unique_warnings.append(w)

    summary = {
        "total_papers": len(results),
        "accept_count": accept,
        "manual_review_count": manual,
        "reject_count": reject,
        "insufficient_data_count": insufficient,
        "average_quality_score": round(avg_score, 3),
        "invalid_linked_gap_count": total_invalid_links,
        "high_overclaim_risk_count": total_overclaim,
        "top_warnings": unique_warnings[:20],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save summary
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (OUTPUT_DIR / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    except Exception:
        pass

    return summary


def _empty_summary() -> dict[str, Any]:
    return {
        "total_papers": 0,
        "accept_count": 0,
        "manual_review_count": 0,
        "reject_count": 0,
        "insufficient_data_count": 0,
        "average_quality_score": 0.0,
        "invalid_linked_gap_count": 0,
        "high_overclaim_risk_count": 0,
        "top_warnings": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Helpers ──


def _load_json(path: str) -> dict[str, Any] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_output(paper_id: str, data: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (OUTPUT_DIR / f"{paper_id}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    except Exception:
        pass


def load_quality(paper_id: str) -> dict[str, Any] | None:
    path = OUTPUT_DIR / f"{paper_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
