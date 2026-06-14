"""Table Schema Inferer — classify table type from headers, captions, and sample data.

Supports 17 table types:
  differential_expression, gene_expression, proteomics, metabolomics,
  sample_metadata, primer_table, strain_table, phenotype_table,
  bioassay_table, survival_table, lc50_table, statistical_result,
  pathway_enrichment, taxonomy_table, method_parameter_table,
  supplementary_index, unknown
"""

from __future__ import annotations

import re
from typing import Any

# ── Table type definitions with header keyword patterns ──

TABLE_TYPE_PATTERNS: list[tuple[str, list[str], list[str], str]] = [
    # (type_name, high_confidence_headers, medium_confidence_headers, description)
    (
        "differential_expression",
        ["log2fc", "logfc", "log2 fold", "padj", "pvalue", "p_value", "fdr", "baseMean",
         "lfcse", "stat", "fold change", "adj pval", "adjusted p"],
        ["gene", "expression", "fc", "p ", "degs", "differentially expressed"],
        "Differential expression analysis results",
    ),
    (
        "gene_expression",
        ["gene id", "gene symbol", "gene name", "fpkm", "rpkm", "tpm", "counts",
         "expression", "transcript id", "probe id"],
        ["expression", "count", "gene", "transcript", "normalized"],
        "Gene expression data (FPKM/RPKM/TPM/counts)",
    ),
    (
        "proteomics",
        ["protein id", "protein name", "accession", "uniprot", "peptide",
         "spectral count", "ms/ms", "intensity", "protein group", "plgs", "maxquant"],
        ["protein", "peptide", "spectra", "intensity", "abundance"],
        "Proteomics data",
    ),
    (
        "metabolomics",
        ["metabolite", "compound", "m/z", "retention time", "rt", "mass",
         "metabolomics", "kegg id", "hmdb", "pubchem", "pathway"],
        ["metabolite", "compound", "mass", "ion", "adduct"],
        "Metabolomics data",
    ),
    (
        "sample_metadata",
        ["sample id", "sample name", "treatment", "condition", "group",
         "replicate", "batch", "time point", "tissue", "cell line", "strain",
         "genotype", "age", "sex", "source", "collection date"],
        ["sample", "group", "condition", "treatment", "metadata"],
        "Sample metadata table",
    ),
    (
        "primer_table",
        ["primer", "sequence", "forward", "reverse", "oligo", "product size",
         "amplicon", "tm", "melting temp", "gc content", "target gene",
         "primer name", "fwd", "rev", "5'", "3'"],
        ["primer", "sequence", "oligo", "pcr"],
        "Primer/oligo sequence table",
    ),
    (
        "strain_table",
        ["strain", "isolate", "genotype", "source", "origin", "collection",
         "serotype", "biotype", "pathovar", "host", "plasmid"],
        ["strain", "isolate", "genotype", "mutant"],
        "Bacterial/fungal strain table",
    ),
    (
        "phenotype_table",
        ["phenotype", "trait", "mortality", "weight", "length", "growth",
         "germination", "survival rate", "disease index", "severity",
         "lesion", "symptom", "score"],
        ["phenotype", "trait", "mortality", "growth"],
        "Phenotype observation table",
    ),
    (
        "bioassay_table",
        ["mortality", "corrected mortality", "concentration", "dose",
         "treatment", "replicate", "total", "dead", "alive",
         "inhibition rate", "growth inhibition"],
        ["bioassay", "mortality", "dose", "concentration"],
        "Bioassay results table",
    ),
    (
        "survival_table",
        ["survival", "kaplan", "meier", "hazard ratio", "median survival",
         "time", "event", "censored", "alive", "dead", "days",
         "survival probability", "log-rank", "cox"],
        ["survival", "time", "event", "censored"],
        "Survival analysis table",
    ),
    (
        "lc50_table",
        ["lc50", "lc50", "ld50", "ld50", "ec50", "ec50", "ic50", "ic50",
         "95% ci", "confidence interval", "slope", "intercept",
         "lethal concentration", "effective concentration"],
        ["lc50", "ld50", "ec50", "ic50", "lethal", "mortality"],
        "LC50/LD50/EC50 determination table",
    ),
    (
        "statistical_result",
        ["p value", "p-value", "pvalue", "fdr", "q value", "statistic",
         "t-test", "anova", "chi", "correlation", "r value",
         "significance", "df", "effect size", "cohen", "eta"],
        ["p ", "statistic", "test", "significance", "correlation"],
        "Statistical test results table",
    ),
    (
        "pathway_enrichment",
        ["pathway", "go term", "kegg", "enrichment", "gene ratio",
         "bg ratio", "enrichment score", "nes", "gene set",
         "ontology", "bp ", "cc ", "mf ", "biological process",
         "cellular component", "molecular function"],
        ["pathway", "enrichment", "go ", "ontology", "kegg"],
        "Pathway/GO enrichment table",
    ),
    (
        "taxonomy_table",
        ["taxonomy", "phylum", "class", "order", "family", "genus",
         "species", "kingdom", "otu", "asv", "16s", "its",
         "abundance", "relative abundance", "bacteria", "fungi"],
        ["taxonomy", "phylum", "species", "abundance", "otu"],
        "Taxonomy/microbiome table",
    ),
    (
        "method_parameter_table",
        ["parameter", "value", "setting", "configuration", "instrument",
         "column", "gradient", "flow rate", "temperature", "voltage",
         "wavelength", "buffer", "concentration", "ph"],
        ["parameter", "setting", "method", "instrument"],
        "Method parameter table",
    ),
    (
        "supplementary_index",
        ["supplementary", "table s", "figure s", "supplementary table",
         "supplementary figure", "suppl", "file name", "description",
         "appendix"],
        ["supplementary", "appendix", "file", "description"],
        "Supplementary material index",
    ),
]


