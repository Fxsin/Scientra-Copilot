"""
Research Map Cache Builder — Stable, persistent topic clusters.

Usage:
  python -m scientra.research_map_builder --force   # rebuild cache
  python -m scientra.research_map_builder --status   # show cache status
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CACHE_SCHEMA_VERSION = "research_map_v3_facet_hierarchical"
CACHE_DIR_NAME = "05_Index"
CACHE_FILE_NAME = "research_map_clusters.json"
RANDOM_SEED = 42


def _safe_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for _ in range(3):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.3)
    tmp.replace(path)


def _build_topic_paper_payload_for_cache(root: Path, paper_record: dict[str, Any]) -> dict[str, Any]:
    """Build a paper dict with summary + evidence for facet classification."""
    from scientra.server import _load_summary_text, _load_evidence_summary
    pid = paper_record.get("paper_id") or paper_record.get("id", "")
    return {
        "paper_id": str(pid),
        "title": str(paper_record.get("title", "")),
        "authors": paper_record.get("authors", []) or [],
        "year": paper_record.get("year"),
        "journal": str(paper_record.get("journal", "")),
        "doi": str(paper_record.get("doi", "")),
        "keywords": paper_record.get("tags", []) or [],
        "summary": _load_summary_text(root, str(pid)) if pid else "",
        "evidence": _load_evidence_summary(root, str(pid)) if pid else None,
    }


def _build_facet_based_topics(
    papers: list[dict[str, Any]],
    vectors: dict[str, list[float]],
) -> list[dict[str, Any]]:
    """Build topics organized by dominant research facet.
    Each facet becomes a topic with papers that match it.
    """
    from scientra.research_facets import FACETS
    from scientra.server import _select_representative_papers
    from datetime import datetime, timezone

    # Group papers by dominant facet
    paper_facet_map: dict[str, list[dict[str, Any]]] = {f["facet"]: [] for f in FACETS}

    for p in papers:
        facets = p.get("research_facets", [])
        if not facets:
            paper_facet_map.setdefault("method_resource_review", []).append(p)
            continue
        top = facets[0]
        top_facet = top["facet"]
        if top_facet in paper_facet_map:
            paper_facet_map[top_facet].append(p)
        else:
            # Unknown facet key — assign to fallback
            paper_facet_map.setdefault("method_resource_review", []).append(p)

    # Collect unclassified papers (no strong facet match)
    unclassified: list[dict[str, Any]] = []
    for p in papers:
        facets = p.get("research_facets", [])
        if not facets or facets[0].get("score", 0) < 0.03:
            unclassified.append(p)
            # Give them a weak fallback facet
            p["research_facets"] = [{
                "facet": "method_resource_review",
                "label": "Method / Resource / Review",
                "score": 0.03,
                "confidence": "low",
                "matched_terms": [],
                "evidence_sources": ["title"],
            }]
        # Ensure the top facet key is in paper_facet_map
        top_facet = p["research_facets"][0]["facet"]
        if top_facet not in paper_facet_map:
            paper_facet_map[top_facet] = []

    # Assign unclassified to fallback
    for p in unclassified:
        paper_facet_map["method_resource_review"].append(p)

    # Build facet groups with subtopic clustering
    from collections import Counter
    from datetime import datetime, timezone

    facet_result_groups: list[dict[str, Any]] = []
    all_clusters: list[dict[str, Any]] = []
    topic_num = 0

    STOPWORDS = {
        "this", "that", "with", "from", "into", "using", "based", "also",
        "study", "studies", "paper", "papers", "result", "results", "method", "methods",
        "data", "found", "show", "shown", "report", "reported", "used", "role", "roles",
        "effect", "effects", "were", "have", "been", "which", "their", "than",
        "these", "those", "about", "between", "among", "against", "first",
        # Evidence boilerplate
        "finding", "findings", "showed", "demonstrated", "revealed", "indicated",
        "suggested", "observed", "confirmed", "identified", "detected",
        "significant", "conclusion", "evidence", "approach", "approaches",
        "associated", "compared", "including", "various", "different",
        "may", "also", "one", "two", "three", "several", "however", "therefore",
        "thus", "abstract", "introduction", "discussion", "conclusions",
        "background", "objective", "expression", "activity", "protein", "proteins",
        "level", "levels", "content", "text", "citation", "citations",
        "response", "analysis", "present", "novel", "new", "gene", "genes",
        "species", "strain", "strains", "field", "fields",
        "bacillus", "thuringiensis",
    }

    for facet_def in FACETS:
        facet_key = facet_def["facet"]
        facet_papers = paper_facet_map.get(facet_key, [])
        if len(facet_papers) < 1:
            continue
        # Allow single-paper facets for completeness
        if len(facet_papers) < 2 and facet_key != "method_resource_review":
            # Reassign lone papers to fallback
            for p in facet_papers:
                paper_facet_map.setdefault("method_resource_review", []).append(p)
            continue

        # ── Compute facet-level stats ──
        all_text = " ".join([str(p.get("title", "")) + " " + str(p.get("summary", ""))[:500]
                            for p in facet_papers[:15]])
        words = re.findall(r'\b[a-z]{4,}\b', all_text.lower())
        facet_kw = [w for w, _ in Counter(words).most_common(10) if w not in STOPWORDS]

        years = [int(p.get("year") or 0) for p in facet_papers
                 if p.get("year") is not None and int(p.get("year") or 0) > 1800]
        yr_range = [min(years), max(years)] if years else [0, 0]

        # ── Subtopic clustering within facet ──
        n = len(facet_papers)
        if n <= 5:
            num_subtopics = 1
        elif n <= 12:
            num_subtopics = 2
        else:
            num_subtopics = min(4, max(2, n // 8))

        # Simple k-means–style clustering using title + summary tokens + methods
        # Assign papers to subtopics by round-robin with similarity refinement
        subtopic_assignments: list[list[dict[str, Any]]] = [[] for _ in range(num_subtopics)]

        # Sort papers by evidence richness, then distribute evenly
        def evidence_score(p: dict[str, Any]) -> int:
            ev = p.get("evidence", {})
            if not ev or not isinstance(ev, dict):
                return 0
            return (len(ev.get("key_results", [])) + len(ev.get("core_findings", [])) +
                    len(ev.get("discussion_points", [])) + len(ev.get("methods", [])))

        sorted_papers = sorted(facet_papers, key=evidence_score, reverse=True)

        # Distribute papers: top papers spread across subtopics for balance
        for i, p in enumerate(sorted_papers):
            bucket = i % num_subtopics
            subtopic_assignments[bucket].append(p)

        # ── Build subtopic clusters ──
        subtopics: list[dict[str, Any]] = []
        for si, sub_papers in enumerate(subtopic_assignments):
            if not sub_papers:
                continue
            topic_num += 1
            cluster_id = f"facet_{facet_key}_{topic_num:03d}"

            # Subtopic keywords from these specific papers
            sub_text = " ".join([str(p.get("title", "")) + " " + str(p.get("summary", ""))[:300]
                                for p in sub_papers[:8]])
            sub_words = re.findall(r'\b[a-z]{4,}\b', sub_text.lower())
            sub_kw = [w for w, _ in Counter(sub_words).most_common(8) if w not in STOPWORDS]

            # Subtopic name from evidence concepts + paper titles
            sub_name = _build_subtopic_name(sub_papers, sub_kw, facet_def["label"])
            # Ensure uniqueness: try secondary intent before numbering
            existing_names = [s["name"] for s in subtopics]
            if sub_name in existing_names and facet_key in FACET_INTENTS:
                # Try second-best intent, then general, then facet default
                intent2 = _classify_subtopic_intent_secondary(facet_key, sub_papers, sub_name)
                if intent2 and intent2 not in existing_names:
                    sub_name = intent2
                else:
                    # Use facet default or general bioactivity as last resort
                    fallback = f"{facet_def['label']}: Group {len(subtopics) + 1}"
                    if fallback not in existing_names:
                        sub_name = fallback
            if sub_name in existing_names:
                counter = 2
                while f"{sub_name} {counter}" in existing_names:
                    counter += 1
                sub_name = f"{sub_name} {counter}"

            sub_years = [int(p.get("year") or 0) for p in sub_papers
                        if p.get("year") is not None and int(p.get("year") or 0) > 1800]
            sub_yr = [min(sub_years), max(sub_years)] if sub_years else yr_range

            # Representative papers
            sub_paper_map = {p["paper_id"]: p for p in sub_papers}
            sub_rep_pids = set(p["paper_id"] for p in sub_papers[:10])
            rep_papers = _select_representative_papers(
                sub_rep_pids, sub_paper_map, vectors,
                sub_papers[0]["paper_id"], count=3
            )

            # Evidence coverage
            ev_count = sum(1 for p in sub_papers
                          if p.get("evidence") and isinstance(p.get("evidence"), dict)
                          and p["evidence"].get("status") != "failed")

            # Papers with relevance
            papers_with_rel = []
            for p in sub_papers:
                top_score = p.get("research_facets", [{}])[0].get("score", 0.5) if p.get("research_facets") else 0.5
                papers_with_rel.append({
                    **{k: v for k, v in p.items() if k not in ("summary", "evidence")},
                    "summary": str(p.get("summary", ""))[:500],
                    "evidence": p.get("evidence"),
                    "topic_relevance": round(top_score, 3),
                    "relevance_label": "high" if top_score >= 0.65 else ("medium" if top_score >= 0.35 else "low"),
                    "relevance_reason": f"Subtopic within {facet_def['label']}",
                })

            this_year = datetime.now(timezone.utc).year
            recent_count = sum(1 for y in sub_years if y >= this_year - 5)
            recent_ratio = recent_count / len(sub_years) if sub_years else 0

            name_meta = _get_subtopic_name_metadata(sub_papers, sub_name, facet_def["label"])
            subtopic = {
                "cluster_id": cluster_id,
                "name": sub_name,
                "paper_count": len(sub_papers),
                "year_range": sub_yr,
                "keywords": [str(k) for k in sub_kw[:6]],
                "papers": papers_with_rel,
                "representative_papers": rep_papers,
                "evidence_coverage": ev_count,
                "facet": facet_key,
                "facet_label": facet_def["label"],
                "name_source": name_meta["name_source"],
                "name_confidence": name_meta["name_confidence"],
                "name_evidence": name_meta["name_evidence"],
                "type": "mature",
                "trend": "stable",
                "trend_label": "active" if recent_ratio >= 0.4 else "stable",
                "recent_count": recent_count,
                "recent_ratio": round(recent_ratio, 3),
                "cohesion_score": 0.5,
                "cohesion_label": "moderate",
                "related_topics": [],
                "subtopics": [],
                "is_merged": False,
            }
            subtopics.append(subtopic)
            all_clusters.append(subtopic)

        facet_result_groups.append({
            "facet": facet_key,
            "label": facet_def["label"],
            "paper_count": len(facet_papers),
            "ratio": round(len(facet_papers) / max(len(papers), 1), 3),
            "keywords": [str(k) for k in facet_kw[:8]],
            "summary": f"Research on {facet_def['label'].lower()} across {len(facet_papers)} papers.",
            "representative_papers": subtopics[0]["representative_papers"][:2] if subtopics else [],
            "subtopics": subtopics,
            "year_range": yr_range,
        })

    return all_clusters, facet_result_groups


# ═══════════════════════════════════════════════════════════════
# Controlled Subtopic Intent System
# ═══════════════════════════════════════════════════════════════

FACET_INTENTS: dict[str, list[dict[str, Any]]] = {
    "bioactivity_phenotype": [
        {"intent": "quantitative_toxicity", "label": "Quantitative toxicity and dose-response analysis",
         "signals": ["lc50", "lc90", "ic50", "ld50", "dose", "concentration", "dose-response", "dosage",
                      "mortality rate", "survival curve", "probit", "lethal concentration", "lethal dose",
                      "sublethal", "sub-lethal", "inhibition concentration"],
         "specificity": "high"},
        {"intent": "comparative_bioactivity", "label": "Comparative bioactivity and efficacy assessment",
         "signals": ["comparative", "comparison", "compared", "efficacy", "activity comparison", "spectrum",
                      "potency", "performance", "more active", "less active", "enhanced activity",
                      "reduced activity", "relative activity", "versus"],
         "specificity": "medium"},
        {"intent": "host_range_phenotype", "label": "Host range and phenotype evaluation",
         "signals": ["host range", "spectrum", "susceptible", "susceptibility", "phenotype",
                      "biological effect", "growth", "development", "larvae", "organism",
                      "target organism", "response", "feeding", "weight", "survival"],
         "specificity": "medium"},
        {"intent": "applied_performance", "label": "Applied performance and field evaluation",
         "signals": ["field", "field trial", "field population", "application", "applied",
                      "formulation", "crop", "plant", "performance", "efficacy",
                      "control effect", "greenhouse", "plot"],
         "specificity": "medium"},
        {"intent": "resistance_linked_activity", "label": "Resistance-linked bioactivity and susceptibility shifts",
         "signals": ["resistant", "resistance", "susceptible", "susceptibility", "reduced sensitivity",
                      "cross-resistance", "resistance ratio", "field-derived", "selected strain",
                      "resistance allele", "resistance level"],
         "specificity": "high"},
        {"intent": "general_bioactivity", "label": "General bioactivity and phenotype assessment",
         "signals": ["bioactivity", "activity", "biological activity", "phenotypic effect", "assay",
                      "bioassay", "toxicity", "mortality", "inhibition", "survival", "potency"],
         "specificity": "low"},
        {"intent": "default", "label": "Bioactivity and phenotype assessment",
         "signals": []},
    ],
    "structure_modeling": [
        {"intent": "protein_structure", "label": "Protein structure and conformational analysis",
         "signals": ["structure", "conformation", "fold", "topology", "architecture", "secondary structure", "tertiary", "quaternary"]},
        {"intent": "structural_modeling", "label": "Structural modeling and computational analysis",
         "signals": ["modeling", "model", "alphafold", "docking", "simulation", "molecular dynamics", "prediction", "computational", "homology"]},
        {"intent": "experimental_structure", "label": "Experimental structure determination",
         "signals": ["crystal", "crystallography", "cryo-em", "cryo em", "electron microscopy", "diffraction", "resolution", "x-ray", "nmr"]},
        {"intent": "default", "label": "Structure and modeling analysis",
         "signals": []},
    ],
    "domain_mutagenesis_engineering": [
        {"intent": "domain_function", "label": "Domain function and activity mapping",
         "signals": ["domain", "region", "functional region", "activity mapping", "n-terminal", "c-terminal", "core domain"]},
        {"intent": "mutagenesis_residue", "label": "Mutagenesis and residue-function analysis",
         "signals": ["mutation", "mutant", "residue", "substitution", "alanine", "variant", "site-directed", "point mutation"]},
        {"intent": "protein_engineering", "label": "Protein engineering and variant design",
         "signals": ["engineering", "chimera", "chimeric", "swap", "domain swapping", "truncation", "deletion", "fusion", "design"]},
        {"intent": "default", "label": "Domain and engineering analysis",
         "signals": []},
    ],
    "target_binding_interaction": [
        {"intent": "receptor_identification", "label": "Target identification and receptor evidence",
         "signals": ["receptor", "target", "candidate", "identification", "validation", "screen", "screen"]},
        {"intent": "binding_assay", "label": "Binding assays and interaction analysis",
         "signals": ["binding", "affinity", "ligand", "interaction", "competition", "pull-down", "blot", "assay", "kinetics"]},
        {"intent": "membrane_interaction", "label": "Membrane interaction and localization",
         "signals": ["membrane", "surface", "localization", "binding site", "receptor site", "brush border", "vesicle"]},
        {"intent": "default", "label": "Target binding and interaction evidence",
         "signals": []},
    ],
    "resistance_genetics_adaptation": [
        {"intent": "resistance_mechanism", "label": "Resistance mechanisms and susceptibility shifts",
         "signals": ["resistance", "resistant", "susceptibility", "mechanism", "tolerance", "reduced sensitivity", "cross-resistance"]},
        {"intent": "inheritance_genetics", "label": "Resistance inheritance and genetic variation",
         "signals": ["inheritance", "allele", "genotype", "mutation", "gene", "locus", "genetic", "heritability", "trait"]},
        {"intent": "population_adaptation", "label": "Population adaptation and fitness cost",
         "signals": ["population", "field-derived", "selection", "adaptation", "fitness cost", "frequency", "evolution"]},
        {"intent": "default", "label": "Resistance genetics and adaptation",
         "signals": []},
    ],
    "expression_production_application": [
        {"intent": "expression_system", "label": "Expression systems and recombinant production",
         "signals": ["expression", "recombinant", "production", "purification", "heterologous", "expressed", "vector", "construct"]},
        {"intent": "application_delivery", "label": "Application systems and delivery performance",
         "signals": ["application", "delivery", "formulation", "transgenic", "field", "crop", "plant", "strain", "deployment"]},
        {"intent": "production_optimization", "label": "Production optimization and stability",
         "signals": ["yield", "stability", "optimization", "fermentation", "purification", "soluble", "insoluble", "scale-up"]},
        {"intent": "default", "label": "Expression and application systems",
         "signals": []},
    ],
    "omics_response_profiling": [
        {"intent": "transcriptomic_response", "label": "Transcriptomic and gene expression response",
         "signals": ["transcriptomics", "rna-seq", "differential expression", "gene expression", "transcription", "microarray", "rnai"]},
        {"intent": "multiomics_profiling", "label": "Multi-omics response profiling",
         "signals": ["proteomics", "metabolomics", "omics", "profiling", "integrated analysis", "pathway", "enrichment"]},
        {"intent": "default", "label": "Omics and response profiling",
         "signals": []},
    ],
    "method_resource_review": [
        {"intent": "review_synthesis", "label": "Review and conceptual synthesis",
         "signals": ["review", "overview", "synthesis", "perspective", "progress", "advances", "update"]},
        {"intent": "method_resource", "label": "Methods, resources, and analytical pipelines",
         "signals": ["protocol", "method", "pipeline", "database", "benchmark", "resource", "tool", "software"]},
        {"intent": "comparative_analysis", "label": "Comparative analysis and literature survey",
         "signals": ["comparative analysis", "survey", "meta-analysis", "evaluation", "systematic"]},
        {"intent": "default", "label": "Method, resource, and review papers",
         "signals": []},
    ],
    "gene_function_genomics": [
        {"intent": "gene_editing", "label": "Gene editing and genome modification",
         "signals": ["crispr", "gene editing", "genome editing", "cas9", "talen", "zfn"], "specificity": "high"},
        {"intent": "knockout_knockdown", "label": "Gene knockout and knockdown analysis",
         "signals": ["knockout", "knockdown", "rna interference", "rnai", "gene silencing", "loss of function"], "specificity": "high"},
        {"intent": "overexpression_study", "label": "Overexpression and gain-of-function studies",
         "signals": ["overexpression", "overexpress", "gain of function", "transgenic", "constitutive expression"], "specificity": "medium"},
        {"intent": "gene_function_characterization", "label": "Gene function and family characterization",
         "signals": ["gene function", "functional genomics", "functional characterization", "gene family", "complementation"], "specificity": "medium"},
        {"intent": "default", "label": "Gene function and functional genomics",
         "signals": []},
    ],
    "genetics_qtl_mapping": [
        {"intent": "gwas_qtl", "label": "GWAS and QTL mapping analysis",
         "signals": ["gwas", "qtl", "genome-wide association", "quantitative trait", "association mapping"], "specificity": "high"},
        {"intent": "genetic_mapping", "label": "Genetic mapping and locus identification",
         "signals": ["genetic mapping", "linkage mapping", "locus", "genetic locus", "segregation", "recombination"], "specificity": "high"},
        {"intent": "allele_variation", "label": "Natural variation and allele analysis",
         "signals": ["allele", "allelic", "polymorphism", "snp", "haplotype", "natural variation", "genetic variation"], "specificity": "medium"},
        {"intent": "default", "label": "Genetics and QTL mapping analysis",
         "signals": []},
    ],
    "signaling_regulation": [
        {"intent": "signaling_pathway", "label": "Signal transduction and pathway analysis",
         "signals": ["signaling", "signal transduction", "pathway", "cascade", "kinase", "phosphatase", "phosphorylation"], "specificity": "high"},
        {"intent": "transcription_regulation", "label": "Transcriptional regulation and TF analysis",
         "signals": ["transcription factor", "regulator", "regulation", "transcriptional regulation", "dna binding", "promoter binding"], "specificity": "high"},
        {"intent": "hormone_signaling", "label": "Hormone signaling and response",
         "signals": ["hormone", "aba", "auxin", "gibberellin", "jasmonic", "salicylic", "ethylene", "brassinosteroid"], "specificity": "medium"},
        {"intent": "default", "label": "Signaling and regulatory networks",
         "signals": []},
    ],
    "development_morphology": [
        {"intent": "organ_development", "label": "Organ development and morphogenesis",
         "signals": ["development", "developmental", "morphogenesis", "organ", "differentiation", "meristem", "embryo"], "specificity": "medium"},
        {"intent": "yield_architecture", "label": "Yield traits and plant architecture",
         "signals": ["yield", "grain", "biomass", "plant height", "architecture", "tiller", "panicle", "heading date", "flowering time"], "specificity": "high"},
        {"intent": "growth_physiology", "label": "Growth physiology and biomass analysis",
         "signals": ["growth", "elongation", "cell division", "senescence", "germination", "biomass", "seed"], "specificity": "medium"},
        {"intent": "default", "label": "Development and morphology analysis",
         "signals": []},
    ],
    "subcellular_localization": [
        {"intent": "protein_localization", "label": "Protein subcellular localization analysis",
         "signals": ["subcellular", "localization", "nuclear", "cytoplasmic", "nucleus", "cytoplasm", "organelle"], "specificity": "high"},
        {"intent": "membrane_trafficking", "label": "Membrane trafficking and targeting",
         "signals": ["trafficking", "translocation", "targeting signal", "secretory", "vesicle", "membrane protein", "import", "export"], "specificity": "high"},
        {"intent": "organelle_biology", "label": "Organelle biology and compartment analysis",
         "signals": ["mitochondria", "chloroplast", "endoplasmic reticulum", "golgi", "vacuole", "peroxisome"], "specificity": "high"},
        {"intent": "default", "label": "Subcellular localization and trafficking",
         "signals": []},
    ],
    "stress_physiology": [
        {"intent": "abiotic_stress", "label": "Abiotic stress tolerance mechanisms",
         "signals": ["drought", "salt", "cold", "heat", "chilling", "osmotic", "oxidative", "abiotic", "stress", "tolerance", "water deficit", "salinity"], "specificity": "medium"},
        {"intent": "stress_biochemistry", "label": "Stress biochemistry and antioxidant systems",
         "signals": ["antioxidant", "reactive oxygen", "ros", "sod", "catalase", "proline", "malondialdehyde", "electrolyte leakage", "chlorophyll"], "specificity": "high"},
        {"intent": "photosynthesis_response", "label": "Photosynthetic and physiological response",
         "signals": ["photosynthesis", "stomatal", "transpiration", "chlorophyll", "fluorescence", "carbon", "assimilation"], "specificity": "medium"},
        {"intent": "default", "label": "Stress physiology and environmental response",
         "signals": []},
    ],
}


def _classify_subtopic_intent(facet: str, papers: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify which research intent best describes this subtopic."""
    intents = FACET_INTENTS.get(facet, [{"intent": "default", "label": "General research", "signals": []}])
    if not intents:
        return {"intent": "default", "label": "General research", "score": 0.0, "matched_terms": [], "evidence_sources": []}

    # Build weighted text corpus
    text_sources: list[tuple[str, float]] = []
    for p in papers:
        text_sources.append((str(p.get("title", "")).lower(), 1.0))
        for kw in p.get("keywords", []):
            text_sources.append((str(kw).lower(), 1.0))
        ev = p.get("evidence", {})
        if ev and isinstance(ev, dict):
            for m in ev.get("methods", [])[:3]:
                if isinstance(m, dict):
                    text_sources.append((str(m.get("name", "")).lower(), 2.0))
                    text_sources.append((str(m.get("quote", "")).lower(), 1.5))
            for field, weight in [("key_results", 2.0), ("core_findings", 2.2)]:
                for item in ev.get(field, [])[:3]:
                    if isinstance(item, dict):
                        text_sources.append((str(item.get("result", item.get("finding", ""))).lower(), weight))
                        text_sources.append((str(item.get("quote", "")).lower(), weight * 0.8))

    # Score each intent with specificity weighting
    SPEC_WEIGHTS = {"high": 3.0, "medium": 1.5, "low": 0.6}
    scores: list[dict[str, Any]] = []
    for intent in intents:
        if intent["intent"] == "default":
            continue
        spec_w = SPEC_WEIGHTS.get(intent.get("specificity", "medium"), 1.5)
        score = 0.0
        matched: set[str] = set()
        sources: set[str] = set()
        has_high_spec = False
        for text, weight in text_sources:
            for signal in intent["signals"]:
                if signal in text:
                    score += 0.15 * weight * spec_w
                    matched.add(signal)
                    if intent.get("specificity") == "high":
                        has_high_spec = True
        scores.append({
            "intent": intent["intent"],
            "label": intent["label"],
            "score": round(min(score, 1.0), 3),
            "matched_terms": sorted(matched)[:8],
            "evidence_sources": sorted(sources),
            "has_high_specificity": has_high_spec,
        })

    scores.sort(key=lambda x: -x["score"])

    if scores and scores[0]["score"] >= 0.20 and len(scores[0]["matched_terms"]) >= 2:
        # Low-specificity-only intents should not win with high confidence
        top = scores[0]
        if top.get("has_high_specificity") is False and top["score"] < 0.6:
            top["name_confidence"] = "low"
        return top

    # Fallback to default
    default = next((i for i in intents if i["intent"] == "default"), intents[-1])
    return {"intent": "default", "label": default["label"], "score": 0.0, "matched_terms": [], "evidence_sources": []}


