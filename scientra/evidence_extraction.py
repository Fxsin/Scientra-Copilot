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

ENGINE_VERSION = "2.3.0"
EVIDENCE_VERSION = "v2.3"

# ── Section detection patterns (enhanced for PDF text) ──

SECTION_PATTERNS: dict[str, list[str]] = {
    "abstract": [
        r"\babstract\b",
    ],
    "introduction": [
        r"\bintroduction\b",
        r"\bbackground\b",
    ],
    "methods": [
        r"\bmethods?\b",
        r"\bmaterials?\s+(?:and|&)\s+methods?\b",
        r"\bexperimental\s+(?:procedures?|design|setup|section)\b",
        r"\bmethodology\b",
        r"\bstudy\s+design\b",
        r"\bdata\s+analysis\b",
        r"\bstatistical\s+analysis\b",
        r"\bexperimental\s+procedures?\b",
    ],
    "results": [
        r"\bresults?\b",
        r"\bfindings?\b",
        r"\bexperimental\s+results?\b",
        r"\bobservations?\b",
        r"\bresults?\s+(?:and|&)\s+discussion\b",
    ],
    "discussion": [
        r"\bdiscussion\b",
        r"\bresults?\s+(?:and|&)\s+discussion\b",
        r"\bgeneral\s+discussion\b",
        r"\bconclusions?\s+(?:and|&)\s+discussion\b",
    ],
    "conclusion": [
        r"\bconclusions?\b",
        r"\bconcluding\s+remarks?\b",
        r"\bsummary\b",
        r"\bconclusions?\s+(?:and|&)\s+(?:future\s+)?(?:directions?|perspectives?|outlook)\b",
    ],
}

# Combined section detection (Results and Discussion merged)
COMBINED_SECTION_MARKER = "results_and_discussion"

