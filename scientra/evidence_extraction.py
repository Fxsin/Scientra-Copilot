"""
Evidence Extraction Engine V1 — Non-destructive, optional stage.

Inserted after Summary Agent, before Embedding.
Reads parsed text + summary → produces sections.json + evidence.json.
Failure does NOT block the workflow.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("evidence_extraction")
    logging.basicConfig(level=logging.INFO)

ENGINE_VERSION = "0.1.0"
EVIDENCE_VERSION = "v1"

# ── Section detection patterns ──

SECTION_PATTERNS: dict[str, list[str]] = {
    "abstract": [r"\babstract\b"],
    "introduction": [r"\bintroduction\b", r"\bbackground\b"],
    "methods": [r"\bmethods?\b", r"\bmaterials?\s+and\s+methods?\b", r"\bexperimental\s+(procedures?|design|setup)\b", r"\bmethodology\b"],
    "results": [r"\bresults?\b", r"\bfindings?\b"],
    "discussion": [r"\bdiscussion\b"],
    "conclusion": [r"\bconclusions?\b", r"\bconcluding\s+remarks?\b", r"\bsummary\b"],
}

# ── Safe write ──

def _safe_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically with temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for _ in range(3):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            import time
            time.sleep(0.3)
    tmp.replace(path)  # final attempt


# ── Section Extractor ──

def extract_sections(raw_text: str, paper_id: str) -> dict[str, Any]:
    """
    Split raw_text into sections using heuristic pattern matching.
    Returns sections.json-compatible dict.
    """
    sections: dict[str, str] = {}
    quality: dict[str, str] = {}

    if not raw_text or not raw_text.strip():
        return _empty_sections(paper_id)

    lines = raw_text.split("\n")
    current_section = "body"
    section_content: dict[str, list[str]] = {k: [] for k in SECTION_PATTERNS}
    section_content["body"] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        matched = False
        for section_name, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, stripped, re.IGNORECASE) and len(stripped) < 80:
                    current_section = section_name
                    matched = True
                    break
            if matched:
                break
        if not matched:
            section_content.setdefault(current_section, []).append(stripped)

    for name in SECTION_PATTERNS:
        text = " ".join(section_content.get(name, []))
        sections[name] = text[:12000]  # max 12k chars per section
        quality[name] = "found" if len(text) > 50 else "missing"

    # Fallback: use body text for sections not found
    body_text = " ".join(section_content.get("body", []))
    for name in SECTION_PATTERNS:
        if quality[name] == "missing" and body_text:
            sections[name] = body_text[:4000]
            quality[name] = "fallback"

    return {
        "paper_id": paper_id,
        "source": "parsed_text",
        "sections": sections,
        "section_quality": quality,
    }


def _empty_sections(paper_id: str) -> dict[str, Any]:
    return {
        "paper_id": paper_id,
        "source": "none",
        "sections": {k: "" for k in SECTION_PATTERNS},
        "section_quality": {k: "missing" for k in SECTION_PATTERNS},
    }


# ── Evidence Extractor ──

def extract_evidence(
    sections: dict[str, Any],
    summary_text: str | None,
    metadata: dict[str, Any] | None,
    paper_id: str,
) -> dict[str, Any]:
    """
    Build evidence.json from sections + summary + metadata.
    Extracts structured claims, methods, results, etc.
    """
    result: dict[str, Any] = {
        "paper_id": paper_id,
        "title": (metadata or {}).get("title", ""),
        "year": (metadata or {}).get("year"),
        "journal": (metadata or {}).get("journal", ""),
        "evidence_version": EVIDENCE_VERSION,
        "status": "success",
        "research_question": "",
        "study_objective": "",
        "research_gap": "",
        "methods": [],
        "key_results": [],
        "core_findings": [],
        "discussion_points": [],
        "limitations": [],
        "open_questions": [],
        "future_directions": [],
        "claims": [],
        "result_discussion_links": [],
        "coverage": {
            "has_introduction": False,
            "has_methods": False,
            "has_results": False,
            "has_discussion": False,
            "has_key_results": False,
            "has_discussion_points": False,
        },
        "fallback_used": False,
        "errors": [],
    }

    secs = sections.get("sections", {})
    quality = sections.get("section_quality", {})

    result["coverage"]["has_introduction"] = quality.get("introduction") in ("found", "fallback")
    result["coverage"]["has_methods"] = quality.get("methods") in ("found", "fallback")
    result["coverage"]["has_results"] = quality.get("results") in ("found", "fallback")
    result["coverage"]["has_discussion"] = quality.get("discussion") in ("found", "fallback")

    # Extract methods from Methods section
    methods_text = secs.get("methods", "")
    if methods_text and len(methods_text) > 50:
        result["methods"] = _extract_methods(methods_text)

    # Extract findings from Results section
    results_text = secs.get("results", "")
    if results_text and len(results_text) > 50:
        result["key_results"] = _extract_key_results(results_text)

    # Extract discussion points
    disc_text = secs.get("discussion", "")
    if disc_text and len(disc_text) > 50:
        result["discussion_points"] = _extract_discussion_points(disc_text)

    # ── Result-Discussion Linking (keyword overlap) ──
    result["result_discussion_links"] = _link_results_to_discussion(
        result.get("key_results", []),
        result.get("discussion_points", []),
    )

    # Fallback: use summary for core findings
    if summary_text:
        try:
            from scientra.summary_parser import parseAISummary
            parsed = parseAISummary(summary_text)
            if parsed:
                for cf in (parsed.coreFindings or []):
                    if cf and len(cf) > 10:
                        result["core_findings"].append({"finding": cf[:300], "source": "summary", "quote": cf[:200]})
                for ev in (parsed.evidence or []):
                    if ev and len(ev) > 10:
                        result["discussion_points"].append({"point": ev[:300], "type": "interpretation", "source": "summary", "quote": ev[:200]})
                for lm in (parsed.limitations or []):
                    if lm and len(lm) > 10:
                        result["limitations"].append({"limitation": lm[:300], "source": "summary", "quote": lm[:200]})
                for gp in (parsed.gaps or []):
                    if gp and len(gp) > 10:
                        result["open_questions"].append({"question": gp[:300], "source": "summary", "quote": gp[:200]})
                if not result["core_findings"]:
                    result["fallback_used"] = True
        except Exception:
            result["fallback_used"] = True
    else:
        result["fallback_used"] = True

    result["coverage"]["has_key_results"] = len(result["key_results"]) > 0
    result["coverage"]["has_discussion_points"] = len(result["discussion_points"]) > 0

    if result["fallback_used"] and not result["core_findings"]:
        result["status"] = "partial"

    return result


def _extract_methods(text: str) -> list[dict[str, Any]]:
    """Extract method mentions from text using generic pattern matching."""
    methods = []
    # Look for common method-indicating phrases
    method_indicators = [
        r"(\w+(?:\s+\w+){0,6})\s+(?:was|were)\s+(?:used|performed|conducted|carried\s+out|applied|employed|utilized)",
        r"(?:using|via|by)\s+(\w+(?:\s+\w+){0,4}(?:\s+(?:assay|analysis|method|technique|approach|protocol|procedure)))",
    ]
    seen = set()
    for pattern in method_indicators:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            method_text = m.group(0).strip()
            if len(method_text) > 10 and method_text not in seen:
                seen.add(method_text)
                methods.append({"name": method_text[:200], "section": "Methods", "quote": method_text[:200]})
    return methods[:8]


def _extract_key_results(text: str) -> list[dict[str, Any]]:
    """Extract result statements from Results section text."""
    results = []
    # Split into sentences and look for result-indicating patterns
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result_indicators = [
        r"\b(?:show(?:ed|n|s)?|found|observed|demonstrated|revealed|indicated|suggested|confirmed|identified|detected)\b",
        r"\b(?:increased|decreased|reduced|enhanced|improved|higher|lower|greater|significant)\b",
    ]
    for sentence in sentences:
        s = sentence.strip()
        if len(s) < 20 or len(s) > 500:
            continue
        is_result = any(re.search(pat, s, re.IGNORECASE) for pat in result_indicators)
        if is_result:
            results.append({"result": s[:300], "section": "Results", "quote": s[:200], "confidence": "medium"})
    return results[:8]


def _link_results_to_discussion(
    key_results: list[dict[str, Any]],
    discussion_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate result_discussion_links based on keyword overlap."""
    links: list[dict[str, Any]] = []
    if not key_results or not discussion_points:
        return links

    for ri, result in enumerate(key_results[:8]):
        r_text = (result.get("result", "") + " " + result.get("quote", "")).lower()
        r_tokens = set(r_text.replace(",", " ").replace(".", " ").split())
        r_tokens = {t for t in r_tokens if len(t) > 3}

        for di, disc in enumerate(discussion_points[:8]):
            d_text = (disc.get("point", "") + " " + disc.get("quote", "")).lower()
            d_tokens = set(d_text.replace(",", " ").replace(".", " ").split())
            d_tokens = {t for t in d_tokens if len(t) > 3}

            if not r_tokens or not d_tokens:
                continue

            overlap = r_tokens & d_tokens
            if len(overlap) < 2:
                continue

            d_type = disc.get("type", "interpretation")
            link_type = "interprets"
            if d_type == "limitation":
                link_type = "limits"
            elif d_type == "future_direction":
                link_type = "extends"
            elif d_type == "uncertainty":
                link_type = "questions"
            elif d_type in ("interpretation", "mechanism", "implication"):
                link_type = "interprets"

            score = len(overlap) / max(len(r_tokens | d_tokens), 1)
            conf = "high" if score >= 0.3 else ("medium" if score >= 0.15 else "low")

            links.append({
                "result_index": ri,
                "discussion_index": di,
                "link_type": link_type,
                "basis": f"Shared terms: {', '.join(sorted(overlap)[:5])}",
                "confidence": conf,
            })

            if len(links) >= 10:
                return links
    return links


