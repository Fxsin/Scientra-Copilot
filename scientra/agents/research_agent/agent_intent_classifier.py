"""Agent Intent Classifier — rule-based intent detection."""

from __future__ import annotations
import re
from typing import Any

INTENTS = [
    ("dataset_question", [r"dataset", r"\.csv", r"\.xlsx", r"\.tsv", r"data file", r"data table", r"appear.*data", r"contain.*gene"]),
    ("entity_comparison_question", [r"which paper", r"across paper", r"compare", r"comparison", r"different paper", r"appear.*in which"]),
    ("claim_support_question", [r"which claim", r"weakly support", r"strongly support", r"evidence.*support", r"support.*claim", r"what.*support"]),
    ("figure_table_question", [r"figure", r"table", r"fig\.", r"fig ", r"chart", r"plot", r"graph", r"image"]),
    ("supplementary_question", [r"supplementary", r"supplement", r"appendix", r"supporting information"]),
    ("gap_question", [r"gap", r"knowledge gap", r"unknown", r"unclear", r"not known", r"missing evidence"]),
    ("hypothesis_question", [r"hypothesis", r"hypotheses", r"proposed", r"might be", r"could be", r"potential mechanism"]),
    ("research_plan_generation", [r"research plan", r"next step", r"experiment.*design", r"what.*next", r"further study", r"generate.*plan", r"what should.*do"]),
    ("method_comparison", [r"method", r"protocol", r"technique", r"assay compare", r"different method"]),
    ("literature_question", [r"what is", r"how does", r"mechanism", r"function", r"role", r"describe", r"explain"]),
    ("opportunity_question", [r"opportunit", r"future research", r"promising", r"potential.*research"]),
]


def classify(query: str) -> dict[str, Any]:
    q = query.lower()
    scores = {}
    for intent, patterns in INTENTS:
        m = sum(1 for p in patterns if re.search(p, q, re.IGNORECASE))
        if m > 0:
            scores[intent] = min(0.4 + 0.2 * m, 0.95)
    if not scores:
        return {"primary_intent": "literature_question", "confidence": 0.3}
    best = max(scores, key=scores.get)
    return {"primary_intent": best, "confidence": round(scores[best], 2)}