def _build_subtopic_name(papers: list[dict[str, Any]], keywords: list[str], facet_label: str) -> str:
    """Controlled subtopic naming using facet-guided intent classification."""
    if not papers:
        return "General subtopic"

    # Determine the facet from the papers' research_facets
    facet_counts: dict[str, int] = {}
    for p in papers:
        for rf in p.get("research_facets", [])[:1]:
            f = rf.get("facet", "")
            if f:
                facet_counts[f] = facet_counts.get(f, 0) + 1
    dominant_facet = max(facet_counts, key=facet_counts.get) if facet_counts else "method_resource_review"

    # Priority 1: Controlled intent classification
    intent = _classify_subtopic_intent(dominant_facet, papers)
    if intent["intent"] != "default" and intent["score"] >= 0.20:
        return intent["label"]

    # Priority 2: Facet default label
    default_intent = next(
        (i for i in FACET_INTENTS.get(dominant_facet, []) if i["intent"] == "default"),
        None,
    )
    if default_intent:
        return default_intent["label"]

    # Priority 3: Generic fallback
    if len(papers) == 1:
        return "Single-paper subtopic"
    return "General subtopic"


def _classify_subtopic_intent_secondary(facet: str, papers: list[dict[str, Any]], exclude_label: str) -> str | None:
    """Get the second-best intent label (different from exclude_label)."""
    intents = FACET_INTENTS.get(facet, [])
    scores = []
    for intent in intents:
        if intent["intent"] == "default" or intent["label"] == exclude_label:
            continue
        score = 0.0
        matched = 0
        for p in papers:
            text = (str(p.get("title", "")) + " ").lower()
            ev = p.get("evidence", {})
            if ev and isinstance(ev, dict):
                for item in ev.get("methods", [])[:2]:
                    if isinstance(item, dict):
                        text += str(item.get("name", "")).lower() + " "
                for item in ev.get("key_results", [])[:2]:
                    if isinstance(item, dict):
                        text += str(item.get("result", "")).lower() + " "
            for signal in intent["signals"]:
                if signal in text:
                    score += 0.15
                    matched += 1
        if score >= 0.08 and matched >= 1:
            scores.append((intent["label"], score))
    scores.sort(key=lambda x: -x[1])
    if scores:
        return scores[0][0]
    # Last resort: use the general_bioactivity label
    for intent in intents:
        if intent["intent"] == "general_bioactivity":
            return intent["label"]
    return None


