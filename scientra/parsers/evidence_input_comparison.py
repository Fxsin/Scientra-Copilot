"""
Hybrid PDF Parser — Evidence Input Comparison (P1.5).

Compares evidence extraction results between legacy raw text and hybrid
final markdown WITHOUT modifying the main pipeline.

- Does NOT write to 03_Evidence/
- Does NOT trigger embedding or LanceDB
- All outputs go to 02_Parse/reports/hybrid_validation/
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Resolvers ──

def _resolve_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[2]


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _read_text_safe(path: Path) -> str | None:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def _load_json_safe(path: Path) -> dict[str, Any] | None:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _ensure_dir(target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    return target


# ── Text Quality Metrics ──

# Characters/patterns indicating encoding issues or garbled text
# We detect garbled characters using a combination of:
# - The Unicode replacement character (U+FFFD)
# - Low control characters (U+0001-U+0008, U+000B-U+000C, U+000E-U+001F)
# - Common mojibake patterns from UTF-8/Latin-1 confusion
_GARBLED_CHARS = set(
    "�"  # Replacement character
    + "".join(chr(c) for c in list(range(1, 9)) + [0x0B, 0x0C] + list(range(0x0E, 0x20)))
)
_GARBLED_SUBSTRINGS = [
    "Ã¢", "Ã©", "Ã±", "â",
]


def _count_garbled(text: str) -> int:
    """Count garbled character occurrences in text."""
    count = 0
    for char in _GARBLED_CHARS:
        count += text.count(char)
    for substr in _GARBLED_SUBSTRINGS:
        count += text.count(substr)
    return count

# Section heading patterns for counting
_HEADING_PATTERN = re.compile(
    r"^#{1,6}\s+\S|"                           # Markdown headings
    r"^\d+(?:\.\d+)*\s+(?:[A-Z][A-Za-z\s&]+)|"  # Numbered headings
    r"^(?:[A-Z][A-Z\s]+)$",                      # ALL CAPS headings
    re.MULTILINE,
)

_FIGURE_REF_PATTERN = re.compile(
    r"!\[.*?\]\(.*?\)|"                          # Markdown image syntax
    r"\b(?:Fig(?:ure)?\.?\s*\d+|fig\.\s*\d+)",  # Figure references
    re.IGNORECASE,
)

_TABLE_REF_PATTERN = re.compile(
    r"\|.*\|.*\||"                               # Markdown table syntax
    r"\b(?:Table\.?\s*\d+|Tab\.\s*\d+)",         # Table references
    re.IGNORECASE,
)


def _compute_text_stats(text: str) -> dict[str, Any]:
    """Compute text-level statistics for comparison."""
    if not text or not text.strip():
        return {
            "text_length": 0,
            "line_count": 0,
            "heading_count": 0,
            "figure_reference_count": 0,
            "table_reference_count": 0,
            "malformed_text_ratio": 0.0,
        }

    text_length = len(text)
    lines = text.split("\n")
    line_count = len([l for l in lines if l.strip()])

    # Count headings
    heading_count = len(_HEADING_PATTERN.findall(text))

    # Count figure/table references
    figure_ref_count = len(_FIGURE_REF_PATTERN.findall(text))
    table_ref_count = len(_TABLE_REF_PATTERN.findall(text))

    # Compute malformed text ratio
    garbled_count = _count_garbled(text)
    malformed_ratio = garbled_count / max(text_length, 1)

    return {
        "text_length": text_length,
        "line_count": line_count,
        "heading_count": heading_count,
        "figure_reference_count": figure_ref_count,
        "table_reference_count": table_ref_count,
        "malformed_text_ratio": round(malformed_ratio, 6),
    }


def _compute_evidence_stats(evidence: dict[str, Any]) -> dict[str, Any]:
    """Compute evidence-level statistics from extract_evidence output."""
    key_results = evidence.get("key_results", [])
    methods = evidence.get("methods", [])
    core_findings = evidence.get("core_findings", [])
    discussion_points = evidence.get("discussion_points", [])
    limitations = evidence.get("limitations", [])
    open_questions = evidence.get("open_questions", [])

    total_evidence = len(key_results) + len(methods) + len(core_findings) + \
                     len(discussion_points) + len(limitations) + len(open_questions)

    # Average evidence text length
    all_texts: list[str] = []
    for item in key_results:
        all_texts.append(item.get("result", "") + item.get("quote", ""))
    for item in methods:
        all_texts.append(item.get("name", "") + item.get("quote", ""))
    for item in core_findings:
        all_texts.append(item.get("finding", "") + item.get("quote", ""))
    for item in discussion_points:
        all_texts.append(item.get("point", "") + item.get("quote", ""))
    for item in limitations:
        all_texts.append(item.get("limitation", "") + item.get("quote", ""))
    for item in open_questions:
        all_texts.append(item.get("question", "") + item.get("quote", ""))

    lengths = [len(t) for t in all_texts if t.strip()]
    avg_length = sum(lengths) / max(len(lengths), 1)

    # Evidence type distribution
    type_distribution = {
        "key_results": len(key_results),
        "methods": len(methods),
        "core_findings": len(core_findings),
        "discussion_points": len(discussion_points),
        "limitations": len(limitations),
        "open_questions": len(open_questions),
    }

    return {
        "total_evidence_count": total_evidence,
        "key_results_count": len(key_results),
        "methods_count": len(methods),
        "core_findings_count": len(core_findings),
        "discussion_points_count": len(discussion_points),
        "average_evidence_length": round(avg_length, 1),
        "evidence_type_distribution": type_distribution,
        "section_coverage": evidence.get("coverage", {}),
        "fallback_used": evidence.get("fallback_used", False),
    }


# ── Recommendation Logic ──

def _generate_recommendation(
    legacy_stats: dict[str, Any],
    hybrid_stats: dict[str, Any],
    hybrid_quality_score: float,
) -> str:
    """Generate a recommendation based on comparison results.

    Returns one of:
    - "use_hybrid_markdown"
    - "use_legacy_raw_text"
    - "manual_review"
    - "insufficient_data"
    """
    ls = legacy_stats
    hs = hybrid_stats
    lt = ls.get("text_stats", {})
    ht = hs.get("text_stats", {})
    le = ls.get("evidence_stats", {})
    he = hs.get("evidence_stats", {})

    # Insufficient data check
    if lt.get("text_length", 0) == 0 and ht.get("text_length", 0) == 0:
        return "insufficient_data"

    if ht.get("text_length", 0) == 0:
        return "use_legacy_raw_text"

    if lt.get("text_length", 0) == 0:
        # Only hybrid has text — check quality
        if hybrid_quality_score >= 0.6:
            return "use_hybrid_markdown"
        return "manual_review"

    # ── Quality checks ──
    checks_passed = 0
    checks_total = 5
    failure_reasons: list[str] = []

    # Check 1: text length >= 80% of legacy
    legacy_len = lt.get("text_length", 1)
    hybrid_len = ht.get("text_length", 1)
    if hybrid_len >= legacy_len * 0.8:
        checks_passed += 1
    else:
        ratio = hybrid_len / max(legacy_len, 1)
        failure_reasons.append(f"Text length {hybrid_len} < 80% of legacy {legacy_len} (ratio={ratio:.2f})")

    # Check 2: heading count > legacy
    if ht.get("heading_count", 0) >= lt.get("heading_count", 0):
        checks_passed += 1
    else:
        failure_reasons.append(
            f"Heading count {ht.get('heading_count', 0)} < legacy {lt.get('heading_count', 0)}"
        )

    # Check 3: malformed text ratio not worse than legacy
    hybrid_malformed = ht.get("malformed_text_ratio", 0)
    legacy_malformed = lt.get("malformed_text_ratio", 0)
    if hybrid_malformed <= legacy_malformed * 1.5:  # Allow 50% tolerance
        checks_passed += 1
    else:
        failure_reasons.append(
            f"Malformed ratio {hybrid_malformed:.4f} significantly worse than legacy {legacy_malformed:.4f}"
        )

    # Check 4: evidence count >= 70% of legacy
    legacy_ev = le.get("total_evidence_count", 1)
    hybrid_ev = he.get("total_evidence_count", 1)
    if hybrid_ev >= legacy_ev * 0.7:
        checks_passed += 1
    else:
        ratio = hybrid_ev / max(legacy_ev, 1)
        failure_reasons.append(f"Evidence count {hybrid_ev} < 70% of legacy {legacy_ev} (ratio={ratio:.2f})")

    # Check 5: section coverage maintained
    legacy_cov = le.get("section_coverage", {})
    hybrid_cov = he.get("section_coverage", {})
    # Check if methods and results sections are detected in hybrid
    hybrid_has_methods = hybrid_cov.get("has_methods", False)
    hybrid_has_results = hybrid_cov.get("has_results", False)
    if hybrid_has_methods and hybrid_has_results:
        checks_passed += 1
    else:
        missing = []
        if not hybrid_has_methods:
            missing.append("methods")
        if not hybrid_has_results:
            missing.append("results")
        failure_reasons.append(f"Hybrid missing sections: {missing}")

    # ── Decision ──
    if checks_passed >= 4:
        return "use_hybrid_markdown"
    elif checks_passed >= 3:
        return "manual_review"
    else:
        return "use_legacy_raw_text"


# ── Main Comparison Function ──

def compare_evidence_inputs(
    paper_id: str,
    config: dict[str, Any] | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Compare evidence extraction results between legacy and hybrid text sources.

    Runs evidence extraction on BOTH sources independently and compares:
    - Input text statistics (length, headings, figures, tables, malformed ratio)
    - Evidence extraction results (counts, types, coverage, lengths)
    - Section detection quality

    Args:
        paper_id: The paper identifier.
        config: Optional hybrid_parser config dict.
        root: Project root directory.

    Returns:
        Comparison report dict (also saved to
        02_Parse/reports/hybrid_validation/{paper_id}_evidence_input_comparison.json).
    """
    project_root = Path(root) if root else _resolve_root()

    # ── Load config ──
    if config is None:
        wf_path = project_root / "Config" / "workflow_config.yaml"
        if wf_path.exists():
            full_config = _load_yaml_safe(wf_path)
            config = full_config.get("hybrid_parser", {})
        else:
            config = {}

    report: dict[str, Any] = {
        "paper_id": paper_id,
        "comparison_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_snapshot": {
            "hybrid_parser_enabled": config.get("enabled", False),
            "prefer_hybrid_markdown_for_evidence": config.get("prefer_hybrid_markdown_for_evidence", False),
            "min_final_markdown_score_for_evidence": config.get("min_final_markdown_score_for_evidence", 0.65),
        },
        "sources": {},
        "legacy": {},
        "hybrid": {},
        "comparison": {},
        "recommendation": "insufficient_data",
        "recommendation_checks": {},
    }

    # ── Locate text sources ──
    legacy_paths = [
        project_root / "03_Summary" / "raw_text" / f"{paper_id}.txt",
        project_root / "02_Parse" / "text" / "pymupdf" / f"{paper_id}.txt",
    ]
    legacy_text: str | None = None
    legacy_source_path: str = ""
    for lp in legacy_paths:
        legacy_text = _read_text_safe(lp)
        if legacy_text:
            legacy_source_path = str(lp)
            break

    hybrid_md_path = project_root / "02_Parse" / "markdown" / "final" / f"{paper_id}.md"
    manifest_path = project_root / "02_Parse" / "reports" / "hybrid" / f"{paper_id}_parse_manifest.json"
    hybrid_text: str | None = _read_text_safe(hybrid_md_path)

    # Load parse quality score from manifest
    hybrid_quality_score = 0.0
    if manifest_path.exists():
        manifest = _load_json_safe(manifest_path)
        if manifest:
            qr = manifest.get("quality_report") or {}
            hybrid_quality_score = qr.get("overall_score", qr.get("markdown_score", 0.0))

    report["sources"] = {
        "legacy_raw_text_path": legacy_source_path,
        "legacy_raw_text_available": legacy_text is not None and len(legacy_text.strip()) > 0,
        "hybrid_final_markdown_path": str(hybrid_md_path) if hybrid_text else "",
        "hybrid_final_markdown_available": hybrid_text is not None and len(hybrid_text.strip()) > 0,
        "hybrid_parse_quality_score": hybrid_quality_score,
    }

    # ── Run extraction on legacy text ──
    if legacy_text and legacy_text.strip():
        try:
            from scientra.evidence_extraction import extract_evidence, extract_sections

            legacy_sections = extract_sections(legacy_text, paper_id)
            legacy_sections["text_source"] = "legacy_raw_text"
            legacy_sections["text_source_path"] = legacy_source_path

            legacy_evidence = extract_evidence(legacy_sections, None, {}, paper_id)
            legacy_evidence["evidence_input_source"] = "legacy_raw_text"

            legacy_text_stats = _compute_text_stats(legacy_text)
            legacy_evidence_stats = _compute_evidence_stats(legacy_evidence)

            # Section-level stats
            sec_quality = legacy_sections.get("section_quality", {})
            legacy_section_stats = {
                "section_count": sum(
                    1 for v in sec_quality.values()
                    if v in ("found", "combined", "fallback_full")
                ),
                "method_section_detected": sec_quality.get("methods") in ("found", "combined", "fallback_full"),
                "result_section_detected": sec_quality.get("results") in ("found", "combined", "fallback_full"),
                "discussion_section_detected": sec_quality.get("discussion") in ("found", "combined", "fallback_full"),
                "introduction_section_detected": sec_quality.get("introduction") in ("found", "combined", "fallback_full"),
                "abstract_section_detected": sec_quality.get("abstract") in ("found", "combined"),
            }

            report["legacy"] = {
                "text_stats": legacy_text_stats,
                "section_stats": legacy_section_stats,
                "evidence_stats": legacy_evidence_stats,
                "fallback_used": legacy_evidence.get("fallback_used", False),
                "status": "success",
            }
        except Exception as exc:
            report["legacy"] = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
    else:
        report["legacy"] = {
            "status": "skipped",
            "reason": "No legacy raw text available",
        }

    # ── Run extraction on hybrid final markdown ──
    if hybrid_text and hybrid_text.strip():
        try:
            from scientra.evidence_extraction import extract_evidence, extract_sections

            hybrid_sections = extract_sections(hybrid_text, paper_id)
            hybrid_sections["text_source"] = "hybrid_final_markdown"
            hybrid_sections["text_source_path"] = str(hybrid_md_path)

            hybrid_evidence = extract_evidence(hybrid_sections, None, {}, paper_id)
            hybrid_evidence["evidence_input_source"] = "hybrid_final_markdown"

            hybrid_text_stats = _compute_text_stats(hybrid_text)
            hybrid_evidence_stats = _compute_evidence_stats(hybrid_evidence)

            sec_quality = hybrid_sections.get("section_quality", {})
            hybrid_section_stats = {
                "section_count": sum(
                    1 for v in sec_quality.values()
                    if v in ("found", "combined", "fallback_full")
                ),
                "method_section_detected": sec_quality.get("methods") in ("found", "combined", "fallback_full"),
                "result_section_detected": sec_quality.get("results") in ("found", "combined", "fallback_full"),
                "discussion_section_detected": sec_quality.get("discussion") in ("found", "combined", "fallback_full"),
                "introduction_section_detected": sec_quality.get("introduction") in ("found", "combined", "fallback_full"),
                "abstract_section_detected": sec_quality.get("abstract") in ("found", "combined"),
            }

            report["hybrid"] = {
                "text_stats": hybrid_text_stats,
                "section_stats": hybrid_section_stats,
                "evidence_stats": hybrid_evidence_stats,
                "fallback_used": hybrid_evidence.get("fallback_used", False),
                "parse_quality_score": hybrid_quality_score,
                "status": "success",
            }
        except Exception as exc:
            report["hybrid"] = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "parse_quality_score": hybrid_quality_score,
            }
    else:
        report["hybrid"] = {
            "status": "skipped",
            "reason": "No hybrid final markdown available",
            "parse_quality_score": hybrid_quality_score,
        }

    # ── Compute comparison deltas ──
    legacy_ok = report["legacy"].get("status") == "success"
    hybrid_ok = report["hybrid"].get("status") == "success"

    if legacy_ok and hybrid_ok:
        lt = report["legacy"]["text_stats"]
        ht = report["hybrid"]["text_stats"]
        le = report["legacy"]["evidence_stats"]
        he = report["hybrid"]["evidence_stats"]
        ls = report["legacy"]["section_stats"]
        hs = report["hybrid"]["section_stats"]

        report["comparison"] = {
            "text_length_delta": ht["text_length"] - lt["text_length"],
            "text_length_ratio": round(ht["text_length"] / max(lt["text_length"], 1), 4),
            "heading_count_delta": ht["heading_count"] - lt["heading_count"],
            "malformed_text_ratio_delta": round(ht["malformed_text_ratio"] - lt["malformed_text_ratio"], 6),
            "evidence_count_delta": he["total_evidence_count"] - le["total_evidence_count"],
            "evidence_count_ratio": round(he["total_evidence_count"] / max(le["total_evidence_count"], 1), 4),
            "section_count_delta": hs["section_count"] - ls["section_count"],
            "figure_reference_delta": ht["figure_reference_count"] - lt["figure_reference_count"],
            "table_reference_delta": ht["table_reference_count"] - lt["table_reference_count"],
            "method_section_match": ls["method_section_detected"] == hs["method_section_detected"],
            "result_section_match": ls["result_section_detected"] == hs["result_section_detected"],
        }
    elif legacy_ok and not hybrid_ok:
        report["comparison"] = {
            "note": "Hybrid extraction failed or was skipped — cannot compare",
        }
    elif not legacy_ok and hybrid_ok:
        report["comparison"] = {
            "note": "Legacy extraction failed — only hybrid results available",
        }
    else:
        report["comparison"] = {
            "note": "Neither source produced results",
        }

    # ── Generate recommendation ──
    # Build a combined stats dict for the recommendation function
    legacy_for_rec = {
        "text_stats": report["legacy"].get("text_stats", {}),
        "evidence_stats": report["legacy"].get("evidence_stats", {}),
    }
    hybrid_for_rec = {
        "text_stats": report["hybrid"].get("text_stats", {}),
        "evidence_stats": report["hybrid"].get("evidence_stats", {}),
    }

    recommendation = _generate_recommendation(legacy_for_rec, hybrid_for_rec, hybrid_quality_score)
    report["recommendation"] = recommendation

    # ── Save report ──
    output_dir = _ensure_dir(project_root / "02_Parse" / "reports" / "hybrid_validation")
    report_path = output_dir / f"{paper_id}_evidence_input_comparison.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report["_report_path"] = str(report_path)

    return report


