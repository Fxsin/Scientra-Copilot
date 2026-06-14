"""Supplementary Evidence Extractor — extract evidence items from supplementary sections.

Evidence types: method_detail, result_detail, dataset_description,
figure_description, table_description, statistical_detail, protocol_detail,
validation_detail, limitation_detail, unknown
"""

from __future__ import annotations

import re
import uuid
from typing import Any

EVIDENCE_PATTERNS: list[tuple[str, list[str]]] = [
    ("method_detail", [
        r"(?:we|the)\s+(?:used?|performed?|conducted?|carried\s+out|employed?)",
        r"(?:method|protocol|procedure|technique|assay)",
        r"(?:was|were)\s+(?:measured?|determined?|calculated?|analy[sz]ed?|assessed?)",
        r"(?:according\s+to|following|based\s+on)\s+(?:the\s+)?(?:method|protocol|manufacturer)",
    ]),
    ("result_detail", [
        r"(?:result|finding|outcome|observation)",
        r"(?:showed?|demonstrated?|revealed?|indicated?|suggested?)",
        r"(?:significantly?|markedly?|substantially?)",
        r"(?:increased?|decreased?|changed?|differed?)",
        r"(?:p\s*[<≤]\s*0\.\d+|statistically\s+significant)",
    ]),
    ("dataset_description", [
        r"(?:dataset|data\s+set|data\s+file)",
        r"(?:contains?|includes?|comprises?|consists?\s+of)",
        r"(?:columns?|variables?|fields?|attributes?)",
        r"(?:rows?|records?|observations?|samples?)",
        r"(?:\.csv|\.tsv|\.xlsx|\.txt|\.fasta|\.fastq)",
    ]),
    ("figure_description", [
        r"(?:figure|fig\.?)\s+S?\d+",
        r"(?:supplementary\s+figure|supplementary\s+fig)",
        r"(?:illustrates?|depicts?|shows?|presents?)",
        r"(?:panel|image|micrograph|photomicrograph)",
    ]),
    ("table_description", [
        r"(?:table|tab\.?)\s+S?\d+",
        r"(?:supplementary\s+table)",
        r"(?:lists?|summarizes?|presents?|shows?)",
        r"(?:row|column|header)",
    ]),
    ("statistical_detail", [
        r"(?:p\s*[<≤=>]\s*0\.\d+|p[\s_-]?value|p[\s_-]?val)",
        r"(?:fdr|q[\s_-]?value|adjusted\s+p)",
        r"(?:odds\s+ratio|hazard\s+ratio|risk\s+ratio|confidence\s+interval)",
        r"(?:t[\s_-]?test|anova|chi[\s_-]?square|mann[\s_-]?whitney|wilcoxon|kruskal)",
        r"(?:correlation|regression|linear\s+model|mixed\s+model|glm|glmm)",
    ]),
    ("protocol_detail", [
        r"(?:step\s+\d+|first|second|third|finally)",
        r"(?:incubate|wash|centrifuge|resuspend|add|mix|pipette|transfer)",
        r"(?:incubat(?:ed?|ion)\s+(?:at|for|with))",
        r"(?:concentration\s+(?:of|was)|final\s+concentration)",
        r"(?:buffer|solution|reagent|antibody|primer|enzyme)",
    ]),
    ("validation_detail", [
        r"(?:validat(?:ed?|ion)|verified?|confirmed?|authenticated?)",
        r"(?:control|standard|reference|calibration)",
        r"(?:reproducib(?:le|ility)|replicat(?:ed?|ion))",
        r"(?:quality\s+control|qc|quality\s+assessment)",
    ]),
    ("limitation_detail", [
        r"(?:limitation|caveat|caution|drawback|shortcoming)",
        r"(?:should\s+be\s+(?:interpreted|considered|noted|taken))",
        r"(?:further\s+(?:studies?|investigation|research|experiments?)\s+(?:is|are)\s+(?:needed|required|warranted))",
        r"(?:preliminary|exploratory|pilot\s+study)",
    ]),
]


def extract_evidence(
    sections: list[dict[str, Any]],
    paper_id: str = "",
    asset_id: str = "",
) -> list[dict[str, Any]]:
    """Extract evidence items from supplementary sections.

    Args:
        sections: List of section dicts from supplementary_sectioner.
        paper_id: Paper ID for traceability.
        asset_id: Asset ID for traceability.

    Returns:
        List of evidence dicts.
    """
    evidence_list: list[dict[str, Any]] = []

    for section in sections:
        section_id = section.get("section_id", "")
        text = section.get("text", "")
        if not text or len(text) < 30:
            continue

        # Split into paragraphs for evidence extraction
        paragraphs = _split_paragraphs(text)

        for para in paragraphs:
            if len(para) < 50:
                continue

            ev_type, confidence = _classify_evidence(para, section)

            ev_id = f"supp_ev_{uuid.uuid4().hex[:12]}"
            evidence_list.append({
                "evidence_id": ev_id,
                "paper_id": paper_id,
                "asset_id": asset_id,
                "section_id": section_id,
                "evidence_type": ev_type,
                "text": para[:2000],
                "related_asset_labels": _extract_asset_labels(para),
                "related_claims": _extract_claims(para),
                "confidence": round(confidence, 2),
                "grounding_source": "supplementary_section",
            })

    return evidence_list


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs."""
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if len(p.strip()) > 30]


def _classify_evidence(text: str, section: dict[str, Any]) -> tuple[str, float]:
    """Classify evidence type from text and section context."""
    text_lower = text.lower()
    section_type = section.get("section_type", "")
    best_type = "unknown"
    best_score = 0.0

    for ev_type, patterns in EVIDENCE_PATTERNS:
        matches = sum(1 for pat in patterns if re.search(pat, text_lower, re.IGNORECASE))
        if matches > 0:
            score = min(0.40 + 0.15 * matches, 0.90)
            if score > best_score:
                best_score = score
                best_type = ev_type

    # Boost based on section type
    section_boost = {
        "supplementary_methods": ("method_detail", 0.15),
        "supplementary_results": ("result_detail", 0.15),
        "dataset_description": ("dataset_description", 0.20),
        "protocol": ("protocol_detail", 0.20),
        "supplementary_figures": ("figure_description", 0.15),
        "supplementary_tables": ("table_description", 0.15),
    }
    boost_type, boost_amount = section_boost.get(section_type, ("", 0))
    if boost_type == best_type:
        best_score = min(best_score + boost_amount, 0.95)

    if best_score < 0.4:
        return ("unknown", best_score)

    return (best_type, best_score)


def _extract_asset_labels(text: str) -> list[str]:
    """Extract figure/table/dataset labels mentioned in text."""
    labels: list[str] = []
    for pat in [r"(?:Figure|Fig\.?)\s+S?\d+[A-Za-z]?",
                r"(?:Table|Tab\.?)\s+S?\d+[A-Za-z]?",
                r"(?:Dataset|Data)\s+S?\d+",
                r"Supplementary\s+(?:Fig|Table|Data)\S*"]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            labels.append(m.group(0))
    return list(dict.fromkeys(labels))[:10]


def _extract_claims(text: str) -> list[str]:
    """Extract claim-like sentences from text."""
    sentences = re.split(r"[.!?]\s+", text)
    claims = []
    for s in sentences:
        if any(kw in s.lower() for kw in ["showed", "demonstrated", "indicated", "found",
                                            "revealed", "suggested", "confirmed", "result",
                                            "observed", "identified", "detected"]):
            claims.append(s.strip()[:200])
    return claims[:5]
