"""Dataset Entity Extractor — extract entities from dataset headers and rows."""

from __future__ import annotations

import re
from typing import Any

ENTITY_PATTERNS: list[tuple[str, list[str]]] = [
    ("gene", [r"\b[A-Z][A-Z0-9]{1,8}\b", r"\bgene\b", r"gene.*symbol", r"gene.*id", r"gene.*name"]),
    ("protein", [r"\bprotein\b", r"\buniprot\b", r"\baccession\b", r"protein.*name"]),
    ("compound", [r"\bcompound\b", r"\bchemical\b", r"\btoxin\b", r"\binhibitor\b", r"\bdrug\b"]),
    ("strain", [r"\bstrain\b", r"\bisolate\b", r"\bserotype\b", r"\bbiotype\b"]),
    ("species", [r"\bspecies\b", r"\borganism\b", r"\bhost\b", r"\binsect\b", r"\bbacteria\b"]),
    ("sample", [r"\bsample\b", r"\breplicate\b", r"\btreatment\b", r"\bgroup\b", r"\bcondition\b"]),
    ("treatment", [r"\btreatment\b", r"\bdose\b", r"\bconcentration\b", r"\bexposure\b"]),
    ("pathway", [r"\bpathway\b", r"\bkegg\b", r"\bgo.*term\b", r"\breactome\b"]),
    ("primer", [r"\bprimer\b", r"\bforward\b", r"\breverse\b", r"\boligo\b"]),
    ("sequence", [r"\bsequence\b", r"\b[ACGT]{10,}\b", r"\b5'[ACGT]", r"\b3'[ACGT]"]),
    ("accession", [r"\baccession\b", r"\b[NMXP][MR]_?\d{4,}\b", r"\bgenbank\b"]),
    ("phenotype", [r"\bphenotype\b", r"\bmortality\b", r"\bgrowth\b", r"\bdisease\b", r"\bscore\b"]),
    ("method", [r"\bmethod\b", r"\bassay\b", r"\btechnique\b", r"\bprotocol\b"]),
    ("concentration", [r"\bconcentration\b", r"\bdose\b", r"\bLC\d{2}\b", r"\bLD\d{2}\b", r"\bEC\d{2}\b", r"\bIC\d{2}\b"]),
    ("timepoint", [r"\btime\b", r"\bhour\b", r"\bday\b", r"\bminute\b", r"\btimepoint\b", r"\bduration\b"]),
]


def extract_entities(
    headers: list[str], sample_rows: list[list[str]] | None = None,
    paper_id: str = "", dataset_id: str = "", asset_id: str = "",
) -> list[dict[str, Any]]:
    """Extract entities from dataset headers and sample rows."""
    entities: list[dict] = []
    sample_rows = sample_rows or []

    # Column-based extraction
    for col_idx, header in enumerate(headers):
        h_lower = header.lower()
        for etype, patterns in ENTITY_PATTERNS:
            for pat in patterns:
                if re.search(pat, h_lower, re.IGNORECASE):
                    # Extract values from this column
                    values = []
                    for ri, row in enumerate(sample_rows[:20]):
                        if col_idx < len(row):
                            v = str(row[col_idx]).strip()
                            if v and len(v) > 1:
                                values.append(v)
                    if values:
                        for v in values[:5]:
                            entities.append({
                                "entity_id": f"ent_{paper_id}_{dataset_id}_{len(entities):04d}",
                                "entity_type": etype, "entity_text": v,
                                "normalized_text": v.strip().upper(),
                                "paper_id": paper_id, "dataset_id": dataset_id,
                                "asset_id": asset_id, "sheet_name": "",
                                "row_index": ri if 'ri' in dir() else 0,
                                "column_name": header,
                                "value_context": {"column": header, "values_sample": values[:3]},
                                "confidence": 0.7,
                            })
                    break

    # Row-based extraction (gene-like patterns in any cell)
    gene_pattern = re.compile(r"^[A-Z][A-Z0-9]{1,8}$")
    for ri, row in enumerate(sample_rows[:30]):
        for ci, cell in enumerate(row):
            cell_str = str(cell).strip()
            if gene_pattern.match(cell_str) and ci < len(headers):
                col_name = headers[ci] if ci < len(headers) else ""
                if not any(kw in col_name.lower() for kw in ["id", "code", "lot", "batch"]):
                    entities.append({
                        "entity_id": f"ent_{paper_id}_{dataset_id}_{len(entities):04d}",
                        "entity_type": "gene" if len(cell_str) <= 8 else "unknown",
                        "entity_text": cell_str, "normalized_text": cell_str.upper(),
                        "paper_id": paper_id, "dataset_id": dataset_id,
                        "asset_id": asset_id, "sheet_name": "",
                        "row_index": ri, "column_name": col_name,
                        "value_context": {"row_index": ri},
                        "confidence": 0.5,
                    })

    return entities