def infer_table_schema(
    headers: list[str],
    caption: str = "",
    sample_rows: list[list[str]] | None = None,
    body_mentions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Infer table type from headers, caption, and sample data.

    Args:
        headers: List of column header strings.
        caption: Table caption text.
        sample_rows: Sample data rows.
        body_mentions: Body citation mentions.

    Returns:
        Schema dict with table_type, confidence, key_columns, reason.
    """
    # Build search text
    search_text = " ".join(h.lower() for h in headers) + " "
    search_text += caption.lower() + " "

    if sample_rows:
        for row in sample_rows[:5]:
            search_text += " ".join(str(c).lower() for c in row) + " "

    if body_mentions:
        for m in body_mentions:
            search_text += m.get("sentence", "").lower() + " "

    # Normalize
    search_text = re.sub(r"[_\-.]", " ", search_text)

    best_type = "unknown"
    best_confidence = 0.0
    best_reason = ""
    key_columns: dict[str, list[str]] = {}

    for ttype, high_kw, med_kw, description in TABLE_TYPE_PATTERNS:
        high_matches = [kw for kw in high_kw if kw.lower() in search_text]
        med_matches = [kw for kw in med_kw if kw.lower() in search_text]

        if high_matches:
            confidence = min(0.70 + 0.10 * len(high_matches), 0.95)
            reason = f"Matched headers: {', '.join(high_matches[:5])}"
        elif len(med_matches) >= 3:
            confidence = min(0.50 + 0.08 * len(med_matches), 0.70)
            reason = f"Partial match: {', '.join(med_matches[:5])}"
        elif len(med_matches) >= 1:
            confidence = 0.35
            reason = f"Weak match: {med_matches[0]}"
        else:
            continue

        if confidence > best_confidence:
            best_type = ttype
            best_confidence = confidence
            best_reason = reason
            # Detect key columns
            key_columns = _detect_key_columns(ttype, headers, high_matches)

    return {
        "table_id": "",
        "table_type": best_type,
        "confidence": round(best_confidence, 2),
        "key_columns": key_columns,
        "reason": best_reason or "No matching patterns found.",
    }


def _detect_key_columns(
    table_type: str, headers: list[str], matched_keywords: list[str],
) -> dict[str, list[str]]:
    """Identify key columns based on table type and headers."""
    key_cols: dict[str, list[str]] = {}

    type_keywords = {
        "differential_expression": ["gene", "log2fc", "padj", "pvalue", "fold change"],
        "gene_expression": ["gene", "expression", "fpkm", "tpm", "count"],
        "bioassay_table": ["concentration", "mortality", "treatment", "replicate"],
        "lc50_table": ["lc50", "95% ci", "slope", "mortality"],
        "survival_table": ["time", "survival", "hazard", "event"],
        "primer_table": ["primer", "sequence", "product size", "tm"],
        "sample_metadata": ["sample", "treatment", "condition", "group", "replicate"],
        "pathway_enrichment": ["pathway", "go term", "enrichment", "p value"],
    }

    target_keys = type_keywords.get(table_type, [])
    for target in target_keys:
        found = [h for h in headers if target.lower() in h.lower()]
        if found:
            key_cols[target] = found

    return key_cols
