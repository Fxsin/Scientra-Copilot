"""Figure Evidence Classifier — classify figure evidence type from captions, context, and metadata.

Uses keyword-based rules to classify figures into evidence types without requiring AI.
This is the default mode when no API key is configured.

Evidence types:
  microscopy, western_blot, gel_image, survival_curve, bioassay,
  binding_assay, expression_analysis, heatmap, volcano_plot,
  phylogeny, structure_model, statistical_plot, workflow_diagram, unknown
"""

from __future__ import annotations

from typing import Any

# ── Evidence type definitions with keyword patterns ──

EVIDENCE_TYPE_PATTERNS: list[tuple[str, list[str], list[str]]] = [
    # (type, high_confidence_keywords, low_confidence_keywords)
    (
        "microscopy",
        [
            "microscop", "confocal", "fluorescence microscop", "tem image",
            "sem image", "electron microscop", "immunofluorescence",
            "brightfield", "phase contrast", "confocal laser scanning",
            "transmission electron", "scanning electron", "light microscop",
            "fluorescent microscop", "live cell imaging", "time-lapse",
        ],
        ["image", "morpholog", "cellular localiz", "subcellular"],
    ),
    (
        "western_blot",
        [
            "western blot", "immunoblot", "western blotting",
            "immunoblotting", "protein blot", "wb analysis",
        ],
        ["band", "kda", "protein expression", "protein level"],
    ),
    (
        "gel_image",
        [
            "gel electrophores", "sds-page", "sds page", "agarose gel",
            "polyacrylamide gel", "dna gel", "rna gel", "native gel",
            "gel image", "gel staining", "coomassie", "ethidium bromide",
            "gel shift", "emsa", "electrophoretic mobility",
        ],
        ["gel", "electrophores", "ladder", "molecular weight"],
    ),
    (
        "survival_curve",
        [
            "survival curve", "kaplan-meier", "kaplan meier",
            "survival analys", "survival probability", "survival rate",
            "survival plot", "mortality curve", "longevity", "lifespan",
            "cumulative survival", "percent survival",
        ],
        ["survival", "mortality", "time", "days post"],
    ),
    (
        "bioassay",
        [
            "bioassay", "lc50", "ld50", "ec50", "ic50", "dose-response",
            "dose response", "concentration-response", "mortality assay",
            "toxicity assay", "inhibition curve", "growth inhibition",
            "feeding assay", "diet bioassay", "surface contamination",
        ],
        ["assay", "concentration", "dose", "mortality", "inhibition"],
    ),
    (
        "binding_assay",
        [
            "binding assay", "binding affinity", "kd value", "spr",
            "surface plasmon resonance", "isothermal titration",
            "itc", "pull-down", "pull down", "co-immunoprecipitation",
            "co-ip", "yeast two-hybrid", "y2h", "biolayer interferometry",
            "mst", "microscale thermophoresis",
        ],
        ["binding", "affinity", "interaction", "ligand", "receptor binding"],
    ),
    (
        "expression_analysis",
        [
            "expression analys", "gene expression", "rt-pcr", "rt pcr",
            "qpcr", "rt-qpcr", "rna-seq", "rna seq", "transcriptom",
            "microarray", "heat ?map", "expression profile",
            "differential expression", "fpkm", "rpkm", "transcript level",
            "rna level", "mrna expression", "northern blot",
        ],
        ["expression", "transcript", "fold change", "upregulat", "downregulat"],
    ),
    (
        "heatmap",
        [
            "heatmap", "heat map", "clustered heatmap", "expression heatmap",
            "correlation heatmap", "hierarchical clustering",
        ],
        ["cluster", "color scale", "row", "column", "z-score"],
    ),
    (
        "volcano_plot",
        [
            "volcano plot", "volcano", "ma plot", "ma-plot",
        ],
        ["log2 fold", "p-value", "fdr", "differential"],
    ),
    (
        "phylogeny",
        [
            "phylogen", "phylogenetic tree", "cladogram", "neighbor-joining",
            "maximum likelihood tree", "bayesian tree", "bootstrap",
            "evolutionary tree", "dendrogram", "molecular phylogen",
            "sequence alignment", "multiple sequence alignment",
        ],
        ["tree", "bootstrap", "branch", "clade", "node"],
    ),
    (
        "structure_model",
        [
            "structure model", "crystal structure", "nmr structure",
            "homology model", "protein structure", "3d structure",
            "molecular docking", "docking model", "ribbon diagram",
            "cartoon representation", "predicted structure", "alphafold",
            "x-ray crystallograph", "cryo-em", "cryo em",
        ],
        ["structure", "model", "docking", "conformation", "domain"],
    ),
    (
        "statistical_plot",
        [
            "bar chart", "bar graph", "scatter plot", "box plot", "boxplot",
            "violin plot", "histogram", "pie chart", "line graph",
            "correlation plot", "regression", "linear regression",
            "anova", "t-test", "statistical analys", "error bar",
            "standard deviation", "standard error", "mean ±",
        ],
        ["plot", "graph", "chart", "error", "significant"],
    ),
    (
        "workflow_diagram",
        [
            "workflow", "schematic", "diagram", "flow chart", "flowchart",
            "experimental design", "study design", "protocol overview",
            "graphical abstract", "model figure", "illustration",
            "cartoon", "overview", "summary figure",
        ],
        ["schema", "overview", "design", "protocol", "step"],
    ),
]


