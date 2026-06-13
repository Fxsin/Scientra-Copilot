"""
Entity Query Parser — lightweight rule-based parser for supplementary entity queries.

Phase 2F-A: Extracts entity query terms and types from user questions.
No LLM. No OCR. No API keys. No external calls.
"""

from __future__ import annotations

import re
from typing import Any

# Known entity-like patterns (domain-agnostic)
ENTITY_PATTERN = re.compile(
    # All-uppercase identifiers: MAP2K4, CASP3, NONEXISTENT_GENE_XYZ
    r'\b([A-Z][A-Z0-9]{1,15}(?:_[A-Z][A-Z0-9]{1,15})*)\b'
    r'|'
    # Mixed-case identifiers: HtrA2, Spodoptera_frugiperda
    r'\b([A-Z][a-z]{2,15}[A-Z0-9][A-Za-z0-9]*)\b'
    r'|'
    # Short alphanumeric genes: p53, ras
    r'\b([a-z][a-z0-9]{1,8}[0-9]+[a-z0-9]*)\b'
)

# Words to exclude from entity detection
ENTITY_STOP_WORDS = {
    'is', 'are', 'was', 'were', 'the', 'a', 'an', 'in', 'on', 'at', 'to',
    'of', 'for', 'with', 'by', 'from', 'as', 'or', 'and', 'not', 'no',
    'it', 'its', 'be', 'has', 'have', 'had', 'do', 'does', 'did',
    'this', 'that', 'these', 'those', 'what', 'which', 'who', 'where',
    'when', 'how', 'why', 'can', 'could', 'may', 'might', 'will',
    'would', 'should', 'shall', 'Table', 'Tables', 'Figure', 'Figures',
    'Supplementary', 'Supplement', 'Data', 'Dataset', 'File', 'Files',
    'Sheet', 'Row', 'Column', 'Gene', 'Protein', 'Compound', 'Entity',
    'Found', 'Find', 'Search', 'Query', 'Result', 'Results', 'Present',
    'Contains', 'Contain', 'FC', 'Expression', 'Log2FC', 'LogFC',
    'Does', 'Where', 'What', 'Which', 'Are', 'Is', 'Any', 'Some',
}

# Supplementary entity intent keywords
SUPP_ENTITY_INTENT_KEYWORDS = [
    'supplementary', 'supplement', 'supplemental', 'suppl',
    'table s', 'table_s', 'supplementary table', 'supplementary data',
    'supplementary file', 'supplementary dataset',
]

ENTITY_TYPE_KEYWORDS = {
    'gene': ['gene', 'genes', 'gene symbol', 'gene name', 'gene id', 'locus'],
    'protein': ['protein', 'proteins', 'peptide', 'accession', 'uniprot'],
    'compound': ['compound', 'metabolite', 'chemical', 'molecule'],
    'treatment': ['treatment', 'condition', 'dose', 'concentration'],
}

LOCATION_INTENT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'where\s+is\s+\w+\s+found',
        r'is\s+\w+\s+present\s+in',
        r'find\s+\w+\s+in\s+\w+\s+(?:table|file|supplement)',
        r'which\s+(?:supplementary\s+)?table\s+contains',
        r'what\s+(?:supplementary\s+)?(?:data|file|table)\s+contains',
        r'does\s+\w+\s+appear\s+in',
        r'what\s+are\s+the\s+(?:fc|p.value|expression|log2fc|lc50|ld50)',
        r'in\s+(?:supplementary|supplemental)\s+(?:file|data|table)',
    ]
]

VALUE_KEYWORD_PATTERNS = [
    'fc', 'fold change', 'fold_change', 'log2fc', 'log 2 fc',
    'p-value', 'p value', 'pvalue', 'padj', 'fdr', 'qvalue',
    'expression', 'lc50', 'ld50', 'ic50', 'ec50',
    'mortality', 'survival', 'count', 'tpm', 'fpkm',
    'concentration', 'dose',
]


def parse_entity_query(question: str) -> dict[str, Any]:
    """Parse a user question for supplementary entity query.

    Returns dict with: entity_query, entity_type, requested_values,
    is_supplementary_context, is_location_intent, paper_id.
    """
    result: dict[str, Any] = {
        "entity_query": None,
        "entity_type": None,
        "requested_values": [],
        "is_supplementary_context": False,
        "is_location_intent": False,
        "paper_id": None,
    }

    q_lower = question.lower()
    q_words = set(re.findall(r'\b\w+\b', q_lower))

    # Check supplementary context
    result["is_supplementary_context"] = any(
        kw in q_lower for kw in SUPP_ENTITY_INTENT_KEYWORDS
    )

    # Check location intent
    result["is_location_intent"] = any(
        pat.search(question) for pat in LOCATION_INTENT_PATTERNS
    )

    # If no supplementary context and no explicit location intent,
    # check if question mentions genes/proteins with data questions
    has_entity_type_word = any(
        kw in q_words for kws in ENTITY_TYPE_KEYWORDS.values() for kw in kws
    )
    if not result["is_supplementary_context"] and not result["is_location_intent"] and not has_entity_type_word:
        result["is_location_intent"] = any(pat.search(question) for pat in LOCATION_INTENT_PATTERNS)

    # Extract entity query token
    entity_candidates = ENTITY_PATTERN.findall(question)
    # Flatten tuple groups from regex
    flat_candidates: list[str] = []
    for match in ENTITY_PATTERN.finditer(question):
        token = match.group(0).strip()
        if token and token not in ENTITY_STOP_WORDS:
            flat_candidates.append(token)

    if flat_candidates:
        # Prefer the longest candidate
        result["entity_query"] = max(flat_candidates, key=len)

    # Detect entity type from context
    for etype, keywords in ENTITY_TYPE_KEYWORDS.items():
        if any(kw in q_words for kw in keywords):
            result["entity_type"] = etype
            break

    # Detect requested values
    result["requested_values"] = [
        kw for kw in VALUE_KEYWORD_PATTERNS if kw in q_lower
    ]
    # Normalize common value terms
    if 'p value' in q_lower or 'pvalue' in q_lower or 'p-value' in q_lower:
        if 'p-value' not in result["requested_values"]:
            result["requested_values"].append('p-value')

    return result


def is_supplementary_entity_query(question: str) -> bool:
    """Quick check: is this question a supplementary entity query?"""
    parsed = parse_entity_query(question)
    # Must have an entity-like token AND either supplementary context or location intent
    has_entity = parsed["entity_query"] is not None
    in_supp_context = parsed["is_supplementary_context"] or parsed["is_location_intent"]

    # Also check for gene/protein + data query patterns
    q_lower = question.lower()
    has_entity_keyword = any(
        kw in q_lower for kws in ENTITY_TYPE_KEYWORDS.values() for kw in kws
    )

    return has_entity and (in_supp_context or has_entity_keyword)
