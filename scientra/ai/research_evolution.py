"""Research Evolution Analysis — deterministic field evolution (Phase 3.4).

Builds a timeline-based analysis of research field evolution using
paper metadata, summaries, evidence, gaps, hypotheses, and opportunities.

No LLM calls — all analysis is rule-based.

Output:
  05_Knowledge/research_evolution/research_evolution.json
  05_Knowledge/research_evolution/research_evolution_summary.json
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
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


DEFAULT_METADATA_DIR = str(_root() / "02_Metadata" / "yaml")
DEFAULT_SUMMARY_V2_DIR = str(_root() / "03_Assets" / "ai" / "summary_v2")
DEFAULT_GAPS_DIR = str(_root() / "03_Assets" / "ai" / "gaps")
DEFAULT_HYPOTHESES_DIR = str(_root() / "03_Assets" / "ai" / "hypotheses")
DEFAULT_GAP_CLUSTERS = str(_root() / "05_Knowledge" / "cross_paper_gaps" / "gap_clusters.json")
DEFAULT_HYP_CLUSTERS = str(_root() / "05_Knowledge" / "cross_paper_hypotheses" / "hypothesis_clusters.json")
DEFAULT_OPPORTUNITIES = str(_root() / "05_Knowledge" / "research_opportunities" / "opportunity_ranking.json")
DEFAULT_OUTPUT_DIR = str(_root() / "05_Knowledge" / "research_evolution")

# Default configuration
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "phase_mode": "auto",
    "min_papers_per_phase": 3,
    "window_years_long_span": 5,
    "window_years_short_span": 3,
    "llm_narrative_enabled": False,
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


def _load_yaml_metadata(metadata_dir: str) -> list[dict[str, Any]]:
    """Load all paper metadata from YAML files."""
    papers: list[dict[str, Any]] = []
    yaml_dir = Path(metadata_dir)
    if not yaml_dir.exists():
        return papers
    try:
        import yaml
    except Exception:
        return papers
    for path in sorted(yaml_dir.glob("*.metadata.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if doc:
                papers.append(doc)
        except Exception:
            pass
    return papers


def _extract_short_hash(paper_id: str) -> str:
    """Extract a hash suffix from a paper_id for cross-referencing.

    Handles both formats:
    - 'paper_<hash>' (YAML metadata) -> returns '<hash>'
    - '<title>_<hash>' (AI JSON files) -> returns '<hash>'
    """
    if paper_id.startswith("paper_"):
        return paper_id[6:]
    # Title-based: extract last underscore-separated segment
    parts = paper_id.rsplit("_", 1)
    if len(parts) == 2 and len(parts[1]) >= 8:
        return parts[1]
    return paper_id


def _build_paper_id_map(metadata_papers: list[dict], ai_dir: str) -> dict[str, str]:
    """Build a map from YAML paper_id (paper_<hash>) to AI paper_id (title+hash).

    Returns dict: yaml_paper_id -> ai_paper_id
    """
    ai_path = Path(ai_dir)
    if not ai_path.exists():
        return {}

    # Build hash index from AI files (filename-based paper_ids)
    ai_files = list(ai_path.glob("*.json"))
    ai_hash_map: dict[str, str] = {}  # short_hash -> ai_paper_id
    for f in ai_files:
        ai_pid = f.stem  # filename without .json is the paper_id
        h = _extract_short_hash(ai_pid)
        ai_hash_map[h] = ai_pid
        # Also index shorter prefixes
        for ln in range(8, len(h) + 1):
            if h[:ln] not in ai_hash_map:
                ai_hash_map[h[:ln]] = ai_pid

    # Match YAML papers to AI papers
    yaml_to_ai: dict[str, str] = {}
    for p in metadata_papers:
        yaml_pid = p.get("paper_id", "")
        if not yaml_pid:
            continue
        h = _extract_short_hash(yaml_pid)
        # Try exact match
        if h in ai_hash_map:
            yaml_to_ai[yaml_pid] = ai_hash_map[h]
        else:
            # Try prefix matching (AI hash contains YAML hash or vice versa)
            for ai_h, ai_pid in ai_hash_map.items():
                if h.startswith(ai_h) or ai_h.startswith(h):
                    yaml_to_ai[yaml_pid] = ai_pid
                    break

    return yaml_to_ai


# ── Phase Building ──


def _determine_phases(
    years: list[int],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Determine time phases based on year span and configuration.

    Returns list of dicts with phase_id, year_range (start, end), label.
    """
    if not years:
        return []

    min_y = min(years)
    max_y = max(years)
    span = max_y - min_y
    min_papers = config.get("min_papers_per_phase", 3)

    # Determine window size
    if config.get("phase_mode", "auto") == "auto":
        if span >= 15:
            window = config.get("window_years_long_span", 5)
        else:
            window = config.get("window_years_short_span", 3)
    else:
        window = config.get("window_years_long_span", 5)

    # Build initial phases
    phases: list[dict[str, Any]] = []
    start = min_y
    ph_idx = 0
    while start <= max_y:
        end = min(start + window - 1, max_y)
        phases.append({
            "phase_id": f"phase_{ph_idx + 1:03d}",
            "year_range": (start, end),
            "label": f"{start}-{end}",
        })
        start = end + 1
        ph_idx += 1

    # Count papers per phase and merge phases with too few papers
    year_counts = Counter(years)

    # Assign years to phases and compute paper counts
    for ph in phases:
        y_start, y_end = ph["year_range"]
        ph["paper_count"] = sum(
            count for year, count in year_counts.items()
            if y_start <= year <= y_end
        )

    # Merge phases with < min_papers
    merged: list[dict[str, Any]] = []
    i = 0
    while i < len(phases):
        current = dict(phases[i])
        # Accumulate papers
        total = current["paper_count"]
        j = i + 1
        while total < min_papers and j < len(phases):
            total += phases[j]["paper_count"]
            current["year_range"] = (
                current["year_range"][0],
                phases[j]["year_range"][1],
            )
            current["label"] = f"{current['year_range'][0]}-{current['year_range'][1]}"
            j += 1

        current["paper_count"] = total
        merged.append(current)
        i = j

    return merged


