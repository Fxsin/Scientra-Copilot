"""
Evidence Packet Builder — converts context chunks into structured Ref packets.

Phase 0.9F-P0: claim_query optimized packets with evidence roles and citations.
"""

from __future__ import annotations

import re
from typing import Any


def clean_text(text: str) -> str:
    """Remove artifacts and collapse whitespace."""
    if not text: return ""
    for artifact in ["[object Object]", "object Object", "undefined", "null null", "None None"]:
        text = text.replace(artifact, "")
    text = re.sub(r'\s+', ' ', text).strip()
    # Deduplicate repeated phrases
    words = text.split()
    if len(words) > 8:
        for w in [5, 6]:
            for i in range(len(words) - w * 2):
                a = " ".join(words[i:i+w])
                b = " ".join(words[i+w:i+w*2])
                if a == b and len(a) > 12:
                    words = words[:i+w] + words[i+w*2:]
                    text = " ".join(words)
                    break
    return text


# ── Boilerplate / Disclaimer detection ──

DISCLAIMER_PATTERNS = [
    "accuracy of the content", "should not be relied upon", "independently verified",
    "primary sources of information", "content is provided", "for informational purposes",
    "no warranty", "without warranty", "publisher note", "neutral with regard",
    "jurisdictional claims", "institutional affiliations",
    "all rights reserved", "creative commons", "open access article",
    "distributed under the terms", "competing interests", "conflict of interest",
    "data availability statement", "supplementary material",
    "author contributions", "acknowledgements", "funding",
    "this content", "this database", "source metadata",
    "generated summary", "parsed content", "extracted content",
    "should be verified", "not intended to replace",
    "copyright", "license", "permissions", "reprint",
]

SCIENTIFIC_SIGNALS = [
    # Molecular biology — universal
    "gene", "protein", "receptor", "ligand", "enzyme", "substrate",
    "rna", "dna", "transcript", "peptide", "antibody",
    # Experimental methods — universal
    "assay", "binding", "mutation", "variant", "expression",
    "purification", "cloning", "sequencing", "pcr", "blot",
    "microscopy", "imaging", "electrophoresis", "chromatography",
    "spectroscopy", "elisa", "immuno", "histochem",
    # Cell biology — universal
    "cell", "membrane", "organelle", "nucleus", "cytoplasm",
    "mitochondria", "signaling", "transduction", "cascade",
    # Physiology/phenotype — universal
    "phenotype", "mortality", "survival", "growth", "development",
    "proliferation", "apoptosis", "differentiation", "metabolism",
    # Pharmacology/toxicology — universal
    "toxicity", "resistance", "sensitivity", "dose", "response",
    "treatment", "inhibition", "activation", "regulation",
    "lc50", "ld50", "ic50", "ec50",
    # Statistics/evidence — universal
    "significant", "p-value", "statistical", "correlation",
    "regression", "control", "experiment", "result", "finding",
    "evidence", "conclusion", "validation", "replicate",
    # Structural/biophysical — universal
    "structure", "domain", "conformation", "folding", "interaction",
    "localization", "trafficking", "transport", "channel",
    # Omics — universal
    "transcriptome", "proteome", "metabolome", "genome",
    "sequence", "alignment", "homology", "conserved",
    # Genetic manipulation — universal
    "knockout", "knockdown", "overexpression", "mutagenesis",
    "transgenic", "crispr", "rnai", "sirna",
]


def _classify_method_category(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["pcr", "qpcr", "sequencing", "cloning", "gene", "rna", "dna", "mutagenesis", "crispr", "rnai", "knockout", "transcript", "genom"]): return "molecular/genetic"
    if any(w in t for w in ["western blot", "sds-page", "elisa", "protein", "purification", "blot", "electrophoresis", "antibod", "immuno", "lc-ms", "mass spectrom"]): return "protein/biochemical"
    if any(w in t for w in ["bioassay", "toxicity", "lc50", "ld50", "mortality", "feeding", "diet", "leaf disc", "larvae", "field trial"]): return "bioassay/phenotype"
    if any(w in t for w in ["microscop", "imaging", "confocal", "immunofluorescen", "histolog", "tem", "sem", "cryo-em"]): return "microscopy/imaging"
    if any(w in t for w in ["statistical", "regression", "anova", "t-test", "phylogenetic", "alignment", "docking", "bioinformatic", "software", "computational"]): return "computational/statistical"
    return "other"


