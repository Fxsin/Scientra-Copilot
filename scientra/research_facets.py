"""
Research Facet Classifier V1 — Generic research-direction classification.

Classifies papers into research facets based on title, keywords, summary,
and V2.3 evidence fields. No domain-specific hardcoding.
"""

from __future__ import annotations

import re
from typing import Any

# ── Facet definitions (generic research concepts, not domain-specific) ──

FACETS: list[dict[str, Any]] = [
    {
        "facet": "bioactivity_phenotype",
        "label": "Bioactivity / Phenotype",
        "signals": [
            "bioassay", "activity", "toxicity", "mortality", "survival",
            "phenotype", "efficacy", "dose", "concentration", "lc50", "ic50",
            "growth", "inhibition", "potency", "lethal", "sublethal",
            "bioactivity", "insecticidal activity", "larval", "feeding",
        ],
        "section_bonus": ["results", "abstract"],
    },
    {
        "facet": "structure_modeling",
        "label": "Structure / Modeling",
        "signals": [
            "structure", "3d", "crystal", "crystallography", "cryo-em", "cryo em",
            "model", "modeling", "molecular dynamics", "docking", "alphafold",
            "conformation", "fold", "structural", "homology model",
            "domain structure", "tertiary", "quaternary", "resolution",
            "electron microscopy", "x-ray", "nmr structure",
        ],
        "section_bonus": ["methods", "results"],
    },
    {
        "facet": "domain_mutagenesis_engineering",
        "label": "Domain / Mutagenesis / Engineering",
        "signals": [
            "domain", "truncation", "mutation", "mutant", "variant",
            "chimera", "chimeric", "substitution", "residue", "engineering",
            "swap", "deletion", "mutagenesis", "site-directed", "alanine scanning",
            "domain swapping", "n-terminal", "c-terminal", "truncated",
            "fragment", "proteolytic", "activation",
        ],
        "section_bonus": ["results", "methods"],
    },
    {
        "facet": "target_binding_interaction",
        "label": "Target / Binding / Interaction",
        "signals": [
            "receptor", "binding", "ligand", "interaction", "affinity",
            "competition", "pull-down", "blot", "co-immunoprecipitation",
            "target", "membrane", "docking", "brush border", "bbmv",
            "alkaline phosphatase", "cadherin", "aminopeptidase",
            "scavenger receptor", "fgfr", "surface plasmon resonance",
            "radiolabel", "biotinylation",
        ],
        "section_bonus": ["results", "discussion"],
    },
    {
        "facet": "resistance_genetics_adaptation",
        "label": "Resistance / Genetics / Adaptation",
        "signals": [
            "resistance", "resistant", "susceptibility", "inheritance",
            "allele", "genotype", "mutation", "population", "field-derived",
            "selection", "fitness cost", "adaptation", "cross-resistance",
            "resistance allele", "resistance mechanism", "genetic basis",
            "heritability", "backcross", "f2 screen", "frequency",
        ],
        "section_bonus": ["results", "discussion"],
    },
    {
        "facet": "expression_production_application",
        "label": "Expression / Production / Application",
        "signals": [
            "expression", "purification", "production", "recombinant",
            "transgenic", "formulation", "field trial", "application",
            "crop", "plant", "strain", "fermentation", "heterologous",
            "overexpression", "synthesis", "yield", "scale-up",
            "bioreactor", "cotton", "maize", "soybean",
        ],
        "section_bonus": ["methods", "results"],
    },
    {
        "facet": "omics_response_profiling",
        "label": "Omics / Response Profiling",
        "signals": [
            "transcriptomics", "proteomics", "metabolomics", "rna-seq",
            "genome-wide", "differential expression", "pathway", "profiling",
            "response", "enrichment", "transcription", "rnai", "gene expression",
            "microarray", "supersage", "sequencing", "transcriptional",
            "upregulated", "downregulated",
        ],
        "section_bonus": ["results", "discussion"],
    },
    {
        "facet": "method_resource_review",
        "label": "Method / Resource / Review",
        "signals": [
            "review", "database", "pipeline", "protocol", "resource",
            "benchmark", "meta-analysis", "survey", "comparative analysis",
            "overview", "perspective", "mini-review", "systematic review",
            "method comparison", "tool", "software",
        ],
        "section_bonus": ["introduction", "discussion"],
    },
    {
        "facet": "gene_function_genomics",
        "label": "Gene Function / Functional Genomics",
        "signals": [
            "knockout", "knockdown", "overexpression", "overexpress", "crispr",
            "gene editing", "genome editing", "gene function", "functional genomics",
            "rna interference", "rnai", "gene silencing", "transgenic", "complementation",
            "loss of function", "gain of function", "gene family", "functional characterization",
            "promoter", "enhancer", "reporter gene", "transgene", "t-dna",
        ],
        "section_bonus": ["results", "methods"],
    },
    {
        "facet": "genetics_qtl_mapping",
        "label": "Genetics / QTL Mapping / GWAS",
        "signals": [
            "qtl", "quantitative trait", "gwas", "genome-wide association",
            "association mapping", "linkage mapping", "genetic mapping", "genetic locus",
            "genotype", "phenotype", "allele", "allelic", "segregation",
            "recombination", "marker-assisted", "snp", "haplotype", "polymorphism",
            "genetic variation", "natural variation", "mapping population",
            "recombinant inbred", "doubled haploid", "backcross",
        ],
        "section_bonus": ["results", "methods"],
    },
    {
        "facet": "signaling_regulation",
        "label": "Signaling / Regulation / Pathway",
        "signals": [
            "signaling", "signalling", "signal transduction", "pathway",
            "transcription factor", "regulator", "regulation", "regulatory network",
            "phosphorylation", "dephosphorylation", "kinase", "phosphatase",
            "hormone", "aba", "auxin", "gibberellin", "jasmonic", "salicylic",
            "receptor-like kinase", "map kinase", "second messenger", "calcium",
            "transcriptional regulation", "promoter binding", "dna binding",
            "upstream", "downstream", "cascade",
        ],
        "section_bonus": ["results", "discussion"],
    },
    {
        "facet": "development_morphology",
        "label": "Development / Morphology / Physiology",
        "signals": [
            "development", "developmental", "morphology", "morphogenesis",
            "growth", "architecture", "organ", "tissue", "differentiation",
            "embryo", "seed", "root", "leaf", "flower", "fruit",
            "meristem", "cell division", "elongation", "senescence",
            "germination", "flowering time", "heading date", "plant height",
            "biomass", "yield", "grain", "tiller", "panicle",
        ],
        "section_bonus": ["results", "discussion"],
    },
    {
        "facet": "subcellular_localization",
        "label": "Subcellular Localization / Trafficking",
        "signals": [
            "subcellular", "localization", "nuclear", "cytoplasmic", "cytoplasm",
            "nucleus", "mitochondria", "chloroplast", "endoplasmic reticulum",
            "golgi", "plasma membrane", "vacuole", "peroxisome",
            "trafficking", "translocation", "import", "export",
            "nuclear localization signal", "targeting signal", "organelle",
            "membrane protein", "secretory pathway", "vesicle",
        ],
        "section_bonus": ["results", "methods"],
    },
    {
        "facet": "stress_physiology",
        "label": "Stress Physiology / Environmental Response",
        "signals": [
            "stress", "tolerance", "drought", "salt", "cold", "heat", "chilling",
            "osmotic", "oxidative", "abiotic", "biotic", "defense",
            "environmental", "acclimation", "adaptation", "response",
            "water deficit", "salinity", "heavy metal", "nutrient",
            "antioxidant", "reactive oxygen", "ros", "sod", "catalase",
            "proline", "malondialdehyde", "electrolyte leakage",
            "photosynthesis", "chlorophyll", "stomatal", "transpiration",
        ],
        "section_bonus": ["results", "discussion"],
    },
]