def _assign_paper_to_phase(
    year: int,
    phases: list[dict[str, Any]],
) -> str | None:
    """Assign a paper year to a phase_id."""
    for ph in phases:
        y_start, y_end = ph["year_range"]
        if y_start <= year <= y_end:
            return ph["phase_id"]
    return None


# ── Topic/Method/Entity Extraction ──


_TOPIC_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "shall", "this", "that", "these", "those", "it", "its", "from",
    "by", "as", "into", "through", "during", "before", "after", "between",
    "against", "not", "without", "onto", "among", "via",
    "study", "studies", "paper", "papers", "research", "result", "results",
    "finding", "findings", "evidence", "method", "methods", "data", "analysis",
    "effect", "effects", "role", "roles", "response", "responses",
    "gene", "genes", "protein", "proteins", "expression", "activity",
    "using", "based", "novel", "current", "new", "two", "one", "also",
    "found", "show", "shown", "report", "reported", "used", "use",
    "et", "al", "doi", "approach", "important", "various", "different", "many",
}


def _extract_keywords(texts: list[str], top_n: int = 10) -> list[str]:
    """Extract meaningful keywords from a list of text snippets."""
    freq: Counter = Counter()
    for text in texts:
        if not text:
            continue
        cleaned = text.lower()
        cleaned = cleaned.replace("{", " ").replace("}", " ").replace("[", " ").replace("]", " ")
        cleaned = cleaned.replace('"', " ").replace("'", " ").replace("`", " ")
        words = cleaned.replace(",", " ").replace(".", " ").replace(":", " ").replace(";", " ")
        words = words.replace("(", " ").replace(")", " ").replace("-", " ").replace("/", " ").split()
        for w in words:
            w = w.strip()
            if len(w) < 4 or w in _TOPIC_STOPWORDS or w.isdigit():
                continue
            freq[w] += 1
    return [w for w, _ in freq.most_common(top_n)]