def _get_subtopic_name_metadata(papers: list[dict[str, Any]], name: str, facet_label: str) -> dict[str, Any]:
    """Return name_source, name_confidence, and name_evidence for a subtopic."""
    facet_counts: dict[str, int] = {}
    for p in papers:
        for rf in p.get("research_facets", [])[:1]:
            f = rf.get("facet", "")
            if f:
                facet_counts[f] = facet_counts.get(f, 0) + 1
    dominant_facet = max(facet_counts, key=facet_counts.get) if facet_counts else "method_resource_review"

    intent = _classify_subtopic_intent(dominant_facet, papers)

    if intent["intent"] != "default" and intent["score"] >= 0.20:
        return {
            "name_source": "controlled_intent",
            "name_confidence": "high" if intent["score"] >= 0.50 else "medium",
            "name_evidence": intent,
        }
    elif name != "General subtopic" and name != "Single-paper subtopic":
        return {
            "name_source": "facet_default",
            "name_confidence": "medium",
            "name_evidence": intent,
        }
    else:
        return {
            "name_source": "fallback",
            "name_confidence": "low",
            "name_evidence": intent,
        }


def compute_source_fingerprint(root: Path) -> str:
    """Stable fingerprint. Changes when papers are added/removed or evidence regenerated."""
    from scientra.server import _load_yaml_metadata
    papers = _load_yaml_metadata(root)
    ids = sorted([p.get("paper_id", "") for p in papers if p.get("paper_id")])

    # Include evidence.json hashes for change detection
    evidence_hashes: dict[str, str] = {}
    evidence_dir = root / "03_Evidence"
    for pid in ids:
        # Search evidence dirs for matching paper
        search_hash = pid.replace("paper_", "") if pid.startswith("paper_") else pid
        for d in evidence_dir.iterdir():
            if not d.is_dir():
                continue
            if search_hash[:10] in d.name or d.name in pid or pid in d.name:
                ev_path = d / "evidence.json"
                if ev_path.exists():
                    try:
                        ev_data = json.loads(ev_path.read_text(encoding="utf-8"))
                        ev_version = ev_data.get("evidence_version", "")
                        ev_hash = hashlib.sha256(
                            json.dumps({
                                "v": ev_version,
                                "kr": len(ev_data.get("key_results", [])),
                                "cf": len(ev_data.get("core_findings", [])),
                                "dp": len(ev_data.get("discussion_points", [])),
                                "mt": len(ev_data.get("methods", [])),
                            }, sort_keys=True).encode()
                        ).hexdigest()[:8]
                        evidence_hashes[pid] = ev_hash
                    except Exception:
                        pass
                break

    data = json.dumps({
        "count": len(ids),
        "ids": ids,
        "evidence_hashes": evidence_hashes,
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _build_facet_group_light(fg: dict[str, Any]) -> dict[str, Any]:
    """Strip heavy fields from facet group for cache."""
    return {
        "facet": fg["facet"],
        "label": fg["label"],
        "paper_count": fg["paper_count"],
        "ratio": fg["ratio"],
        "keywords": fg.get("keywords", []),
        "summary": fg.get("summary", ""),
        "year_range": fg.get("year_range", [0, 0]),
        "subtopics": [_build_topic_payload_light(st) for st in fg.get("subtopics", [])],
    }


def _build_topic_payload_light(topic: dict[str, Any]) -> dict[str, Any]:
    """Strip heavy fields from topic for cache (keep evidence structure but not full text)."""
    light = dict(topic)
    # Keep papers but strip evidence/summary text to reduce cache size
    if "papers" in light:
        light_papers = []
        for p in light["papers"]:
            lp = {
                "paper_id": p.get("paper_id", ""),
                "title": p.get("title", ""),
                "authors": p.get("authors", []) or [],
                "year": p.get("year"),
                "journal": p.get("journal", ""),
                "doi": p.get("doi", ""),
                "topic_relevance": p.get("topic_relevance"),
                "relevance_label": p.get("relevance_label"),
                "relevance_reason": p.get("relevance_reason"),
            }
            # Include evidence summary (light) if present
            if p.get("evidence") and isinstance(p["evidence"], dict):
                ev = p["evidence"]
                lp["evidence"] = {
                    "status": ev.get("status"),
                    "core_findings": ev.get("core_findings", [])[:3],
                    "key_results": ev.get("key_results", [])[:3],
                    "discussion_points": ev.get("discussion_points", [])[:3],
                    "methods": ev.get("methods", [])[:3],
                }
            if p.get("summary"):
                lp["summary"] = str(p["summary"])[:500]
            light_papers.append(lp)
        light["papers"] = light_papers
    return light


def build_research_map_cache(root: Path, force: bool = False) -> dict[str, Any]:
    """Build or load the Research Map cache. Returns cache dict."""
    cache_dir = root / CACHE_DIR_NAME
    cache_path = cache_dir / CACHE_FILE_NAME

    # Check if cache is valid
    if not force and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            fp = compute_source_fingerprint(root)
            if cached.get("source_fingerprint") == fp and cached.get("schema_version") == CACHE_SCHEMA_VERSION:
                return cached
        except (json.JSONDecodeError, KeyError):
            pass  # corrupted, rebuild

    # Build fresh
    from scientra.server import _load_yaml_metadata, _rebuild_relationships_for_clusters, _select_representative_papers

    papers = _load_yaml_metadata(root)
    if not papers:
        return _empty_cache(root)

    vectors: dict[str, list[float]] = {}
    try:
        import lancedb
        db_dir = root / "04_VectorDB" / "lancedb"
        if db_dir.exists() and any(db_dir.iterdir()):
            db = lancedb.connect(str(db_dir))
            tables = db.table_names()
            if tables:
                table = db.open_table(tables[0])
                df = table.to_pandas()
                for row in df.to_dict("records"):
                    pid = str(row.get("paper_id", ""))
                    vec = row.get("vector")
                    if pid and vec is not None:
                        vectors[pid] = [float(x) for x in vec]
    except Exception:
        pass

    # ── Classify research facets for each paper ──
    from scientra.research_facets import classify_paper_facets, compute_topic_facet_distribution, FACETS

    # Build full paper payloads with evidence for classification
    paper_map: dict[str, dict[str, Any]] = {}
    for p in papers:
        pid = p.get("paper_id", "")
        if pid:
            paper_map[pid] = p

    all_classified_papers: list[dict[str, Any]] = []
    for p in papers:
        pid = p.get("paper_id", "")
        if not pid:
            continue
        pp = _build_topic_paper_payload_for_cache(root, p)
        pp["research_facets"] = classify_paper_facets(pp)
        all_classified_papers.append(pp)

    # ── Build hierarchical facet-subtopic map ──
    clusters, facet_data = _build_facet_based_topics(all_classified_papers, vectors)
    relationships = _rebuild_relationships_for_clusters(clusters, vectors)

    # Add facet_distribution to each cluster
    for c in clusters:
        c["facet_distribution"] = compute_topic_facet_distribution(c.get("papers", []))

    # Build merged_topic_map (old_id -> parent_id)
    merged_map: dict[str, str] = {}
    for c in clusters:
        for st in c.get("subtopics", []):
            merged_map[st.get("cluster_id", "")] = c.get("cluster_id", "")

    # Count stats
    raw_count = len(clusters) + sum(len(c.get("subtopics", [])) for c in clusters)
    final_count = len(clusters)
    merged_count = sum(1 for c in clusters if c.get("is_merged"))

    cache = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(papers),
        "source_fingerprint": compute_source_fingerprint(root),
        "random_seed": RANDOM_SEED,
        "view_mode_default": "facet",
        "facet_groups": [_build_facet_group_light(fg) for fg in facet_data],
        "topics": [_build_topic_payload_light(c) for c in clusters],
        "clusters": [_build_topic_payload_light(c) for c in clusters],
        "relationships": relationships,
        "merged_topic_map": merged_map,
        "stats": {
            "paper_count": len(papers),
            "facet_count": len(facet_data),
            "subtopic_count": len(clusters),
            "topic_count": len(clusters),
            "raw_cluster_count": raw_count,
            "final_topic_count": final_count,
            "merged_count": merged_count,
        },
    }

    _safe_write(cache_path, cache)
    return cache


def _empty_cache(root: Path) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_count": 0,
        "source_fingerprint": compute_source_fingerprint(root),
        "random_seed": RANDOM_SEED,
        "topics": [],
        "relationships": [],
        "merged_topic_map": {},
        "stats": {"raw_cluster_count": 0, "final_topic_count": 0, "merged_count": 0},
    }


