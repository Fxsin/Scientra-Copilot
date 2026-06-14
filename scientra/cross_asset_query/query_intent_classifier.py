"""Query Intent Classifier — rule-based intent detection (no LLM required)."""

from __future__ import annotations

import re
from typing import Any

INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("claim_support_search", [
        r"which\s+(?:evidence|figure|table|data)\s+support",
        r"support(?:s|ing|ed)?\s+(?:evidence|data)",
        r"evidence\s+(?:for|of|supporting)",
        r"what\s+(?:evidence|data)\s+support",
        r"claim.*support", r"support.*claim",
    ]),
    ("figure_search", [
        r"figure", r"fig\.?\s", r"image", r"micrograph", r"western blot image",
        r"microscopy image", r"photomicrograph", r"panel",
    ]),
    ("table_search", [
        r"table", r"tabular", r"spreadsheet", r"\.xlsx", r"\.csv",
        r"column", r"row", r"header",
    ]),
    ("supplementary_search", [
        r"supplementary", r"supplement", r"supporting information",
        r"appendix", r"additional file", r"suppl",
    ]),
    ("entity_search", [
        r"gene\b", r"protein\b", r"receptor\b", r"toxin\b", r"enzyme\b",
        r"species\b", r"strain\b", r"compound\b", r"chemical\b",
        r"pathway\b", r"kinase\b", r"transcription factor",
    ]),
    ("method_search", [
        r"method", r"protocol", r"procedure", r"technique",
        r"assay\b", r"pcr\b", r"blot", r"sequencing",
        r"how\s+(?:was|is|were|are)\s+(?:measured|determined|detected)",
    ]),
    ("gap_search", [
        r"gap", r"knowledge gap", r"unknown", r"unclear",
        r"not known", r"remains?\s+(?:to be|unclear)",
        r"further\s+(?:research|study|investigation)",
    ]),
    ("hypothesis_search", [
        r"hypothesis", r"hypothes[ie]s", r"proposed mechanism",
        r"predicted", r"might be", r"could be", r"may be",
    ]),
    ("graph_neighborhood_search", [
        r"related to", r"connected to", r"linked to",
        r"neighbor(?:s|hood)?", r"graph",
    ]),
    ("bioassay_search", [
        r"lc50", r"ld50", r"ec50", r"ic50", r"bioassay",
        r"mortality", r"toxicity", r"dose.response",
    ]),
    ("expression_search", [
        r"expression", r"upregulat", r"downregulat",
        r"transcript", r"fpkm", r"rpkm", r"tpm",
        r"rna.seq", r"qpcr", r"rt.pcr",
    ]),
]


def classify_intent(query: str) -> dict[str, Any]:
    """Classify query intent using rule-based pattern matching.

    Returns dict with primary_intent, confidence, all_scores.
    """
    q = query.lower()
    scores: dict[str, float] = {}

    for intent, patterns in INTENT_PATTERNS:
        matches = sum(1 for p in patterns if re.search(p, q, re.IGNORECASE))
        if matches > 0:
            scores[intent] = min(0.4 + 0.2 * matches, 0.95)

    if not scores:
        return {"primary_intent": "evidence_search", "confidence": 0.3, "all_scores": {"evidence_search": 0.3}}

    best = max(scores, key=scores.get)
    return {
        "primary_intent": best,
        "confidence": round(scores[best], 2),
        "all_scores": {k: round(v, 2) for k, v in sorted(scores.items(), key=lambda x: -x[1])},
    }


def get_target_asset_types(intent: str) -> list[str]:
    """Get recommended asset types to query based on intent."""
    mapping = {
        "figure_search": ["figure", "evidence"],
        "table_search": ["table", "evidence"],
        "supplementary_search": ["supplementary", "evidence"],
        "entity_search": ["evidence", "graph", "table"],
        "method_search": ["evidence", "supplementary", "table"],
        "claim_support_search": ["evidence", "figure", "table", "graph"],
        "gap_search": ["gap", "hypothesis", "evidence", "graph"],
        "hypothesis_search": ["hypothesis", "gap", "evidence", "graph"],
        "graph_neighborhood_search": ["graph"],
        "bioassay_search": ["evidence", "table", "figure"],
        "expression_search": ["evidence", "table", "figure"],
        "evidence_search": ["evidence", "figure", "table", "supplementary"],
    }
    return mapping.get(intent, ["evidence", "figure", "table", "supplementary", "graph"])