# ── Gap Evolution ──


def _analyze_gap_evolution(
    gap_clusters: list[dict],
    paper_year_map: dict[str, int],
    phases: list[dict[str, Any]],
    opportunities: list[dict],
) -> list[dict]:
    """Add temporal evolution analysis to gap clusters."""
    # Build opportunity index by gap cluster
    opp_by_gap: dict[str, list[dict]] = defaultdict(list)
    for opp in opportunities:
        gc_id = opp.get("linked_gap_cluster_id", "")
        if gc_id:
            opp_by_gap[gc_id].append(opp)

    results: list[dict] = []
    for gc in gap_clusters:
        gc_id = gc.get("cluster_id", "")
        paper_ids = gc.get("paper_ids", [])

        # Collect years for papers in this cluster
        cluster_years: list[int] = []
        for pid in paper_ids:
            y = paper_year_map.get(pid)
            if y:
                # Also try hash-based matching
                short_h = _extract_short_hash(pid)
                for map_pid, map_y in paper_year_map.items():
                    if short_h in map_pid or map_pid in short_h or _extract_short_hash(map_pid) == short_h:
                        y = map_y
                        break
            if y:
                cluster_years.append(y)

        if not cluster_years:
            results.append({
                **gc,
                "first_seen_year": 0,
                "last_seen_year": 0,
                "active_year_span": 0,
                "paper_count_by_phase": {},
                "trend": "unknown",
                "persistence_score": 0.0,
                "closure_signal": "unknown",
                "related_opportunities": [],
            })
            continue

        first_year = min(cluster_years)
        last_year = max(cluster_years)
        year_span = last_year - first_year

        # Paper count by phase
        paper_count_by_phase: dict[str, int] = {}
        for y in cluster_years:
            ph_id = _assign_paper_to_phase(y, phases)
            if ph_id:
                paper_count_by_phase[ph_id] = paper_count_by_phase.get(ph_id, 0) + 1

        # Determine trend
        phase_ids = sorted(paper_count_by_phase.keys())
        if not phase_ids:
            trend = "unknown"
            persistence = 0.0
        else:
            first_phase = phase_ids[0]
            last_phase = phase_ids[-1]
            first_count = paper_count_by_phase.get(first_phase, 0)
            last_count = paper_count_by_phase.get(last_phase, 0)
            middle_phases = phase_ids[1:-1] if len(phase_ids) > 2 else []

            # Count phases with papers
            active_phases = len(phase_ids)

            if active_phases == 1:
                trend = "single_period"
                persistence = 0.1
            elif last_count > first_count * 1.3 and last_phase == phases[-1]["phase_id"] if phases else True:
                trend = "emerging"
                persistence = min(1.0, active_phases / len(phases)) if phases else 0.5
            elif first_count > last_count * 1.3 and last_phase != (phases[-1]["phase_id"] if phases else ""):
                trend = "declining"
                persistence = min(1.0, active_phases / len(phases)) if phases else 0.5
            elif active_phases >= 2:
                trend = "persistent"
                persistence = min(1.0, active_phases / len(phases)) if phases else 1.0
            else:
                trend = "unknown"
                persistence = 0.0

        # Closure signal
        closure = "open"
        if gc.get("paper_count", 0) >= 5 and trend == "declining":
            closure = "possibly_resolved"
        elif gc.get("paper_count", 0) >= 3 and trend == "persistent":
            closure = "partially_addressed"

        # Related opportunities
        related_opps = opp_by_gap.get(gc_id, [])

        results.append({
            **gc,
            "first_seen_year": first_year,
            "last_seen_year": last_year,
            "active_year_span": year_span,
            "paper_count_by_phase": paper_count_by_phase,
            "trend": trend,
            "persistence_score": round(persistence, 3),
            "closure_signal": closure,
            "related_opportunities": [
                {"opportunity_id": o.get("opportunity_id", ""),
                 "title": o.get("title", "")[:120],
                 "score": o.get("opportunity_score", 0)}
                for o in related_opps[:3]
            ],
        })

    return results