def get_cache_status(root: Path) -> dict[str, Any]:
    """Return cache status info."""
    cache_path = root / CACHE_DIR_NAME / CACHE_FILE_NAME
    if not cache_path.exists():
        return {"exists": False, "message": "No cache file found. Run with --force to build."}

    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        fp_current = compute_source_fingerprint(root)
        fp_cached = cached.get("source_fingerprint", "")

        # Count covered papers
        facet_groups = cached.get("facet_groups", [])
        covered: set[str] = set()
        for fg in facet_groups:
            for st in fg.get("subtopics", []):
                for p in st.get("papers", []):
                    covered.add(p.get("paper_id", ""))
        paper_count = cached.get("paper_count", 0)
        missing_count = paper_count - len(covered) if paper_count > 0 else 0

        return {
            "exists": True,
            "valid": fp_current == fp_cached,
            "schema_version": cached.get("schema_version"),
            "generated_at": cached.get("generated_at"),
            "paper_count": paper_count,
            "covered_paper_count": len(covered),
            "missing_paper_count": max(0, missing_count),
            "facet_group_count": len(facet_groups),
            "subtopic_count": sum(len(fg.get("subtopics", [])) for fg in facet_groups),
            "source_fingerprint": fp_cached,
            "current_fingerprint": fp_current,
            "stats": cached.get("stats", {}),
            "cache_path": str(cache_path),
        }
    except Exception as e:
        return {"exists": True, "valid": False, "error": str(e), "cache_path": str(cache_path)}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Research Map Cache Builder")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true", help="Force rebuild cache")
    parser.add_argument("--status", action="store_true", help="Show cache status")
    args = parser.parse_args()

    if args.status:
        status = get_cache_status(args.root)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    print(f"Building Research Map cache...")
    cache = build_research_map_cache(args.root, force=args.force)
    stats = cache.get("stats", {})
    print(f"  Raw clusters: {stats.get('raw_cluster_count', '?')}")
    print(f"  Final topics: {stats.get('final_topic_count', '?')}")
    print(f"  Merged: {stats.get('merged_count', '?')}")
    print(f"  Relationships: {len(cache.get('relationships', []))}")
    print(f"  Fingerprint: {cache.get('source_fingerprint', '?')}")
    print(f"  Cache: {args.root / CACHE_DIR_NAME / CACHE_FILE_NAME}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