def _extract_discussion_points(text: str) -> list[dict[str, Any]]:
    """Extract discussion/interpretation points."""
    points = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    disc_indicators = [
        r"\b(?:suggest(?:s|ed|ing)?|indicat(?:es|ed|ing)|may|might|could|possibly|likely|appears?\b|seems?\b)",
        r"\b(?:interpret|explain|hypothes[ie]s|mechanism|consistent\s+with|in\s+contrast|however|therefore|thus)\b",
    ]
    for sentence in sentences:
        s = sentence.strip()
        if len(s) < 20 or len(s) > 500:
            continue
        if any(re.search(pat, s, re.IGNORECASE) for pat in disc_indicators):
            points.append({"point": s[:300], "type": "interpretation", "section": "Discussion", "quote": s[:200], "confidence": "medium"})
    return points[:8]


# ── Main runner ──

def run_evidence_extraction(
    root: str | Path,
    force: bool = False,
    papers: list[str] | None = None,
) -> dict[str, Any]:
    """
    Main entry point for the Evidence Extraction stage.
    Returns a report dict for the workflow runner.
    """
    root = Path(root).resolve()
    evidence_dir = root / "03_Evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    metadata_dir = root / "02_Metadata"
    summary_dir = root / "03_Summary"
    raw_text_dir = summary_dir / "raw_text"

    report: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "evidence_version": EVIDENCE_VERSION,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total": 0,
        "success": 0,
        "partial": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    # Discover papers from metadata or raw text
    paper_ids = set()
    if papers:
        paper_ids = set(papers)
    else:
        if raw_text_dir.exists():
            for path in raw_text_dir.glob("*.txt"):
                paper_ids.add(path.stem)
        if metadata_dir.exists():
            yaml_dir = metadata_dir / "yaml"
            if yaml_dir.exists():
                for path in yaml_dir.glob("*.metadata.yaml"):
                    paper_ids.add(path.stem.replace(".metadata", ""))

    if not paper_ids:
        report["errors"].append("No papers found for evidence extraction")
        return report

    report["total"] = len(paper_ids)

    for pid in sorted(paper_ids):
        evidence_path = evidence_dir / pid / "evidence.json"
        if evidence_path.exists() and not force:
            report["skipped"] += 1
            continue

        try:
            # Load raw text
            raw_text = ""
            raw_path = raw_text_dir / f"{pid}.txt"
            if raw_path.exists():
                raw_text = raw_path.read_text(encoding="utf-8", errors="replace")

            # Load summary
            summary_text = None
            summary_path = summary_dir / pid / "summary.md"
            if summary_path.exists():
                summary_text = summary_path.read_text(encoding="utf-8", errors="replace")

            # Load metadata
            meta = None
            try:
                import yaml
                yaml_path = metadata_dir / "yaml" / f"{pid}.metadata.yaml"
                if yaml_path.exists():
                    meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            except Exception:
                pass

            # Extract
            sections = extract_sections(raw_text, pid)
            _safe_write_json(evidence_dir / pid / "sections.json", sections)

            evidence = extract_evidence(sections, summary_text, meta, pid)
            _safe_write_json(evidence_path, evidence)

            if evidence["status"] == "success":
                report["success"] += 1
            elif evidence["status"] == "partial":
                report["partial"] += 1
            else:
                report["failed"] += 1
                report["errors"].append(f"{pid}: {evidence.get('errors', ['unknown'])[0]}")

        except Exception as exc:
            report["failed"] += 1
            report["errors"].append(f"{pid}: {type(exc).__name__}: {exc}")
            # Write failure report
            _safe_write_json(evidence_dir / pid / "extraction_report.json", {
                "paper_id": pid,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _safe_write_json(evidence_dir / "extraction_report.json", report)

    # Write markdown report
    _write_markdown_report(evidence_dir / "extraction_report.md", report)

    return report


def _write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Evidence Extraction Report",
        "",
        f"**Engine version:** {ENGINE_VERSION}",
        f"**Evidence version:** {EVIDENCE_VERSION}",
        f"**Started:** {report.get('started_at', '')}",
        f"**Finished:** {report.get('finished_at', '')}",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total | {report['total']} |",
        f"| Success | {report['success']} |",
        f"| Partial | {report['partial']} |",
        f"| Failed | {report['failed']} |",
        f"| Skipped | {report['skipped']} |",
        "",
    ]
    if report.get("errors"):
        lines.append("## Errors")
        for err in report["errors"][:20]:
            lines.append(f"- {err}")
    path.write_text("\n".join(lines), encoding="utf-8")


# ── CLI ──

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Scientra Copilot Evidence Extraction Engine V1")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--papers", nargs="*", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    logger.info("Evidence Extraction Engine V1 started")
    report = run_evidence_extraction(args.root, force=args.force, papers=args.papers)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Total: {report['total']}")
        print(f"Success: {report['success']}  Partial: {report['partial']}  Failed: {report['failed']}  Skipped: {report['skipped']}")

    return 1 if report["failed"] > report["success"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