# ── Hypothesis Evolution ──


def _analyze_hypothesis_evolution(
    hypothesis_clusters: list[dict],
    paper_year_map: dict[str, int],
    phases: list[dict[str, Any]],
) -> list[dict]:
    """Add temporal evolution analysis to hypothesis clusters."""
    results: list[dict] = []
    for hc in hypothesis_clusters:
        hc_id = hc.get("hypothesis_cluster_id", "")
        paper_ids = hc.get("paper_ids", [])

        # Collect years
        cluster_years: list[int] = []
        for pid in paper_ids:
            y = paper_year_map.get(pid)
            if y:
                cluster_years.append(y)
            else:
                short_h = _extract_short_hash(pid)
                for map_pid, map_y in paper_year_map.items():
                    if short_h in map_pid or map_pid in short_h or _extract_short_hash(map_pid) == short_h:
                        cluster_years.append(map_y)
                        break

        if not cluster_years:
            results.append({
                **hc,
                "first_seen_year": 0,
                "last_seen_year": 0,
                "trend": "unknown",
                "linked_gap_cluster_id": hc.get("linked_gap_cluster_id", ""),
                "supporting_papers_by_phase": {},
                "validation_status": "proposed",
                "risk_trend": "unknown",
            })
            continue

        first_year = min(cluster_years)
        last_year = max(cluster_years)

        # Papers by phase
        papers_by_phase: dict[str, int] = {}
        for y in cluster_years:
            ph_id = _assign_paper_to_phase(y, phases)
            if ph_id:
                papers_by_phase[ph_id] = papers_by_phase.get(ph_id, 0) + 1

        # Trend
        phase_ids = sorted(papers_by_phase.keys())
        if len(phase_ids) == 1:
            trend = "single_period"
        elif len(phase_ids) >= 2:
            first_count = papers_by_phase.get(phase_ids[0], 0)
            last_count = papers_by_phase.get(phase_ids[-1], 0)
            last_phase_id = phases[-1]["phase_id"] if phases else ""
            if last_count > first_count and phase_ids[-1] == last_phase_id:
                trend = "emerging"
            elif first_count > last_count:
                trend = "declining"
            else:
                trend = "persistent"
        else:
            trend = "unknown"

        # Validation status
        paper_count = len(paper_ids)
        if paper_count >= 5 and trend == "persistent":
            validation = "repeatedly_supported"
        elif paper_count >= 2 and trend in ("emerging", "persistent"):
            validation = "partially_supported"
        else:
            validation = "proposed"

        # Risk trend from risk_level_distribution
        risk_dist = hc.get("risk_level_distribution", {})
        risk_trend = "unknown"
        if risk_dist:
            total_risk = sum(risk_dist.values()) or 1
            high_ratio = risk_dist.get("high", 0) / total_risk
            low_ratio = risk_dist.get("low", 0) / total_risk
            if high_ratio > 0.3:
                risk_trend = "increasing"
            elif low_ratio > 0.6:
                risk_trend = "decreasing"
            else:
                risk_trend = "stable"

        results.append({
            **hc,
            "first_seen_year": first_year,
            "last_seen_year": last_year,
            "trend": trend,
            "linked_gap_cluster_id": hc.get("linked_gap_cluster_id", ""),
            "supporting_papers_by_phase": papers_by_phase,
            "validation_status": validation,
            "risk_trend": risk_trend,
        })

    return results


# ── Opportunity Evolution ──


