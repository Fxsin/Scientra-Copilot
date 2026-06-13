"""
Table Asset Builder — combines table extraction + linking into TableAsset records.

Phase 2A: Rule-based table type classification. Caption + Reference extraction only.
No complex table structure parsing.

Output: 06_PDF_DataAssets/03_tables/{paper_id}/tables.json
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import Confidence, TableAsset
from scientra.pdf_data_assets.table_extractor import TableExtractor
from scientra.pdf_data_assets.table_linker import TableLinker
from scientra.pdf_data_assets.table_structure_extractor import TableStructureExtractor


# ── Table type classification rules (Phase 2A) ──

TABLE_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("toxicity_or_bioassay", [
        "lc50", "lc 50", "ld50", "ld 50", "mortality", "toxicity", "bioassay",
        "feeding assay", "leaf disc", "diet overlay", "surface contamination",
        "survival", "corrected mortality", "lethal concentration", "lethal dose",
        "median lethal", "insecticidal activity",
    ]),
    ("expression_or_production", [
        "expression", "purification", "yield", "production", "recombinant",
        "heterologous", "soluble", "insoluble", "inclusion body", "mg/l",
        "protein yield", "expression level", "expression vector",
        "production yield", "purification fold",
    ]),
    ("binding_or_affinity", [
        "binding", "affinity", "kd", "ka", "competition", "ligand blot",
        "bbmv", "brush border membrane", "spr", "surface plasmon",
        "radiolabel", "dissociation constant", "binding affinity",
        "competitive binding", "receptor binding",
    ]),
    ("omics_data", [
        "rna-seq", "rnaseq", "transcriptome", "proteome", "deg",
        "differentially expressed", "differential expression",
        "microarray", "gene expression profile", "fpkm", "rpkm",
        "fold change", "upregulated", "downregulated", "go term",
        "kegg", "enrichment", "cluster analysis",
    ]),
    ("gene_or_protein_list", [
        "gene ", "genes ", "protein list", "gene list", "accession",
        "locus tag", "gene id", "protein id", "orf", "open reading frame",
        "genomic", "gene name", "gene symbol", "gene family",
    ]),
    ("primer_or_plasmid", [
        "primer", "plasmid", "vector", "oligonucleotide", "construct",
        "restriction site", "cloning", "pcr primer", "forward primer",
        "reverse primer",
    ]),
    ("strain_or_sample", [
        "strain", "isolate", "sample", "specimen", "collection site",
        "geographic", "field-collected", "lab colony", "population",
        "accession number", "isolate name",
    ]),
    ("statistics_or_model", [
        "p-value", "p value", "regression", "anova", "model",
        "statistical", "correlation", "coefficient", "r-squared",
        "standard deviation", "standard error", "confidence interval",
        "odds ratio", "hazard ratio", "goodness of fit", "aic", "bic",
        "chi-square", "t-test", "mann-whitney", "kruskal-wallis",
    ]),
    ("phenotype_summary", [
        "phenotype", "morpholog", "growth rate", "body weight",
        "lesion", "symptom", "disease severity", "disease incidence",
        "efficacy", "potency", "activity against",
    ]),
    ("sequence_or_domain", [
        "sequence", "domain", "identity", "alignment", "conserved",
        "residues", "motif", "signal peptide", "transmembrane",
        "nucleotide sequence", "amino acid sequence", "homology",
    ]),
    ("supplementary_index", [
        "supplementary table", "supplementary information",
        "additional file", "supporting information",
        "see supplementary", "data not shown",
    ]),
]


class TableAssetBuilder:
    """Builds TableAsset records from extracted tables + reference links."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "03_tables"
        self.extractor = TableExtractor(root)
        self.linker = TableLinker(root)
        self.structure_extractor = TableStructureExtractor(root)

    def build(self, paper_id: str, force: bool = False) -> list[TableAsset]:
        """Build table assets for a paper."""
        output_path = self.output_dir / paper_id / "tables.json"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        # Extract tables
        raw_tables = self.extractor.extract(paper_id)
        if not raw_tables:
            return []

        # Find references
        references = self.linker.find_references(paper_id)

        # Link
        linked_tables = self.linker.link_to_assets(paper_id, raw_tables, references)

        # Build TableAssets
        timestamp = datetime.now(timezone.utc).isoformat()
        assets: list[TableAsset] = []

        for i, tbl in enumerate(linked_tables):
            caption = tbl.get("caption", "")
            ref_sentences = tbl.get("reference_sentences", [])

            # Source text: prefer caption, fall back to reference sentences
            source_text = caption if caption else " ".join(ref_sentences)[:2000]
            if not source_text.strip():
                source_text = tbl.get("source_text", tbl.get("table_label", "unknown"))

            # Classify table type
            table_type = self._classify_table_type(caption, " ".join(ref_sentences))

            # Phase 2B: Attempt structure extraction if caption exists
            structure_result: dict[str, Any] | None = None
            table_number = tbl.get("table_number", str(i))
            if caption:
                structure_result = self.structure_extractor.extract_structure(
                    paper_id, table_number, caption
                )
            elif source_text and source_text != tbl.get("table_label", "unknown"):
                # Try with source_text as caption fallback
                structure_result = self.structure_extractor.extract_structure(
                    paper_id, table_number, source_text[:500]
                )

            # Build structure fields
            if structure_result:
                struct_status = structure_result.get("structure_status", "caption_only")
                struct_cols = structure_result.get("structured_columns", [])
                struct_rows = structure_result.get("structured_rows", [])
                struct_confidence = structure_result.get("structure_confidence", "none")
                struct_method = structure_result.get("structure_extraction_method", "unavailable")
                struct_notes = structure_result.get("structure_notes", [])
                raw_tbl_text = structure_result.get("raw_table_text")
            else:
                struct_status = "caption_only"
                struct_cols = []
                struct_rows = []
                struct_confidence = "none"
                struct_method = "unavailable"
                struct_notes = []
                raw_tbl_text = None

            asset = TableAsset(
                asset_id=f"{paper_id}:table:{i:04d}",
                paper_id=paper_id,
                table_id=f"{paper_id}_tbl_{table_number}",
                table_label=tbl.get("table_label", "unknown"),
                table_number=table_number,
                caption=caption,
                source_text=source_text,
                source_file=f"03_Summary/raw_text/{paper_id}.txt",
                source_section=tbl.get("mentioned_in_sections", ["unknown"])[0] if tbl.get("mentioned_in_sections") else "unknown",
                table_type=table_type,
                mentioned_in_sections=tbl.get("mentioned_in_sections", []),
                reference_sentences=ref_sentences,
                linked_result_assets=tbl.get("linked_result_assets", []),
                linked_claim_assets=tbl.get("linked_claim_assets", []),
                linked_evidence_ids=tbl.get("linked_evidence_ids", []),
                confidence=Confidence(tbl.get("confidence", "low")),
                linked_evidence_id=paper_id,
                linked_summary_section=None,
                extraction_method=tbl.get("extraction_method", "reference_only"),
                caption_quality=tbl.get("caption_quality", "none"),
                caption_source=tbl.get("caption_source", "unknown"),
                structure_status=struct_status,
                structured_rows=struct_rows[:100],  # cap rows for safety
                structured_columns=struct_cols,
                raw_table_text=raw_tbl_text,
                structure_confidence=struct_confidence,
                structure_extraction_method=struct_method,
                structure_notes=struct_notes[:10],
                created_at=timestamp,
                metadata={
                    "extraction_method": tbl.get("extraction_method", "regex_heuristic"),
                    "caption_quality": tbl.get("caption_quality", "none"),
                    "caption_source": tbl.get("caption_source", "unknown"),
                    "has_caption": bool(caption),
                    "has_references": len(ref_sentences) > 0,
                    "num_references": len(ref_sentences),
                    "table_type": table_type,
                    "structure_status": struct_status,
                    "structure_confidence": struct_confidence,
                    "structure_extraction_method": struct_method,
                    "row_count": len(struct_rows),
                    "column_count": len(struct_cols),
                },
            )
            assets.append(asset)

        self._write_output(output_path, assets)
        return assets

    def _classify_table_type(self, caption: str, references: str) -> str:
        """Rule-based table type classification based on caption + reference text."""
        combined = (caption + " " + references).lower()
        for ttype, keywords in TABLE_TYPE_RULES:
            for kw in keywords:
                if kw in combined:
                    return ttype
        return "unknown"

    def _load_existing(self, path: Path) -> list[TableAsset]:
        try:
            return [TableAsset(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
        except Exception:
            return []

    def _write_output(self, path: Path, assets: list[TableAsset]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.model_dump(mode="json", exclude_none=False) for a in assets]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_table_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "tables.json"
        if not path.exists():
            return 0
        try:
            return len(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return 0