# Max section length to avoid memory issues
MAX_SECTION_LENGTH = 16000

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
    Split raw_text into sections using enhanced heuristic pattern matching.

    Improvements over V1:
    - Handles combined 'Results and Discussion' sections
    - Uses content-based detection when headings are unreliable
    - Increased max section length (16k chars)
    - Smarter fallback uses full text, not just body
    """
    sections: dict[str, str] = {}
    quality: dict[str, str] = {}

    if not raw_text or not raw_text.strip():
        return _empty_sections(paper_id)

    lines = raw_text.split("\n")
    current_section = "body"
    section_content: dict[str, list[str]] = {k: [] for k in list(SECTION_PATTERNS.keys()) + ["body", COMBINED_SECTION_MARKER]}
    section_content["body"] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        matched = False

        # Check for section headings (short lines matching section patterns)
        is_heading = len(stripped) < 100 and re.search(r"^(?:\d+\.?\s*)?(?:[A-Z][A-Za-z\s&]+)$", stripped)

        for section_name, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, stripped, re.IGNORECASE):
                    if is_heading or len(stripped) < 80:
                        # Check for combined "Results and Discussion"
                        if section_name == "results" and re.search(r"discussion", stripped, re.IGNORECASE):
                            current_section = COMBINED_SECTION_MARKER
                        elif section_name == "discussion" and re.search(r"results?", stripped, re.IGNORECASE):
                            current_section = COMBINED_SECTION_MARKER
                        else:
                            current_section = section_name
                        matched = True
                        break
            if matched:
                break

        if not matched:
            section_content.setdefault(current_section, []).append(stripped)

    # Build sections from collected content
    for name in list(SECTION_PATTERNS.keys()) + [COMBINED_SECTION_MARKER]:
        text = " ".join(section_content.get(name, []))
        sections[name] = text[:MAX_SECTION_LENGTH]
        quality[name] = "found" if len(text) > 80 else "missing"

    # Handle combined results_and_discussion: copy to both results and discussion
    combined_text = sections.get(COMBINED_SECTION_MARKER, "")
    if combined_text and len(combined_text) > 80:
        if quality.get("results") == "missing":
            sections["results"] = combined_text[:MAX_SECTION_LENGTH]
            quality["results"] = "combined"
        if quality.get("discussion") == "missing":
            sections["discussion"] = combined_text[:MAX_SECTION_LENGTH]
            quality["discussion"] = "combined"

    # Smart fallback: use full text for missing sections instead of just body
    body_text = " ".join(section_content.get("body", []))
    full_text_for_fallback = raw_text[:MAX_SECTION_LENGTH] if len(body_text) < 500 else body_text[:MAX_SECTION_LENGTH]

    for name in SECTION_PATTERNS:
        if quality.get(name) == "missing" and full_text_for_fallback:
            sections[name] = full_text_for_fallback[:MAX_SECTION_LENGTH]
            quality[name] = "fallback_full"

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


# ── Evidence Extractor V2.3 ──

def extract_evidence(
    sections: dict[str, Any],
    summary_text: str | None,
    metadata: dict[str, Any] | None,
    paper_id: str,
) -> dict[str, Any]:
    """Build evidence.json from sections + summary + metadata. V2.3 enhanced.

    Key improvements:
    - Multi-section fallback for key_results (Results -> Discussion -> Abstract -> full text)
    - Methods extracted from full text when Methods section is poor
    - Core findings from Conclusion/Abstract
    - Lower linking thresholds for result-discussion pairs
    """
    result: dict[str, Any] = {
        "paper_id": paper_id,
        "title": (metadata or {}).get("title", ""),
        "year": (metadata or {}).get("year"),
        "journal": (metadata or {}).get("journal", ""),
        "evidence_version": EVIDENCE_VERSION,
        "extraction_mode": "v2.3_enhanced",
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

    result["coverage"]["has_introduction"] = quality.get("introduction") in ("found", "fallback", "combined", "fallback_full")
    result["coverage"]["has_methods"] = quality.get("methods") in ("found", "fallback", "combined", "fallback_full")
    result["coverage"]["has_results"] = quality.get("results") in ("found", "fallback", "combined", "fallback_full")
    result["coverage"]["has_discussion"] = quality.get("discussion") in ("found", "fallback", "combined", "fallback_full")

    # ── Extract Methods (from Methods section + full text fallback) ──
    methods_text = secs.get("methods", "")
    if methods_text and len(methods_text) > 100:
        result["methods"] = _extract_methods_enhanced(methods_text)
    else:
        full_text = " ".join(v for v in secs.values() if isinstance(v, str) and len(v) > 100)
        if full_text:
            result["methods"] = _extract_methods_enhanced(full_text, source_label="full_text_fallback")

    # ── Extract Key Results (multi-section priority fallback) ──
    results_text = secs.get("results", "")
    extracted_kr = False

    if results_text and len(results_text) > 200:
        result["key_results"] = _extract_key_results_enhanced(results_text, "Results")
        extracted_kr = len(result["key_results"]) > 0

    if not extracted_kr:
        disc_text = secs.get("discussion", "")
        if disc_text and len(disc_text) > 200:
            result["key_results"] = _extract_key_results_enhanced(
                disc_text, "Discussion", max_results=5, require_direction=True
            )
            extracted_kr = len(result["key_results"]) > 0

    if not extracted_kr:
        abs_text = secs.get("abstract", "")
        conc_text = secs.get("conclusion", "")
        combined = " ".join([t for t in [abs_text, conc_text] if t and len(t) > 50])
        if combined and len(combined) > 50:
            result["key_results"] = _extract_key_results_enhanced(combined, "Abstract_Conclusion", max_results=4)
            extracted_kr = len(result["key_results"]) > 0

    if not extracted_kr:
        full_text = " ".join(v for v in secs.values() if isinstance(v, str) and len(v) > 100)
        if full_text:
            result["key_results"] = _extract_key_results_enhanced(full_text, "Full_text", max_results=5)
            result["fallback_used"] = True

    # ── Extract Discussion Points ──
    disc_text = secs.get("discussion", "")
    if disc_text and len(disc_text) > 200:
        result["discussion_points"] = _extract_discussion_points_enhanced(disc_text)

    # ── Extract Core Findings ──
    result["core_findings"] = _extract_core_findings(
        secs.get("conclusion", ""),
        secs.get("abstract", ""),
        disc_text,
        result["key_results"],
    )

    # ── Result-Discussion Linking ──
    result["result_discussion_links"] = _link_results_to_discussion_enhanced(
        result.get("key_results", []),
        result.get("discussion_points", []),
    )

    # ── Summary-based supplement ──
    if summary_text:
        try:
            from scientra.summary_parser import parseAISummary
            parsed = parseAISummary(summary_text)
            if parsed:
                if not result["core_findings"]:
                    for cf in (parsed.coreFindings or []):
                        if cf and len(cf) > 10:
                            result["core_findings"].append({
                                "finding": cf[:300], "section": "Summary", "quote": cf[:200], "confidence": "low"
                            })
                existing_dp = len(result["discussion_points"])
                if existing_dp < 3:
                    for ev in (parsed.evidence or []):
                        if ev and len(ev) > 10:
                            result["discussion_points"].append({
                                "point": ev[:300], "type": "interpretation", "section": "Summary",
                                "quote": ev[:200], "confidence": "low"
                            })
                for lm in (parsed.limitations or []):
                    if lm and len(lm) > 10:
                        result["limitations"].append({
                            "limitation": lm[:300], "section": "Summary", "quote": lm[:200]
                        })
                for gp in (parsed.gaps or []):
                    if gp and len(gp) > 10:
                        result["open_questions"].append({
                            "question": gp[:300], "section": "Summary", "quote": gp[:200]
                        })
                if not result["core_findings"] and not result["key_results"]:
                    result["fallback_used"] = True
        except Exception:
            if not result["core_findings"] and not result["key_results"]:
                result["fallback_used"] = True
    elif not result["key_results"] and not result["core_findings"]:
        result["fallback_used"] = True

    result["coverage"]["has_key_results"] = len(result["key_results"]) > 0
    result["coverage"]["has_discussion_points"] = len(result["discussion_points"]) > 0

    if result["fallback_used"] and not result["core_findings"] and not result["key_results"]:
        result["status"] = "partial"

    return result


# ── Enhanced Method Extraction V2.3 ──

METHOD_VOCABULARY: set[str] = {
    "assay", "analysis", "sequencing", "microscopy", "imaging", "structure",
    "structural analysis", "crystallography", "cryo-em", "cryo em",
    "modeling", "simulation", "docking", "profiling",
    "transcriptomics", "proteomics", "metabolomics",
    "screen", "screening", "survey", "comparison", "validation",
    "experiment", "expression", "purification", "binding",
    "culture", "bioassay", "electrophoresis", "western blot", "western blotting",
    "qpcr", "quantitative pcr", "pcr", "rna-seq", "rna sequencing",
    "lc-ms", "lc ms", "mass spectrometry",
    "statistical analysis", "phylogenetic analysis", "phylogeny",
    "genome sequencing", "genomic", "genomics",
    "mutagenesis", "knockout", "knockdown",
    "overexpression", "pull-down", "co-ip", "co immunoprecipitation",
    "elisa", "immunofluorescence", "flow cytometry",
    "diet-overlay", "leaf-disk", "feeding", "injection",
    "bioinformatics", "docking", "chromatography",
    "spectroscopy", "nmr", "electron microscopy",
    "recombinant", "heterologous expression", "cloning",
    "site-directed mutagenesis", "alanine scanning",
    "surface plasmon resonance", "spr", "isothermal titration calorimetry", "itc",
}

METHOD_PATTERNS: list[tuple[str, str]] = [
    (r"(\w+(?:\s+\w+){0,8})\s+(?:was|were)\s+(?:used|performed|conducted|carried\s+out|applied|employed|utilized|executed)", "experiment"),
    (r"(?:using|via|by)\s+(\w+(?:\s+\w+){0,5}(?:\s+(?:assay|analysis|method|technique|approach|protocol|procedure|system)))", "experiment"),
    (r"(?:performed|conducted|carried\s+out)\s+(?:using|with|by)\s+(\w+(?:\s+\w+){0,6})", "experiment"),
    (r"(?:measured|quantified|determined|assessed|evaluated|examined)\s+(?:using|via|by|with)\s+(\w+(?:\s+\w+){0,6})", "experiment"),
]


def _extract_methods_enhanced(text: str, source_label: str = "Methods") -> list[dict[str, Any]]:
    """Enhanced method extraction using vocabulary + pattern matching."""
    methods: list[dict[str, Any]] = []
    seen: set[str] = set()
    text_lower = text.lower()

    for method_term in sorted(METHOD_VOCABULARY, key=len, reverse=True):
        if method_term in text_lower and method_term not in seen:
            idx = text_lower.find(method_term)
            start = max(0, idx - 60)
            end = min(len(text), idx + len(method_term) + 60)
            context = text[start:end].strip()
            seen.add(method_term)

            ev_type = "experiment"
            if any(w in method_term for w in ["sequencing", "seq", "genom"]): ev_type = "sequencing"
            elif any(w in method_term for w in ["microscop", "imaging", "cryo", "em ", "crystall"]): ev_type = "microscopy"
            elif any(w in method_term for w in ["model", "simulat", "dock", "bioinform"]): ev_type = "computational"
            elif any(w in method_term for w in ["statistic", "phylogen"]): ev_type = "statistical"
            elif any(w in method_term for w in ["assay", "elisa", "blot", "pcr", "qpcr", "electrophor"]): ev_type = "assay"
            elif any(w in method_term for w in ["spectro", "nmr", "chromatograph", "lc-ms", "mass spec"]): ev_type = "biochemical"
            elif any(w in method_term for w in ["mutagen", "knockout", "knockdown", "overexpress", "cloning", "recomb"]): ev_type = "genetic"

            methods.append({
                "name": method_term,
                "evidence_type": ev_type,
                "section": source_label,
                "quote": context[:200],
                "confidence": "medium",
            })

    for pattern, ev_type in METHOD_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            method_text = m.group(0).strip()
            key = method_text.lower()[:40]
            if len(method_text) > 15 and key not in seen:
                seen.add(key)
                methods.append({
                    "name": method_text[:200],
                    "evidence_type": ev_type,
                    "section": source_label,
                    "quote": method_text[:200],
                    "confidence": "low",
                })

    unique: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for m in methods:
        norm = re.sub(r'\s+', ' ', m["name"].lower().strip())[:30]
        if norm not in seen_names:
            seen_names.add(norm)
            unique.append(m)

    return unique[:12]


# ── Enhanced Key Results Extraction V2.3 ──

RESULT_INDICATOR_WORDS = {
    "show", "showed", "shown", "shows", "find", "found", "finding",
    "observe", "observed", "observation", "demonstrate", "demonstrated",
    "reveal", "revealed", "indicate", "indicated", "suggest", "suggested",
    "confirm", "confirmed", "identify", "identified", "detect", "detected",
    "discover", "discovered", "report", "reported",
}

DIRECTION_WORDS: dict[str, str] = {
    "increased": "increase", "increase": "increase", "elevated": "increase", "higher": "increase",
    "greater": "increase", "enhanced": "increase", "upregulated": "increase", "up-regulated": "increase",
    "decreased": "decrease", "decrease": "decrease", "reduced": "decrease", "lower": "decrease",
    "diminished": "decrease", "downregulated": "decrease", "down-regulated": "decrease", "suppressed": "decrease",
    "no difference": "no_change", "not significantly": "no_change", "no significant": "no_change",
    "similar": "no_change", "comparable": "no_change", "unchanged": "no_change",
    "associated": "association", "correlated": "association", "linked": "association",
    "no association": "no_association", "not associated": "no_association",
    "not correlated": "no_association",
}


def _detect_direction(sentence: str) -> str:
    s_lower = sentence.lower()
    for word, direction in sorted(DIRECTION_WORDS.items(), key=lambda x: -len(x[0])):
        if word in s_lower:
            return direction
    return "descriptive"


def _extract_key_results_enhanced(
    text: str, source_section: str, max_results: int = 8, require_direction: bool = False,
) -> list[dict[str, Any]]:
    """Enhanced key results extraction with direction/variable detection."""
    results: list[dict[str, Any]] = []
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        s = sentence.strip()
        if len(s) < 30 or len(s) > 600:
            continue

        words = set(re.findall(r'\b\w+\b', s.lower()))
        has_indicator = bool(words & RESULT_INDICATOR_WORDS)
        has_direction = any(w in s.lower() for w in DIRECTION_WORDS)

        if not has_indicator and not has_direction:
            continue
        if require_direction and not has_direction:
            continue

        direction = _detect_direction(s)

        if has_indicator and has_direction:
            confidence = "high"
        elif has_indicator:
            confidence = "medium"
        else:
            confidence = "low"

        results.append({
            "result": s[:300],
            "measured_variable": "",
            "direction": direction,
            "section": source_section,
            "quote": s[:240],
            "confidence": confidence,
            "method": "",
            "condition": "",
        })

    return results[:max_results]


# ── Enhanced Discussion Points Extraction V2.3 ──

DISCUSSION_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:suggest|indicat|imply|interpret|mean|infer|appear|seem|likely|possibly|probably|therefore|thus|hence|consequently)\b", "interpretation"),
    (r"\b(?:mechanism|pathway|mode of action|signal|signalling|cascade|interaction)\b", "mechanism"),
    (r"\b(?:compar|contrast|similar|differ|unlike|whereas|while|however)\b", "comparison"),
    (r"\b(?:limitation|limiting|caveat|caution|drawback|shortcoming|although|notably)\b", "limitation"),
    (r"\b(?:future|further|additional|more|next step|remain|needed|required|warranted)\b", "future_direction"),
    (r"\b(?:implication|significance|importance|relevance|impact|consequence)\b", "implication"),
    (r"\b(?:unclear|uncertain|unknown|not clear|not known|remains to be|ambigu)\b", "uncertainty"),
]


def _extract_discussion_points_enhanced(text: str) -> list[dict[str, Any]]:
    """Enhanced discussion point extraction with type classification."""
    points: list[dict[str, Any]] = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    seen_texts: set[str] = set()

    for sentence in sentences:
        s = sentence.strip()
        if len(s) < 30 or len(s) > 500:
            continue

        s_lower = s.lower()
        best_type = "interpretation"
        best_len = 0
        for pattern, dtype in DISCUSSION_TYPE_PATTERNS:
            matches = re.findall(pattern, s_lower)
            if len(matches) > best_len:
                best_len = len(matches)
                best_type = dtype

        key = s_lower[:60]
        if key in seen_texts:
            continue
        seen_texts.add(key)

        points.append({
            "point": s[:300],
            "type": best_type,
            "section": "Discussion",
            "quote": s[:200],
            "confidence": "medium" if best_len >= 2 else "low",
        })

    return points[:10]


# ── Core Findings Extraction V2.3 ──

CORE_FINDING_INDICATORS = [
    r"\b(?:in conclusion|in summary|taken together|overall|collectively|altogether|these results|these findings|our results|our findings|this study|the present study)\b",
    r"\b(?:we conclude|we propose|we demonstrate|we show|we have shown|we found|our data)\b",
    r"\b(?:the results demonstrate|the results show|the findings suggest|these data)\b",
]


def _extract_core_findings(
    conclusion_text: str,
    abstract_text: str,
    discussion_text: str,
    key_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract core findings (author-level conclusions) from multiple sources."""
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()

    for text, source in [(conclusion_text, "Conclusion"), (abstract_text, "Abstract")]:
        if not text or len(text) < 50:
            continue
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for i, s in enumerate(sentences):
            s = s.strip()
            if len(s) < 30 or len(s) > 500:
                continue
            is_concluding = any(re.search(pat, s, re.IGNORECASE) for pat in CORE_FINDING_INDICATORS)
            is_end = i > len(sentences) * 0.7
            if is_concluding or is_end:
                key = s.lower()[:60]
                if key not in seen:
                    seen.add(key)
                    findings.append({
                        "finding": s[:300],
                        "section": source,
                        "quote": s[:200],
                        "confidence": "medium" if is_concluding else "low",
                    })

    if len(findings) < 2:
        high_conf_kr = [kr for kr in key_results if kr.get("confidence") == "high"]
        for kr in high_conf_kr[:2]:
            key = kr["result"].lower()[:60]
            if key not in seen:
                seen.add(key)
                findings.append({
                    "finding": kr["result"][:300],
                    "section": "Results",
                    "quote": kr.get("quote", "")[:200],
                    "confidence": "medium",
                })

    return findings[:3]