def _analyze_opportunity_evolution(
    opportunities: list[dict],
    gap_clusters: list[dict],
    paper_year_map: dict[str, int],
    phases: list[dict[str, Any]],
) -> list[dict]:
    """Add temporal dimension to research opportunities."""
    # Build gap cluster index by cluster_id
    gc_map: dict[str, dict] = {gc.get("cluster_id", ""): gc for gc in gap_clusters}

    results: list[dict] = []
    for opp in opportunities:
        gc_id = opp.get("linked_gap_cluster_id", "")
        gc = gc_map.get(gc_id, {})

        # Get years from member papers
        member_papers = gc.get("paper_ids", opp.get("member_papers", []))
        opp_years: list[int] = []
        for pid in member_papers:
            y = paper_year_map.get(pid)
            if y:
                opp_years.append(y)
            else:
                short_h = _extract_short_hash(pid)
                for map_pid, map_y in paper_year_map.items():
                    if short_h in map_pid or map_pid in short_h or _extract_short_hash(map_pid) == short_h:
                        opp_years.append(map_y)
                        break

        first_year = min(opp_years) if opp_years else 0
        latest_year = max(opp_years) if opp_years else 0

        # Trend
        if not opp_years:
            trend = "unknown"
            priority_traj = "unknown"
        elif len(opp_years) < 2:
            trend = "new"
            priority_traj = "unknown"
        else:
            # Split into halves
            mid = sorted(opp_years)[len(opp_years) // 2]
            early = [y for y in opp_years if y <= mid]
            late = [y for y in opp_years if y > mid]
            if len(late) > len(early) * 1.3:
                trend = "growing"
                priority_traj = "rising"
            elif len(early) > len(late) * 1.3:
                trend = "declining"
                priority_traj = "falling"
            elif len(set(opp_years)) >= 5:
                trend = "persistent"
                priority_traj = "stable"
            else:
                trend = "unknown"
                priority_traj = "stable"

        results.append({
            **opp,
            "first_seen_year": first_year,
            "latest_support_year": latest_year,
            "trend": trend,
            "priority_trajectory": priority_traj,
        })

    return results


# ── Main Function ──


def build_research_evolution(
    metadata_dir: str = DEFAULT_METADATA_DIR,
    summary_v2_dir: str = DEFAULT_SUMMARY_V2_DIR,
    gaps_dir: str = DEFAULT_GAPS_DIR,
    hypotheses_dir: str = DEFAULT_HYPOTHESES_DIR,
    gap_clusters_path: str = DEFAULT_GAP_CLUSTERS,
    hypothesis_clusters_path: str = DEFAULT_HYP_CLUSTERS,
    opportunities_path: str = DEFAULT_OPPORTUNITIES,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    config: dict | None = None,
) -> dict[str, Any]:
    """Build research evolution analysis.

    Computes time phases, gap/hypothesis/opportunity evolution trends,
    and generates phase-by-phase research narrative.

    Returns:
        dict with phases, gap_evolution, hypothesis_evolution,
        opportunity_evolution, summary, and metadata.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    # ── Load metadata ──
    metadata_papers = _load_yaml_metadata(metadata_dir)
    if not metadata_papers:
        return _empty_result("No metadata found")

    # Build paper year map from YAML metadata
    # Key: yaml paper_id (paper_<hash>) -> year
    yaml_year_map: dict[str, int] = {}
    for p in metadata_papers:
        pid = p.get("paper_id", "")
        year = p.get("year")
        if pid and year:
            try:
                yaml_year_map[pid] = int(year)
            except (ValueError, TypeError):
                pass

    # Build cross-reference: AI paper_id (title+hash) -> year
    # by matching hash suffixes
    paper_year_map: dict[str, int] = {}
    for yaml_pid, year in yaml_year_map.items():
        short_h = _extract_short_hash(yaml_pid)
        # Check summary_v2 dir for matching AI files
        ai_pids = _build_paper_id_map(metadata_papers, summary_v2_dir)
        ai_pid = ai_pids.get(yaml_pid, "")
        if ai_pid:
            paper_year_map[ai_pid] = year
        # Also map by hash directly
        paper_year_map[short_h] = year
        paper_year_map[yaml_pid] = year

    # Build paper info map (title, journal, core_finding, etc.)
    paper_info: dict[str, dict[str, Any]] = {}
    for yaml_pid, ai_pid in _build_paper_id_map(metadata_papers, summary_v2_dir).items():
        # Get YAML metadata
        yp = next((p for p in metadata_papers if p.get("paper_id") == yaml_pid), {})
        year = yp.get("year")
        try:
            year = int(year) if year else None
        except (ValueError, TypeError):
            year = None

        info: dict[str, Any] = {
            "paper_id": ai_pid,
            "yaml_paper_id": yaml_pid,
            "title": yp.get("title", ""),
            "year": year,
            "journal": yp.get("journal", ""),
            "core_finding": "",
            "method_summary": [],
            "main_claims": [],
            "important_entities": [],
        }

        # Load summary_v2
        sv2_path = Path(summary_v2_dir) / f"{ai_pid}.json"
        if sv2_path.exists():
            sv2 = _load_json(str(sv2_path))
            if sv2:
                info["core_finding"] = sv2.get("core_finding", "")
                info["method_summary"] = sv2.get("method_summary", [])
                claims = sv2.get("key_evidence", [])
                if isinstance(claims, list):
                    info["main_claims"] = [
                        c.get("claim", "") for c in claims[:5] if isinstance(c, dict)
                    ]

        # Load gaps count
        gaps_path = Path(gaps_dir) / f"{ai_pid}.json"
        if gaps_path.exists():
            gaps_data = _load_json(str(gaps_path))
            if gaps_data:
                info["gap_count"] = len(gaps_data.get("gaps", []))

        # Load hypotheses count
        hyps_path = Path(hypotheses_dir) / f"{ai_pid}.json"
        if hyps_path.exists():
            hyps_data = _load_json(str(hyps_path))
            if hyps_data:
                info["hypothesis_count"] = len(hyps_data.get("hypotheses", []))

        paper_info[ai_pid] = info

    # ── Load cross-paper data ──
    gc_data = _load_json(gap_clusters_path)
    hc_data = _load_json(hypothesis_clusters_path)
    opp_data = _load_json(opportunities_path)

    gap_clusters = gc_data.get("clusters", []) if gc_data else []
    hyp_clusters = hc_data.get("hypothesis_clusters", []) if hc_data else []
    opportunities = opp_data.get("opportunities", []) if opp_data else []

    # ── Determine phases ──
    all_years = [info["year"] for info in paper_info.values() if info["year"] is not None]
    phases = _determine_phases(all_years, cfg)

    # ── Build phase content ──
    phase_results: list[dict[str, Any]] = []
    for ph in phases:
        y_start, y_end = ph["year_range"]
        ph_papers = {
            pid: info for pid, info in paper_info.items()
            if info["year"] and y_start <= info["year"] <= y_end
        }

        # Representative papers (prefer those with core_finding)
        scored = sorted(
            ph_papers.items(),
            key=lambda kv: (
                len(kv[1].get("core_finding", "")) > 0,
                len(kv[1].get("main_claims", [])),
            ),
            reverse=True,
        )
        rep_papers = [
            {"paper_id": pid, "title": info["title"][:150], "year": info["year"],
             "journal": info.get("journal", ""), "core_finding": info.get("core_finding", "")[:200]}
            for pid, info in scored[:5]
        ]

        # Dominant topics from titles + core_findings
        all_texts: list[str] = []
        for info in ph_papers.values():
            all_texts.append(info.get("title", ""))
            all_texts.append(info.get("core_finding", ""))
        dominant_topics = _extract_keywords(all_texts, top_n=10)

        # Dominant methods
        all_methods: list[str] = []
        for info in ph_papers.values():
            methods = info.get("method_summary", [])
            if isinstance(methods, list):
                all_methods.extend(methods)
        dominant_methods = _extract_keywords(all_methods, top_n=8)

        # Dominant entities (from claims)
        all_claims: list[str] = []
        for info in ph_papers.values():
            claims = info.get("main_claims", [])
            if isinstance(claims, list):
                all_claims.extend(claims)
        dominant_entities = _extract_keywords(all_claims, top_n=8)

        # Core findings for this phase
        core_findings = [
            info.get("core_finding", "")[:200]
            for info in ph_papers.values()
            if info.get("core_finding")
        ][:5]

        # Gaps and hypotheses from clusters that involve papers in this phase
        # (will be enriched after gap/hyp evolution analysis)

        phase_results.append({
            "phase_id": ph["phase_id"],
            "year_range": f"{y_start}-{y_end}",
            "paper_count": len(ph_papers),
            "representative_papers": rep_papers,
            "dominant_topics": dominant_topics,
            "dominant_methods": dominant_methods,
            "dominant_entities": dominant_entities,
            "core_findings": core_findings,
            "emerging_gaps": [],
            "persistent_gaps": [],
            "emerging_hypotheses": [],
            "resolved_or_declining_topics": [],
            "opportunity_signals": [],
            "phase_summary": "",
        })

    # ── Gap Evolution ──
    gap_evolution = _analyze_gap_evolution(
        gap_clusters, paper_year_map, phases, opportunities,
    )

    # ── Hypothesis Evolution ──
    hypothesis_evolution = _analyze_hypothesis_evolution(
        hyp_clusters, paper_year_map, phases,
    )

    # ── Opportunity Evolution ──
    opportunity_evolution = _analyze_opportunity_evolution(
        opportunities, gap_clusters, paper_year_map, phases,
    )

    # ── Enrich phases with gap/hypothesis/opportunity info ──
    for ph in phase_results:
        ph_id = ph["phase_id"]

        # Emerging gaps: appear in this phase, growing
        ph["emerging_gaps"] = [
            {"cluster_id": g["cluster_id"], "title": g.get("unified_gap_statement", "")[:150],
             "trend": g["trend"], "paper_count": g.get("paper_count", 0)}
            for g in gap_evolution
            if g["trend"] == "emerging" and ph_id in g.get("paper_count_by_phase", {})
        ][:5]

        # Persistent gaps: cross multiple phases
        ph["persistent_gaps"] = [
            {"cluster_id": g["cluster_id"], "title": g.get("unified_gap_statement", "")[:150],
             "trend": g["trend"], "paper_count": g.get("paper_count", 0)}
            for g in gap_evolution
            if g["trend"] == "persistent" and ph_id in g.get("paper_count_by_phase", {})
        ][:5]

        # Emerging hypotheses
        ph["emerging_hypotheses"] = [
            {"hypothesis_cluster_id": h["hypothesis_cluster_id"],
             "title": h.get("unified_hypothesis_statement", "")[:150],
             "trend": h["trend"]}
            for h in hypothesis_evolution
            if h["trend"] == "emerging" and ph_id in h.get("supporting_papers_by_phase", {})
        ][:5]

        # Opportunity signals: high-score opportunities
        ph["opportunity_signals"] = [
            {"opportunity_id": o["opportunity_id"], "title": o.get("title", "")[:120],
             "score": o.get("opportunity_score", 0), "trend": o["trend"]}
            for o in opportunity_evolution
            if o.get("opportunity_score", 0) >= 0.5
        ][:5]

        # Phase summary (deterministic)
        topics_str = ", ".join(ph["dominant_topics"][:4]) if ph["dominant_topics"] else "various topics"
        methods_str = ", ".join(ph["dominant_methods"][:3]) if ph["dominant_methods"] else "diverse methods"
        n_gaps = len(ph["emerging_gaps"]) + len(ph["persistent_gaps"])
        ph["phase_summary"] = (
            f"Phase {ph['year_range']}: {ph['paper_count']} papers focused on {topics_str}. "
            f"Key methods include {methods_str}. "
            f"{n_gaps} active research gaps identified."
        )

    # ── Build summary ──
    year_span = max(all_years) - min(all_years) if all_years else 0
    persistent_gaps = [g for g in gap_evolution if g["trend"] == "persistent"]
    emerging_gaps = [g for g in gap_evolution if g["trend"] == "emerging"]
    emerging_hyps = [h for h in hypothesis_evolution if h["trend"] == "emerging"]
    rising_opps = [o for o in opportunity_evolution if o["priority_trajectory"] == "rising"]

    # Top lists
    top_persistent_gaps = sorted(
        persistent_gaps, key=lambda g: -g.get("persistence_score", 0)
    )[:10]
    top_emerging_gaps = sorted(
        emerging_gaps, key=lambda g: -(g.get("paper_count_by_phase", {}).get(
            phases[-1]["phase_id"], 0) if phases else 0)
    )[:10]
    top_emerging_hyps = sorted(
        emerging_hyps, key=lambda h: -(h.get("supporting_papers_by_phase", {}).get(
            phases[-1]["phase_id"], 0) if phases else 0)
    )[:10]
    top_rising_opps = sorted(
        rising_opps, key=lambda o: -o.get("opportunity_score", 0)
    )[:10]

    # Gap trend distribution
    gap_trend_dist = Counter(g["trend"] for g in gap_evolution)
    hyp_trend_dist = Counter(h["trend"] for h in hypothesis_evolution)
    opp_trend_dist = Counter(o["trend"] for o in opportunity_evolution)

    summary = {
        "total_papers": len(paper_info),
        "year_span": year_span,
        "year_min": min(all_years) if all_years else 0,
        "year_max": max(all_years) if all_years else 0,
        "phase_count": len(phase_results),
        "phase_window_years": cfg.get("window_years_long_span", 5) if year_span >= 15 else cfg.get("window_years_short_span", 3),
        "total_gap_clusters": len(gap_evolution),
        "total_hypothesis_clusters": len(hypothesis_evolution),
        "total_opportunities": len(opportunity_evolution),
        "gap_trend_distribution": dict(gap_trend_dist),
        "hypothesis_trend_distribution": dict(hyp_trend_dist),
        "opportunity_trend_distribution": dict(opp_trend_dist),
        "top_persistent_gaps": [
            {"cluster_id": g["cluster_id"], "title": g.get("unified_gap_statement", "")[:150],
             "persistence_score": g.get("persistence_score", 0),
             "paper_count": g.get("paper_count", 0)}
            for g in top_persistent_gaps
        ],
        "top_emerging_gaps": [
            {"cluster_id": g["cluster_id"], "title": g.get("unified_gap_statement", "")[:150],
             "paper_count": g.get("paper_count", 0)}
            for g in top_emerging_gaps
        ],
        "top_emerging_hypotheses": [
            {"hypothesis_cluster_id": h["hypothesis_cluster_id"],
             "title": h.get("unified_hypothesis_statement", "")[:150]}
            for h in top_emerging_hyps
        ],
        "top_rising_opportunities": [
            {"opportunity_id": o["opportunity_id"], "title": o.get("title", "")[:120],
             "score": o.get("opportunity_score", 0)}
            for o in top_rising_opps
        ],
        "phases_overview": [
            {"phase_id": ph["phase_id"], "year_range": ph["year_range"],
             "paper_count": ph["paper_count"],
             "dominant_topics": ph["dominant_topics"][:5]}
            for ph in phase_results
        ],
    }

    # ── Build final result ──
    result = {
        "status": "generated",
        "config": cfg,
        "phases": phase_results,
        "gap_evolution": gap_evolution,
        "hypothesis_evolution": hypothesis_evolution,
        "opportunity_evolution": opportunity_evolution,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_output(Path(output_dir), result)
    return result


def _empty_result(message: str = "No data available") -> dict:
    return {
        "status": "no_data",
        "message": message,
        "phases": [],
        "gap_evolution": [],
        "hypothesis_evolution": [],
        "opportunity_evolution": [],
        "summary": {
            "total_papers": 0,
            "year_span": 0,
            "year_min": 0,
            "year_max": 0,
            "phase_count": 0,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_output(output_path: Path, result: dict) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "research_evolution.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path / "research_evolution_summary.json").write_text(
        json.dumps(result.get("summary", {}), ensure_ascii=False, indent=2), encoding="utf-8")


def load_research_evolution(output_dir: str | None = None) -> dict | None:
    path = Path(output_dir or DEFAULT_OUTPUT_DIR) / "research_evolution.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
