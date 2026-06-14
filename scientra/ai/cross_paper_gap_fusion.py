"""Cross-Paper Gap Fusion V2 — Embedding Community Detection (Phase 3.1.1).

Uses BGE-M3 embeddings + sentence_transformers community_detection
to cluster similar research gaps across papers.

Replaces Phase 3.1 Jaccard-based clustering with semantic embedding clustering.
No LLM/API cost — all local embedding.

Reference:
  sentence_transformers.util.community_detection

Output:
  05_Knowledge/cross_paper_gaps/gap_clusters.json
  05_Knowledge/cross_paper_gaps/gap_fusion_summary.json
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ── Path configuration ──


def _detect_project_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "Config" / "llm_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
DEFAULT_GAPS_DIR = PROJECT_ROOT / "03_Assets" / "ai" / "gaps"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "05_Knowledge" / "cross_paper_gaps"

# ── Default parameters ──

DEFAULT_THRESHOLD = 0.72
DEFAULT_MIN_COMMUNITY_SIZE = 1
DEFAULT_STRONG_SUPPORT = 3
DEFAULT_ALLOW_CROSS_TYPE = False

# ── Stopwords for keyword extraction ──

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "and", "but",
    "or", "not", "no", "nor", "so", "yet", "both", "either", "neither",
    "each", "every", "all", "any", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "than", "too", "very", "just", "because",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "we", "us", "our", "you", "your", "he", "she", "his", "her", "who",
    "whom", "which", "what", "when", "where", "how", "also", "about",
    "study", "studies", "research", "paper", "data", "results", "findings",
    "role", "effect", "effects", "function", "functions", "mechanism",
    "mechanisms", "analysis", "evidence", "based", "using", "used",
    "however", "therefore", "thus", "although", "while", "whereas",
    "furthermore", "moreover", "additional", "addition", "well",
    "without", "within", "due", "lack", "limited", "remains",
    "remain", "unclear", "unknown", "needed", "required",
    "one", "two", "three", "many", "much", "still",
    "understanding", "understand", "known",
    "response", "cells", "cell", "protein", "proteins",
    "gene", "genes", "pathway", "pathways", "expression",
    "human", "humans", "model", "models", "system", "systems",
    "including", "include", "includes", "included",
    "found", "observed", "showed", "shown", "identified",
}

# ── Gap Text Builder ──


def _build_gap_text(gap: dict[str, Any]) -> str:
    """Build embedding text from gap fields."""
    parts = [
        f"{gap.get('gap_type', 'unknown')}. {gap.get('gap_statement', '')}",
        f"Missing: {gap.get('missing_information', '')}",
        f"Importance: {gap.get('why_it_matters', '')}",
    ]
    return " ".join(parts)

# ── Data Loading ──


def _load_all_gaps(gaps_dir: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load all gaps from disk. Returns (flat_gaps, papers_map)."""
    gaps_dir_path = Path(gaps_dir)
    if not gaps_dir_path.exists():
        return [], {}

    all_gaps: list[dict[str, Any]] = []
    papers_map: dict[str, Any] = {}

    for gf in sorted(gaps_dir_path.glob("*.json")):
        try:
            data = json.loads(gf.read_text(encoding="utf-8"))
        except Exception:
            continue

        paper_id = data.get("paper_id", gf.stem)
        papers_map[paper_id] = data

        for gap in data.get("gaps", []) or []:
            gap["_paper_id"] = paper_id
            gap["_quality_score"] = data.get("overall_quality_score", 0.5)
            all_gaps.append(gap)

    return all_gaps, papers_map

# ── Embedding ──


def _embed_texts(texts: list[str]) -> np.ndarray:
    """Encode texts with BGE-M3 and return normalized numpy array."""
    from scientra.embedding import BgeM3Embedder

    embedder = BgeM3Embedder(normalize_embeddings=True)
    embedder.load()
    vectors = embedder.encode(texts, batch_size=32)
    arr = np.array(vectors, dtype=np.float32)
    return arr

# ── Community Detection ──


def _detect_communities(
    embeddings: np.ndarray,
    threshold: float,
    min_community_size: int,
) -> list[list[int]]:
    """Run community detection and return list of communities (list of indices)."""
    from sentence_transformers.util import community_detection

    communities = community_detection(
        embeddings,
        threshold=threshold,
        min_community_size=min_community_size,
        batch_size=1024,
        show_progress_bar=False,
    )
    return communities

# ── Keyword Extraction ──