def classify_evidence_type(
    caption: str = "",
    body_mentions: list[dict[str, Any]] | None = None,
    asset_filename: str = "",
) -> dict[str, Any]:
    """Classify figure evidence type based on caption, body mentions, and filename.

    Args:
        caption: Figure caption text.
        body_mentions: List of body citation mentions for this figure.
        asset_filename: The asset filename (additional signal).

    Returns:
        dict with keys:
            evidence_type: str — best match from evidence types
            subtype: str — more specific subtype if detectable
            confidence: float — 0.0 to 1.0
            reason: str — brief explanation
            alternatives: list[str] — other possible types
    """
    # Collect all searchable text
    search_text = caption.lower() + " "
    if body_mentions:
        for m in body_mentions:
            search_text += m.get("sentence", "").lower() + " "
            search_text += m.get("context_before", "").lower() + " "
            search_text += m.get("context_after", "").lower() + " "
    search_text += asset_filename.lower()

    # Normalize separators so filename patterns like "western_blot" match keywords like "western blot"
    import re
    search_text = re.sub(r"[_\-.]", " ", search_text)

    best_type = "unknown"
    best_confidence = 0.0
    best_reason = ""
    alternatives: list[str] = []

    for etype, high_kw, low_kw in EVIDENCE_TYPE_PATTERNS:
        high_matches = [kw for kw in high_kw if kw.lower() in search_text]
        low_matches = [kw for kw in low_kw if kw.lower() in search_text]

        if high_matches:
            # High confidence keywords found
            confidence = min(0.70 + 0.15 * len(high_matches), 0.98)
            reason = f"Matched keywords: {', '.join(high_matches[:5])}"
        elif len(low_matches) >= 2:
            # Multiple low confidence keywords
            confidence = min(0.40 + 0.10 * len(low_matches), 0.65)
            reason = f"Partial match: {', '.join(low_matches[:5])}"
        elif len(low_matches) == 1:
            confidence = 0.30
            reason = f"Weak match: {low_matches[0]}"
        else:
            continue

        if confidence > best_confidence:
            if best_type != "unknown" and best_confidence > 0.3:
                alternatives.append(best_type)
            best_type = etype
            best_confidence = confidence
            best_reason = reason
        elif confidence > 0.3:
            alternatives.append(etype)

    # Detect subtype for certain categories
    subtype = _detect_subtype(best_type, search_text)

    return {
        "evidence_type": best_type,
        "subtype": subtype,
        "confidence": round(best_confidence, 2),
        "reason": best_reason,
        "alternatives": alternatives[:3],
    }


def _detect_subtype(evidence_type: str, search_text: str) -> str:
    """Detect specific subtype within an evidence type."""
    subtype_map = {
        "microscopy": [
            ("confocal", "confocal"),
            ("electron", "electron microscopy"),
            ("fluorescence", "fluorescence microscopy"),
            ("live_cell", "live cell imaging"),
            ("tem", "transmission electron microscopy"),
            ("sem", "scanning electron microscopy"),
        ],
        "western_blot": [
            ("quantitative", "quantitative western blot"),
            ("semi_quantitative", "semi-quantitative"),
        ],
        "gel_image": [
            ("sds_page", "SDS-PAGE"),
            ("agarose", "agarose gel"),
            ("emsa", "EMSA/gel shift"),
            ("native", "native gel"),
        ],
        "bioassay": [
            ("lc50", "LC50 determination"),
            ("ld50", "LD50 determination"),
            ("ec50", "EC50 determination"),
            ("ic50", "IC50 determination"),
            ("dose_response", "dose-response"),
            ("feeding", "feeding assay"),
        ],
        "expression_analysis": [
            ("qpcr", "qPCR"),
            ("rna_seq", "RNA-seq"),
            ("microarray", "microarray"),
            ("northern", "northern blot"),
        ],
        "phylogeny": [
            ("ml_tree", "maximum likelihood"),
            ("bayesian", "bayesian"),
            ("nj_tree", "neighbor-joining"),
        ],
        "structure_model": [
            ("crystal", "X-ray crystallography"),
            ("cryo_em", "cryo-EM"),
            ("docking", "molecular docking"),
            ("alphafold", "AlphaFold prediction"),
        ],
    }

    if evidence_type in subtype_map:
        for key, label in subtype_map[evidence_type]:
            if key in search_text:
                return label

    return ""
