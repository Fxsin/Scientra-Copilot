"""Dataset Schema Inferer — classify dataset type from headers and sample data."""

from __future__ import annotations

import re
from typing import Any

TYPE_PATTERNS: list[tuple[str, list[str], str]] = [
    ("differential_expression", ["log2fc", "logfc", "padj", "pvalue", "fdr", "baseMean", "lfcse", "stat"], "Differential expression"),
    ("gene_expression", ["fpkm", "rpkm", "tpm", "counts", "gene symbol", "gene id", "expression"], "Gene expression"),
    ("proteomics", ["protein", "peptide", "accession", "uniprot", "intensity", "spectral count"], "Proteomics"),
    ("pathway_enrichment", ["pathway", "go term", "kegg", "enrichment score", "gene ratio", "nes"], "Pathway enrichment"),
    ("sample_metadata", ["sample id", "treatment", "condition", "group", "replicate", "tissue", "cell line"], "Sample metadata"),
    ("primer_table", ["primer", "sequence", "forward", "reverse", "product size", "amplicon", "tm"], "Primer table"),
    ("strain_table", ["strain", "isolate", "genotype", "serotype", "biotype"], "Strain table"),
    ("phenotype_table", ["phenotype", "mortality", "growth", "weight", "length", "score", "disease index"], "Phenotype"),
    ("bioassay", ["mortality", "corrected mortality", "total", "dead", "alive", "inhibition"], "Bioassay"),
    ("lc50", ["lc50", "ld50", "ec50", "ic50", "95% ci", "lethal concentration"], "LC50/EC50"),
    ("mortality", ["mortality", "dead", "alive", "survival rate", "mortality rate"], "Mortality"),
    ("survival", ["survival", "kaplan", "meier", "hazard ratio", "time", "event", "censored"], "Survival"),
    ("binding_assay", ["kd", "binding affinity", "spr", "itc", "pull-down", "co-ip"], "Binding assay"),
    ("statistical_result", ["p value", "statistic", "t-test", "anova", "correlation", "effect size"], "Statistical"),
    ("taxonomy", ["phylum", "class", "order", "family", "genus", "species", "otu", "16s", "its"], "Taxonomy"),
    ("method_parameters", ["parameter", "value", "setting", "instrument", "column", "gradient", "temperature"], "Method params"),
    ("source_data", ["source data", "raw data", "underlying data", "data behind"], "Source data"),
    ("supplementary_index", ["supplementary", "table s", "figure s", "file name", "description"], "Supplementary index"),
]


def infer_schema(headers: list[str], sample_rows: list[list[str]] | None = None, caption: str = "") -> dict[str, Any]:
    search = " ".join(h.lower() for h in headers) + " " + caption.lower()
    if sample_rows:
        for row in sample_rows[:10]:
            search += " " + " ".join(str(c).lower() for c in row)
    search = re.sub(r"[_\-.]", " ", search)

    best_type = "unknown"
    best_conf = 0.0
    best_reason = ""
    key_cols: dict[str, list[str]] = {}

    for ttype, keywords, desc in TYPE_PATTERNS:
        matches = [kw for kw in keywords if kw.lower() in search]
        if matches:
            conf = min(0.7 + 0.05 * len(matches), 0.95)
            reason = f"Matched: {', '.join(matches[:5])}"
            if conf > best_conf:
                best_type = ttype
                best_conf = conf
                best_reason = reason
                key_cols = {kw: [h for h in headers if kw.lower() in h.lower()] for kw in matches[:5] if any(kw.lower() in h.lower() for h in headers)}

    return {
        "dataset_id": "", "paper_id": "", "asset_id": "",
        "dataset_type": best_type, "confidence": round(best_conf, 2),
        "key_columns": key_cols, "sheet_schemas": [],
        "reason": best_reason or "No matching patterns",
    }