def is_boilerplate_or_disclaimer(text: str) -> bool:
    """Check if text is a non-scientific boilerplate/disclaimer."""
    text_lower = text.lower()
    has_disclaimer = any(p in text_lower for p in DISCLAIMER_PATTERNS)
    if not has_disclaimer:
        return False
    # If it has disclaimer patterns AND no scientific signals, it's boilerplate
    has_science = any(s in text_lower for s in SCIENTIFIC_SIGNALS)
    return not has_science


def classify_evidence_role(chunk_type: str, confidence: str, text: str, has_links: bool) -> str:
    if is_boilerplate_or_disclaimer(text):
        return "boilerplate"
    if chunk_type == "claim" and confidence in ("low", "medium") and not has_links:
        return "weak_claim"
    if chunk_type == "claim" and confidence == "low":
        return "weak_claim"
    if chunk_type == "claim":
        return "claim"
    if chunk_type == "result":
        return "supporting_result"
    if chunk_type == "figure":
        return "figure_context"
    if confidence == "low":
        return "weak_evidence"
    return "direct_evidence" if confidence == "high" else "background"


def build_citation(paper_title: str, year: Any) -> str:
    """Build author-year style citation from available info."""
    title = str(paper_title or "Unknown").strip()
    yr = str(year).strip() if year else ""
    # Use first significant word as pseudo-author
    words = [w for w in title.split() if len(w) > 2 and w.lower() not in
             ("the", "and", "for", "from", "with", "that", "this", "into", "over")]
    short = " ".join(words[:6]) if words else title[:60]
    if yr:
        return f"{short} ({yr})"
    return short


def build_evidence_packet(chunks: list, max_items: int = 12, max_chars: int = 900, intent: str = "") -> str:
    """Build a structured Evidence Packet for LLM consumption.

    Each Ref: citation, chunk type, evidence role, confidence, content, links.
    For research_gap_query: adds gap inference hints.
    """
    lines: list[str] = []
    seen_texts: set[str] = set()

    count = 0
    for i, chunk in enumerate(chunks):
        if count >= max_items:
            break

        text = clean_text(getattr(chunk, 'text', ''))
        if not text or len(text) < 20:
            continue
        if is_boilerplate_or_disclaimer(text):
            continue  # Skip disclaimers — not scientific claims

        # Dedup
        key = text[:80].strip().lower()
        if key in seen_texts:
            continue
        seen_texts.add(key)

        ref_id = count + 1
        title = getattr(chunk, 'paper_title', '') or getattr(chunk, 'paper_id', '')[:60]
        year = getattr(chunk, 'paper_year', None)
        ctype = getattr(chunk, 'chunk_type', 'unknown')
        conf = getattr(chunk, 'confidence', 'unknown')
        ev_ids = getattr(chunk, 'linked_evidence_ids', []) or []
        has_links = len(ev_ids) > 0
        role = classify_evidence_role(ctype, conf, text, has_links)
        citation = build_citation(title, year)

        # Build Ref block
        parts = [
            f"[Ref:{ref_id}]",
            f"Citation: {citation}",
            f"Chunk type: {ctype}",
            f"Evidence role: {role}",
            f"Confidence: {conf}",
        ]
        if has_links:
            parts.append(f"Linked evidence: {len(ev_ids)} item(s)")
        if ctype == "claim":
            parts.append(f"Text: {text[:max_chars]}")
        else:
            parts.append(f"Text: {text[:max_chars]}")

        # Method-specific: add category hint
        if intent == "method_query":
            cat = _classify_method_category(text)
            if cat != "other":
                parts.append(f"Method category: {cat}")

        # Result-specific: add strength hint
        if intent == "result_query":
            strength = "direct" if conf == "high" else ("supporting" if conf == "medium" else "descriptive")
            parts.append(f"Evidence strength: {strength}")

        # Gap-specific hints
        if intent == "research_gap_query" and role in ("weak_claim", "indirect_evidence", "background"):
            reasons = []
            if not has_links: reasons.append("no linked evidence")
            if conf in ("low", "medium"): reasons.append(f"{conf} confidence")
            if any(w in text.lower() for w in ["unclear", "unknown", "remains", "requires", "future"]):
                reasons.append("text indicates uncertainty")
            if reasons:
                parts.append(f"Potential gap signal: {', '.join(reasons)}")

        # Weakness notes for claims
        if role == "weak_claim":
            notes = []
            if not has_links: notes.append("no linked evidence")
            if conf in ("low", "medium"): notes.append(f"{conf} confidence")
            if notes: parts.append(f"Notes: {', '.join(notes)}")

        lines.append("\n".join(parts) + "\n")
        count += 1

    if not lines:
        return "No clean evidence available for this query."

    return "\n".join(lines)