# ── Enhanced Result-Discussion Linking V2.3 ──

def _link_results_to_discussion_enhanced(
    key_results: list[dict[str, Any]],
    discussion_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enhanced linking with lower threshold and better type inference."""
    links: list[dict[str, Any]] = []
    if not key_results or not discussion_points:
        return links

    for ri, result in enumerate(key_results[:8]):
        r_text = (result.get("result", "") + " " +
                  result.get("measured_variable", "") + " " +
                  result.get("quote", "")).lower()
        r_tokens = set(re.findall(r'\b\w{4,}\b', r_text))

        for di, disc in enumerate(discussion_points[:10]):
            d_text = (disc.get("point", "") + " " + disc.get("quote", "")).lower()
            d_tokens = set(re.findall(r'\b\w{4,}\b', d_text))

            if not r_tokens or not d_tokens:
                continue

            overlap = r_tokens & d_tokens
            score = len(overlap) / max(len(r_tokens | d_tokens), 1)
            if len(overlap) < 1 or score < 0.05:
                continue

            d_type = disc.get("type", "interpretation")
            link_type = "interprets"
            if d_type == "limitation":
                link_type = "limits"
            elif d_type == "future_direction":
                link_type = "extends"
            elif d_type == "uncertainty":
                link_type = "questions"
            elif d_type == "comparison":
                link_type = "extends"
            elif d_type in ("interpretation", "mechanism", "implication"):
                link_type = "interprets"

            conf = "high" if score >= 0.25 else ("medium" if score >= 0.12 else "low")

            links.append({
                "result_index": ri,
                "discussion_index": di,
                "link_type": link_type,
                "basis": f"Shared terms: {', '.join(sorted(overlap)[:5])}" if overlap else "Co-occurrence in paper",
                "confidence": conf,
            })

    links.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("confidence", "low"), 2))
    return links[:10]


if __name__ == "__main__":
    raise SystemExit(main())