def _extract_keywords(text: str, max_kw: int = 15) -> list[str]:
    """Extract normalized keywords using frequency counting."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    words = [w for w in text.split() if w not in STOPWORDS and len(w) > 2]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(max_kw)]


def _collect_cluster_keywords(gap_texts: list[str], max_kw: int = 15) -> list[str]:
    """Extract keywords from all texts in a cluster."""
    combined = " ".join(gap_texts)
    return _extract_keywords(combined, max_kw)

# ── Representative Selection ──


def _select_representative(cluster_gaps: list[dict[str, Any]]) -> int:
    """Select the best representative gap from a cluster.

    Priority:
      1. Highest quality_score (_quality_score from paper's overall)
      2. Highest confidence
      3. Highest evidence grounding (if available)
    Returns the index into cluster_gaps.
    """
    scored = []
    for i, gap in enumerate(cluster_gaps):
        qs = gap.get("_quality_score", 0.5)
        conf = gap.get("confidence", 0.5)
        # evidence grounding bonus
        ev = len(gap.get("based_on_evidence", []) or [])
        ev_bonus = min(ev * 0.05, 0.2)
        score = qs * 0.4 + conf * 0.4 + ev_bonus
        scored.append((score, i))
    scored.sort(reverse=True)
    return scored[0][1]

# ── Cluster Building ──


def _build_cluster(
    cluster_id: int,
    member_indices: list[int],
    all_gaps: list[dict[str, Any]],
    all_texts: list[str],
    embeddings: np.ndarray,
) -> dict[str, Any]:
    """Build enhanced cluster output from member indices."""
    cluster_gaps = [all_gaps[i] for i in member_indices]
    paper_ids = sorted(set(g.get("_paper_id", "") for g in cluster_gaps))
    paper_count = len(paper_ids)

    # Confidence stats
    confidences = [g.get("confidence", 0) for g in cluster_gaps if g.get("confidence")]
    conf_mean = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
    conf_min = round(min(confidences), 3) if confidences else 0.0
    conf_max = round(max(confidences), 3) if confidences else 0.0

    # Support level
    if paper_count >= DEFAULT_STRONG_SUPPORT:
        support_level = "strong_multi_paper"
    elif paper_count >= 2:
        support_level = "multi_paper"
    else:
        support_level = "single_paper"

    # Representative
    rep_idx = _select_representative(cluster_gaps)
    rep_gap = cluster_gaps[rep_idx]
    rep_text = cluster_gaps[rep_idx].get("gap_statement", "")

    # Keywords from all cluster texts
    cluster_texts = [all_texts[i] for i in member_indices]
    keywords = _collect_cluster_keywords(cluster_texts)

    # Average similarity: mean cosine between central embedding (first) and all members
    central_emb = embeddings[member_indices[0]]
    avg_sim = 0.0
    if len(member_indices) > 1:
        sims = []
        for i in member_indices:
            dot = float(np.dot(central_emb, embeddings[i]))
            sims.append(dot)
        avg_sim = round(float(np.mean(sims)), 4)

    # Evidence count
    evidence_count = sum(len(g.get("based_on_evidence", []) or []) for g in cluster_gaps)

    # Gap type (majority vote within cluster)
    type_counter = Counter(g.get("gap_type", "unknown") for g in cluster_gaps)
    gap_type = type_counter.most_common(1)[0][0]

    # Merged why_it_matters
    why_merged = " | ".join(
        sorted(set(
            g.get("why_it_matters", "") for g in cluster_gaps if g.get("why_it_matters")
        ))
    )[:500]

    cluster_id_str = f"gap_cluster_v2_{cluster_id:04d}"

    return {
        "cluster_id": cluster_id_str,
        "fusion_method": "community_detection_v2",
        "representative_gap_id": rep_gap.get("gap_id", ""),
        "representative_paper_id": rep_gap.get("_paper_id", ""),
        "representative_gap": rep_text,
        "unified_gap_statement": rep_text,
        "gap_type": gap_type,
        "paper_count": paper_count,
        "member_gap_count": len(cluster_gaps),
        "member_gap_ids": [g.get("gap_id", "") for g in cluster_gaps],
        "paper_ids": paper_ids,
        "confidence_mean": conf_mean,
        "confidence_min": conf_min,
        "confidence_max": conf_max,
        "evidence_count": evidence_count,
        "support_level": support_level,
        "average_similarity": avg_sim,
        "semantic_keywords": keywords,
        "why_it_matters_merged": why_merged,
        "warnings": [],
    }

# ── Orphan handling ──


def _create_orphan_clusters(
    all_indices: set[int],
    assigned_indices: set[int],
    all_gaps: list[dict[str, Any]],
    all_texts: list[str],
    embeddings: np.ndarray,
    start_id: int,
) -> list[dict[str, Any]]:
    """Create single-member clusters for gaps not assigned to any community."""
    orphans = all_indices - assigned_indices
    clusters = []
    for idx in orphans:
        cluster = _build_cluster(
            cluster_id=start_id + len(clusters),
            member_indices=[idx],
            all_gaps=all_gaps,
            all_texts=all_texts,
            embeddings=embeddings,
        )
        clusters.append(cluster)
    return clusters

# ── Main Fusion ──


def fuse_cross_paper_gaps(
    gaps_dir: str | None = None,
    output_dir: str | None = None,
    config: dict[str, Any] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    min_community_size: int = DEFAULT_MIN_COMMUNITY_SIZE,
    allow_cross_type: bool = DEFAULT_ALLOW_CROSS_TYPE,
) -> dict[str, Any]:
    """Fuse gaps across papers using embedding community detection.

    Args:
        gaps_dir: Path to gaps directory.
        output_dir: Path to output directory.
        config: Optional config dict (unused, for API compat).
        threshold: Cosine similarity threshold (0.0-1.0). Default 0.72.
        min_community_size: Minimum community size. Default 1.
        allow_cross_type: If False, cluster within each gap_type separately.

    Returns:
        dict with clusters, summary, and metadata.
    """
    gaps_path = Path(gaps_dir or DEFAULT_GAPS_DIR)
    output_path = Path(output_dir or DEFAULT_OUTPUT_DIR)

    # Load all gaps
    all_gaps, papers_map = _load_all_gaps(str(gaps_path))

    if not all_gaps:
        result = {
            "status": "no_data",
            "fusion_method": "community_detection_v2",
            "total_gaps": 0,
            "total_papers": 0,
            "clusters": [],
            "summary": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_output(output_path, result)
        return result

    # Build texts
    all_texts = [_build_gap_text(g) for g in all_gaps]
    gap_types = [g.get("gap_type", "unknown") for g in all_gaps]
    unique_types = sorted(set(gap_types))
    all_indices = set(range(len(all_gaps)))

    # Encode all texts
    embeddings = _embed_texts(all_texts)

    # Cluster — per type or all together
    communities: list[list[int]] = []
    if allow_cross_type:
        communities = _detect_communities(embeddings, threshold, min_community_size)
    else:
        for gtype in unique_types:
            type_indices = [i for i, t in enumerate(gap_types) if t == gtype]
            if len(type_indices) < min_community_size:
                continue
            type_embeddings = embeddings[type_indices]
            try:
                type_communities = _detect_communities(
                    type_embeddings, threshold, min_community_size,
                )
            except Exception:
                type_communities = []
            # Map back to global indices
            for comm in type_communities:
                communities.append([type_indices[i] for i in comm])

    # Build clusters from communities
    clusters: list[dict[str, Any]] = []
    assigned_indices: set[int] = set()

    for comm in communities:
        if len(comm) < min_community_size:
            continue
        cluster = _build_cluster(
            cluster_id=len(clusters),
            member_indices=comm,
            all_gaps=all_gaps,
            all_texts=all_texts,
            embeddings=embeddings,
        )
        clusters.append(cluster)
        assigned_indices.update(comm)

    # Add orphan gaps as single-member clusters
    orphan_clusters = _create_orphan_clusters(
        all_indices, assigned_indices, all_gaps, all_texts, embeddings,
        start_id=len(clusters),
    )
    clusters.extend(orphan_clusters)

    # Sort by paper_count desc, then by confidence_mean desc
    clusters.sort(key=lambda c: (-c["paper_count"], -c["confidence_mean"]))

    # Statistics
    total_papers = len(papers_map)
    single = sum(1 for c in clusters if c["support_level"] == "single_paper")
    multi = sum(1 for c in clusters if c["support_level"] == "multi_paper")
    strong = sum(1 for c in clusters if c["support_level"] == "strong_multi_paper")

    type_dist = Counter(c["gap_type"] for c in clusters)
    avg_cluster_size = len(all_gaps) / len(clusters) if clusters else 0
    largest = max(len(c["member_gap_ids"]) for c in clusters) if clusters else 0

    summary = {
        "fusion_method": "community_detection_v2",
        "total_gaps": len(all_gaps),
        "total_papers": total_papers,
        "total_clusters": len(clusters),
        "single_paper_clusters": single,
        "multi_paper_clusters": multi,
        "strong_multi_paper_clusters": strong,
        "average_cluster_size": round(avg_cluster_size, 2),
        "largest_cluster_size": largest,
        "gap_type_distribution": dict(type_dist.most_common()),
        "threshold_used": threshold,
        "min_community_size_used": min_community_size,
        "allow_cross_type": allow_cross_type,
    }

    result = {
        "status": "generated",
        "fusion_method": "community_detection_v2",
        "total_gaps": len(all_gaps),
        "total_papers": total_papers,
        "total_clusters": len(clusters),
        "clusters": clusters,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_output(output_path, result)
    return result

# ── Output ──


def _save_output(output_path: Path, result: dict[str, Any]) -> None:
    output_path.mkdir(parents=True, exist_ok=True)

    clusters_file = output_path / "gap_clusters.json"
    try:
        clusters_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    except Exception:
        pass

    summary_file = output_path / "gap_fusion_summary.json"
    try:
        summary_file.write_text(
            json.dumps(result.get("summary", {}), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_cross_paper_gaps(output_dir: str | None = None) -> dict[str, Any] | None:
    """Load previously generated cross-paper gap clusters."""
    output_path = Path(output_dir or DEFAULT_OUTPUT_DIR)
    clusters_file = output_path / "gap_clusters.json"
    if not clusters_file.exists():
        return None
    try:
        return json.loads(clusters_file.read_text(encoding="utf-8"))
    except Exception:
        return None