def classify_paper_facets(paper: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify a paper into research facets. Returns top 3 facets with scores."""
    # Build text corpus from all available fields
    texts: list[tuple[str, str]] = []  # (text, source)

    title = str(paper.get("title", ""))
    if title:
        texts.append((title.lower(), "title"))

    for kw in paper.get("keywords", []):
        texts.append((str(kw).lower(), "keywords"))

    summary = paper.get("summary", "")
    if summary:
        texts.append((str(summary).lower(), "summary"))

    # Evidence V2.3 fields
    evidence = paper.get("evidence")
    if evidence and isinstance(evidence, dict):
        for field, source in [
            ("key_results", "key_results"),
            ("core_findings", "core_findings"),
            ("methods", "methods"),
            ("discussion_points", "discussion_points"),
        ]:
            for item in evidence.get(field, []) or []:
                if isinstance(item, dict):
                    t = str(item.get("result") or item.get("finding") or item.get("point") or item.get("name") or "")
                else:
                    t = str(item)
                if t:
                    texts.append((t.lower(), source))

    # Score each facet
    results: list[dict[str, Any]] = []
    for facet_def in FACETS:
        score = 0.0
        matched_terms: list[str] = []
        evidence_sources: set[str] = set()

        for text, source in texts:
            for signal in facet_def["signals"]:
                # Word-boundary matching
                pattern = re.compile(r"\b" + re.escape(signal) + r"\b", re.IGNORECASE)
                matches = pattern.findall(text)
                if matches:
                    count = len(matches)
                    # Bonus for evidence fields over title/keywords
                    weight = 2.0 if source in ("key_results", "core_findings", "methods") else 1.0
                    score += count * 0.08 * weight
                    if signal not in matched_terms:
                        matched_terms.append(signal)
                    evidence_sources.add(source)

        # Section bonus
        for text, source in texts:
            if source in facet_def.get("section_bonus", []):
                score += 0.02  # small bonus per matching section text

        score = min(score, 1.0)  # cap at 1.0

        if score > 0.02:  # minimum threshold
            confidence = "high" if score >= 0.65 else ("medium" if score >= 0.35 else "low")
            results.append({
                "facet": facet_def["facet"],
                "label": facet_def["label"],
                "score": round(score, 3),
                "confidence": confidence,
                "matched_terms": matched_terms[:8],
                "evidence_sources": sorted(evidence_sources),
            })

    # Sort by score, return top 3
    results.sort(key=lambda x: -x["score"])
    top = results[:3]

    # If no strong facets, add generic fallback
    if not top or top[0]["score"] < 0.10:
        top.append({
            "facet": "method_resource_review",
            "label": "Method / Resource / Review",
            "score": 0.05,
            "confidence": "low",
            "matched_terms": [],
            "evidence_sources": ["title"],
        })

    return top


def compute_topic_facet_distribution(
    papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute facet distribution for a topic from its papers."""
    from collections import Counter

    facet_counts: Counter = Counter()
    facet_papers: dict[str, list[dict[str, Any]]] = {}

    for p in papers:
        facets = p.get("research_facets", [])
        if not facets:
            # Classify on-the-fly if not pre-computed
            facets = classify_paper_facets(p)
        for f in facets[:2]:  # count top 2 facets per paper
            key = f["facet"]
            facet_counts[key] += 1
            if key not in facet_papers:
                facet_papers[key] = []
            facet_papers[key].append(p)

    total = len(papers) if papers else 1
    distribution: list[dict[str, Any]] = []
    for facet, count in facet_counts.most_common():
        facet_def = next((fd for fd in FACETS if fd["facet"] == facet), None)
        label = facet_def["label"] if facet_def else facet
        top_papers = facet_papers.get(facet, [])[:3]
        distribution.append({
            "facet": facet,
            "label": label,
            "paper_count": count,
            "ratio": round(count / total, 3),
            "top_papers": [
                {"paper_id": tp.get("paper_id", ""), "title": tp.get("title", "")}
                for tp in top_papers
            ],
        })

    return distribution