def compare_all_papers(
    config: dict[str, Any] | None = None,
    root: str | Path | None = None,
    limit: int | None = None,
    min_quality: float = 0.65,
) -> dict[str, Any]:
    """Run comparison on all papers that have both legacy and hybrid outputs.

    Args:
        config: Optional hybrid_parser config dict.
        root: Project root directory.
        limit: Max papers to compare.
        min_quality: Minimum hybrid parse quality score to include in comparison.

    Returns:
        Summary dict (also saved to
        02_Parse/reports/hybrid_validation/summary.json).
    """
    project_root = Path(root) if root else _resolve_root()

    # Discover papers with hybrid final markdown
    final_md_dir = project_root / "02_Parse" / "markdown" / "final"
    paper_ids: list[str] = []
    if final_md_dir.exists():
        for md_path in sorted(final_md_dir.glob("*.md")):
            paper_ids.append(md_path.stem)

    if limit:
        paper_ids = paper_ids[:limit]

    results: list[dict[str, Any]] = []
    recommendations: dict[str, int] = {
        "use_hybrid_markdown": 0,
        "use_legacy_raw_text": 0,
        "manual_review": 0,
        "insufficient_data": 0,
    }
    quality_scores: list[float] = []
    legacy_evidence_counts: list[int] = []
    hybrid_evidence_counts: list[int] = []
    failure_reasons: dict[str, int] = {}

    for paper_id in paper_ids:
        report = compare_evidence_inputs(paper_id=paper_id, config=config, root=project_root)
        results.append(report)

        rec = report.get("recommendation", "insufficient_data")
        recommendations[rec] = recommendations.get(rec, 0) + 1

        quality_scores.append(report.get("sources", {}).get("hybrid_parse_quality_score", 0.0))

        le = report.get("legacy", {}).get("evidence_stats", {})
        he = report.get("hybrid", {}).get("evidence_stats", {})
        legacy_evidence_counts.append(le.get("total_evidence_count", 0))
        hybrid_evidence_counts.append(he.get("total_evidence_count", 0))

        # Track failure reasons from comparison notes
        comp = report.get("comparison", {})
        note = comp.get("note", "")
        if note:
            failure_reasons[note] = failure_reasons.get(note, 0) + 1

    # Build summary
    total = len(results)
    summary: dict[str, Any] = {
        "summary_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_papers_compared": total,
        "recommendations": recommendations,
        "hybrid_recommended_pct": round(recommendations.get("use_hybrid_markdown", 0) / max(total, 1) * 100, 1),
        "legacy_recommended_pct": round(recommendations.get("use_legacy_raw_text", 0) / max(total, 1) * 100, 1),
        "manual_review_pct": round(recommendations.get("manual_review", 0) / max(total, 1) * 100, 1),
        "average_hybrid_quality_score": round(sum(quality_scores) / max(len(quality_scores), 1), 3),
        "average_legacy_evidence_count": round(sum(legacy_evidence_counts) / max(len(legacy_evidence_counts), 1), 1),
        "average_hybrid_evidence_count": round(sum(hybrid_evidence_counts) / max(len(hybrid_evidence_counts), 1), 1),
        "top_failure_reasons": dict(
            sorted(failure_reasons.items(), key=lambda x: -x[1])[:5]
        ),
        "per_paper_results": [
            {
                "paper_id": r["paper_id"],
                "recommendation": r["recommendation"],
                "report_path": r.get("_report_path", ""),
            }
            for r in results
        ],
    }

    # Save summary
    output_dir = _ensure_dir(project_root / "02_Parse" / "reports" / "hybrid_validation")
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary["_summary_path"] = str(summary_path)

    return summary
