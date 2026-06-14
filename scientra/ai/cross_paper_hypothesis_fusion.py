"""Cross-Paper Hypothesis Fusion — Embedding Community Detection (Phase 3.2).

Fuses hypotheses from multiple papers into unified hypothesis clusters
by linking through cross-paper gap clusters.

Uses BGE-M3 embeddings + community_detection to group similar hypotheses.
No LLM/API cost.

Output:
  05_Knowledge/cross_paper_hypotheses/hypothesis_clusters.json
  05_Knowledge/cross_paper_hypotheses/hypothesis_fusion_summary.json
  05_Knowledge/cross_paper_hypotheses/hypothesis_fusion_quality.json
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def _detect_project_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "Config" / "llm_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
DEFAULT_GAP_CLUSTERS_PATH = str(PROJECT_ROOT / "05_Knowledge" / "cross_paper_gaps" / "gap_clusters.json")
DEFAULT_HYPOTHESES_DIR = str(PROJECT_ROOT / "03_Assets" / "ai" / "hypotheses")
DEFAULT_GAPS_DIR = str(PROJECT_ROOT / "03_Assets" / "ai" / "gaps")
DEFAULT_QUALITY_DIR = str(PROJECT_ROOT / "03_Assets" / "ai" / "quality" / "gap_hypothesis")
DEFAULT_OUTPUT_DIR = str(PROJECT_ROOT / "05_Knowledge" / "cross_paper_hypotheses")

DEFAULT_THRESHOLD = 0.72
DEFAULT_MIN_COMMUNITY_SIZE = 1
DEFAULT_STRONG_SUPPORT = 3


# ── Data Loading ──


def _load_json(path: str) -> dict[str, Any] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_hypothesis_map(hypotheses_dir: str) -> dict[str, dict[str, Any]]:
    """Build a map from hypothesis_id to full hypothesis dict."""
    hyp_map: dict[str, dict[str, Any]] = {}
    hyp_dir = Path(hypotheses_dir)
    if not hyp_dir.exists():
        return hyp_map
    for f in sorted(hyp_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for h in data.get("hypotheses", []) or []:
                hid = h.get("hypothesis_id", "")
                if hid:
                    h["_paper_id"] = data.get("paper_id", "")
                    hyp_map[hid] = h
        except Exception:
            pass
    return hyp_map


def _build_quality_map(quality_dir: str) -> dict[str, dict[str, Any]]:
    """Build a map from hypothesis_id to quality score."""
    qmap: dict[str, dict[str, Any]] = {}
    qdir = Path(quality_dir)
    if not qdir.exists():
        return qmap
    for f in sorted(qdir.glob("*.json")):
        if f.name == "summary.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            paper_quality = data.get("overall_quality_score", 0.5)
            for hs in data.get("hypothesis_scores", []) or []:
                hid = hs.get("hypothesis_id", "")
                if hid:
                    qmap[hid] = {
                        "weighted_score": hs.get("weighted_score", 0.5),
                        "linked_gap_valid": hs.get("linked_gap_valid", True),
                        "testability_score": hs.get("testability_score", 0.5),
                        "over_specificity_risk": hs.get("over_specificity_risk", "low"),
                        "paper_quality_score": paper_quality,
                    }
        except Exception:
            pass
    return qmap


# ── Hypothesis Text Builder ──


def _build_hypothesis_text(hyp: dict[str, Any]) -> str:
    """Build embedding text from hypothesis fields."""
    parts = [
        hyp.get("hypothesis_statement", ""),
        hyp.get("rationale", ""),
        hyp.get("testable_prediction", ""),
        hyp.get("suggested_experiment", ""),
        f"linked_gap: {hyp.get('linked_gap_id', '')}",
    ]
    return " ".join(parts)


# ── Embedding ──


_embedder_cache: Any = None


def _embed_texts(texts: list[str]) -> np.ndarray:
    """Encode texts with BGE-M3 and return normalized numpy array."""
    global _embedder_cache
    from scientra.embedding import BgeM3Embedder

    if _embedder_cache is None:
        _embedder_cache = BgeM3Embedder(normalize_embeddings=True)
        _embedder_cache.load()
    vectors = _embedder_cache.encode(texts, batch_size=32)
    return np.array(vectors, dtype=np.float32)


# ── Community Detection ──


def _detect_communities(
    embeddings: np.ndarray, threshold: float, min_size: int,
) -> list[list[int]]:
    """Run community detection."""
    from sentence_transformers.util import community_detection

    return community_detection(
        embeddings, threshold=threshold,
        min_community_size=min_size, batch_size=1024, show_progress_bar=False,
    )


# ── Representative Selection ──


def _select_representative_hypothesis(
    hyps: list[dict[str, Any]], quality_map: dict[str, dict[str, Any]],
) -> int:
    """Select best representative hypothesis.

    Priority: quality_score high → confidence high → risk_level low → paper_count high
    """
    scored = []
    for i, h in enumerate(hyps):
        hid = h.get("hypothesis_id", "")
        q = quality_map.get(hid, {})
        qs = q.get("weighted_score", q.get("paper_quality_score", 0.5))
        conf = float(h.get("confidence", 0.5))
        risk = h.get("risk_level", "medium")
        risk_bonus = {"low": 0.2, "medium": 0.1, "high": 0.0}.get(risk, 0.1)
        score = qs * 0.35 + conf * 0.35 + risk_bonus
        scored.append((score, i))
    scored.sort(reverse=True)
    return scored[0][1]

# ── Cluster Builder ──


def _build_hypothesis_cluster(
    cluster_id: int,
    hyps: list[dict[str, Any]],
    gap_cluster: dict[str, Any],
    quality_map: dict[str, dict[str, Any]],
    member_indices: list[int],
    all_texts: list[str],
    embeddings: np.ndarray,
) -> dict[str, Any]:
    """Build a unified hypothesis cluster."""
    cluster_hyps = [hyps[i] for i in member_indices]
    paper_ids = sorted(set(h.get("_paper_id", "") for h in cluster_hyps))
    paper_count = len(paper_ids)

    # Confidence stats
    confs = [float(h.get("confidence", 0)) for h in cluster_hyps if h.get("confidence")]
    conf_mean = round(sum(confs) / len(confs), 3) if confs else 0.0

    # Risk distribution
    risk_dist: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
    for h in cluster_hyps:
        r = h.get("risk_level", "medium")
        risk_dist[r] = risk_dist.get(r, 0) + 1

    # Quality scores
    q_scores = [
        quality_map.get(h.get("hypothesis_id", ""), {}).get("weighted_score", 0.5)
        for h in cluster_hyps
    ]
    q_mean = round(sum(q_scores) / len(q_scores), 3) if q_scores else 0.0

    # Overclaim count
    overclaim = sum(
        1 for h in cluster_hyps
        if quality_map.get(h.get("hypothesis_id", ""), {}).get("over_specificity_risk") == "high"
    )

    # Representative
    rep_idx = _select_representative_hypothesis(cluster_hyps, quality_map)
    rep = cluster_hyps[rep_idx]

    # Support level
    if paper_count >= DEFAULT_STRONG_SUPPORT:
        support_level = "strong_multi_paper"
    elif paper_count >= 2:
        support_level = "multi_paper"
    else:
        support_level = "single_paper"

    # Collect predictions, experiments, evidence
    predictions = list(set(
        h.get("testable_prediction", "") for h in cluster_hyps if h.get("testable_prediction")
    ))[:5]
    experiments = list(set(
        h.get("suggested_experiment", "") for h in cluster_hyps if h.get("suggested_experiment")
    ))[:5]
    evidence = list(set(
        e for h in cluster_hyps
        for e in (h.get("supporting_evidence", []) or [])
    ))[:10]

    # Supporting gap IDs
    gap_ids = list(set(h.get("linked_gap_id", "") for h in cluster_hyps if h.get("linked_gap_id")))

    # Average similarity
    avg_sim = 0.0
    if len(member_indices) > 1:
        central = embeddings[member_indices[0]]
        sims = [float(np.dot(central, embeddings[i])) for i in member_indices]
        avg_sim = round(float(np.mean(sims)), 4)

    return {
        "hypothesis_cluster_id": f"hyp_cluster_{cluster_id:04d}",
        "linked_gap_cluster_id": gap_cluster.get("cluster_id", ""),
        "unified_hypothesis_statement": rep.get("hypothesis_statement", ""),
        "representative_hypothesis_id": rep.get("hypothesis_id", ""),
        "representative_paper_id": rep.get("_paper_id", ""),
        "member_hypothesis_ids": [h.get("hypothesis_id", "") for h in cluster_hyps],
        "paper_ids": paper_ids,
        "paper_count": paper_count,
        "gap_count": len(gap_ids),
        "supporting_gap_ids": gap_ids,
        "supporting_evidence": evidence,
        "testable_predictions": predictions,
        "suggested_experiments": experiments,
        "risk_level_distribution": risk_dist,
        "confidence_mean": conf_mean,
        "confidence_min": round(min(confs), 3) if confs else 0.0,
        "confidence_max": round(max(confs), 3) if confs else 0.0,
        "support_level": support_level,
        "quality_score_mean": q_mean,
        "overclaim_risk_count": overclaim,
        "average_similarity": avg_sim,
        "warnings": [],
    }

# ── Orphans ──


def _create_orphan_hypothesis_clusters(
    unassigned: list[int], hyps: list[dict[str, Any]],
    gap_cluster: dict[str, Any], quality_map: dict[str, dict[str, Any]],
    all_texts: list[str], embeddings: np.ndarray, start_id: int,
) -> list[dict[str, Any]]:
    """Create single-member clusters for unassigned hypotheses."""
    clusters = []
    for idx in unassigned:
        c = _build_hypothesis_cluster(
            start_id + len(clusters), hyps, gap_cluster, quality_map,
            [idx], all_texts, embeddings,
        )
        clusters.append(c)
    return clusters


# ── Quality Summary ──


def _build_quality_summary(
    clusters: list[dict[str, Any]], gap_clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build deterministic quality summary for hypothesis fusion."""
    invalid_links = 0
    high_risk = 0
    overclaim = 0
    low_conf = 0
    missing_pred = 0

    for c in clusters:
        if not c.get("linked_gap_cluster_id"):
            invalid_links += 1
        rd = c.get("risk_level_distribution", {})
        high_risk += rd.get("high", 0)
        overclaim += c.get("overclaim_risk_count", 0)
        if c.get("confidence_mean", 0) < 0.5:
            low_conf += 1
        if len(c.get("testable_predictions", []) or []) == 0:
            missing_pred += 1

    total = len(clusters)
    avg_score = (
        sum(c.get("quality_score_mean", 0) for c in clusters) / total
        if total else 0.0
    )

    if total == 0:
        recommendation = "insufficient_data"
    elif avg_score >= 0.7 and invalid_links == 0 and overclaim < total * 0.2:
        recommendation = "accept"
    elif avg_score >= 0.5 and invalid_links <= total * 0.1:
        recommendation = "manual_review"
    else:
        recommendation = "reject"

    return {
        "total_hypothesis_clusters": total,
        "invalid_gap_cluster_links": invalid_links,
        "high_risk_hypothesis_count": high_risk,
        "overclaim_risk_count": overclaim,
        "low_confidence_cluster_count": low_conf,
        "missing_testable_prediction_count": missing_pred,
        "average_quality_score": round(avg_score, 3),
        "recommendation": recommendation,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Main Fusion ──


def fuse_cross_paper_hypotheses(
    gap_clusters_path: str = DEFAULT_GAP_CLUSTERS_PATH,
    hypotheses_dir: str = DEFAULT_HYPOTHESES_DIR,
    gaps_dir: str = DEFAULT_GAPS_DIR,
    quality_dir: str = DEFAULT_QUALITY_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    config: dict[str, Any] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    min_community_size: int = DEFAULT_MIN_COMMUNITY_SIZE,
) -> dict[str, Any]:
    """Fuse hypotheses across papers, linked through gap clusters.

    Args:
        gap_clusters_path: Path to gap_clusters.json from gap fusion.
        hypotheses_dir: Directory containing hypothesis JSON files.
        gaps_dir: Directory containing gap JSON files.
        quality_dir: Directory containing quality check JSON files.
        output_dir: Output directory.
        config: Optional config dict.
        threshold: Cosine similarity threshold for community detection.
        min_community_size: Minimum community size.

    Returns:
        dict with hypothesis_clusters, summary, and quality.
    """
    # Load gap clusters
    gc_data = _load_json(gap_clusters_path)
    if not gc_data:
        return _empty_result(threshold)
    gap_clusters = gc_data.get("clusters", []) or []

    # Load hypotheses map
    hyp_map = _build_hypothesis_map(hypotheses_dir)

    # Load quality map
    quality_map = _build_quality_map(quality_dir)

    if not hyp_map or not gap_clusters:
        return _empty_result(threshold)

    # For each gap cluster, collect linked hypotheses
    all_hypothesis_clusters: list[dict[str, Any]] = []

    for gc in gap_clusters:
        member_gap_ids = set(gc.get("member_gap_ids", []) or [])

        # Find hypotheses linked to these gap IDs
        linked_hyps: list[dict[str, Any]] = []
        for hid, hyp in hyp_map.items():
            if hyp.get("linked_gap_id", "") in member_gap_ids:
                linked_hyps.append(hyp)

        if not linked_hyps:
            continue

        # Build texts and embed
        hyp_texts = [_build_hypothesis_text(h) for h in linked_hyps]

        try:
            embeddings = _embed_texts(hyp_texts)
        except Exception:
            # Fallback: create single-member clusters for all
            for i, h in enumerate(linked_hyps):
                cluster = _build_hypothesis_cluster(
                    len(all_hypothesis_clusters) + i,
                    linked_hyps, gc, quality_map, [i], hyp_texts,
                    np.random.randn(len(linked_hyps), 128).astype(np.float32),
                )
                all_hypothesis_clusters.append(cluster)
            continue

        # Cluster
        try:
            communities = _detect_communities(embeddings, threshold, min_community_size)
        except Exception:
            communities = []

        assigned: set[int] = set()
        for comm in communities:
            if len(comm) < min_community_size:
                continue
            cluster = _build_hypothesis_cluster(
                len(all_hypothesis_clusters),
                linked_hyps, gc, quality_map, comm, hyp_texts, embeddings,
            )
            all_hypothesis_clusters.append(cluster)
            assigned.update(comm)

        # Orphans
        unassigned = [i for i in range(len(linked_hyps)) if i not in assigned]
        orphans = _create_orphan_hypothesis_clusters(
            unassigned, linked_hyps, gc, quality_map, hyp_texts, embeddings,
            start_id=len(all_hypothesis_clusters),
        )
        all_hypothesis_clusters.extend(orphans)

    # Sort
    all_hypothesis_clusters.sort(
        key=lambda c: (-c["paper_count"], -c["confidence_mean"])
    )

    # Statistics
    total_hyps = len(hyp_map)
    total = len(all_hypothesis_clusters)
    multi = sum(1 for c in all_hypothesis_clusters if c["support_level"] == "multi_paper")
    strong = sum(1 for c in all_hypothesis_clusters if c["support_level"] == "strong_multi_paper")

    summary = {
        "fusion_method": "community_detection",
        "total_hypotheses": total_hyps,
        "total_hypothesis_clusters": total,
        "multi_paper_hypothesis_clusters": multi,
        "strong_multi_paper_hypothesis_clusters": strong,
        "threshold_used": threshold,
        "min_community_size_used": min_community_size,
    }

    # Quality
    quality = _build_quality_summary(all_hypothesis_clusters, gap_clusters)

    result = {
        "status": "generated",
        "fusion_method": "community_detection",
        "total_hypotheses": total_hyps,
        "total_hypothesis_clusters": total,
        "hypothesis_clusters": all_hypothesis_clusters,
        "summary": summary,
        "quality": quality,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_output(Path(output_dir), result, quality)
    return result


def _empty_result(threshold: float) -> dict[str, Any]:
    return {
        "status": "no_data",
        "fusion_method": "community_detection",
        "total_hypotheses": 0,
        "total_hypothesis_clusters": 0,
        "hypothesis_clusters": [],
        "summary": {},
        "quality": _build_quality_summary([], []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_output(output_path: Path, result: dict[str, Any], quality: dict[str, Any]) -> None:
    output_path.mkdir(parents=True, exist_ok=True)

    (output_path / "hypothesis_clusters.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (output_path / "hypothesis_fusion_summary.json").write_text(
        json.dumps(result.get("summary", {}), ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (output_path / "hypothesis_fusion_quality.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def load_cross_paper_hypotheses(output_dir: str | None = None) -> dict[str, Any] | None:
    path = Path(output_dir or DEFAULT_OUTPUT_DIR) / "hypothesis_clusters.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
