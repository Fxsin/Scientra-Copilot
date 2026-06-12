"""
Figure Asset Builder — combines figure extraction + linking into FigureAsset records.

Phase 1: Rule-based figure type classification.
Output: 06_PDF_DataAssets/02_figures/{paper_id}/figures.json
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import Confidence, FigureAsset
from scientra.pdf_data_assets.figure_extractor import FigureExtractor
from scientra.pdf_data_assets.figure_linker import FigureLinker


# ── Figure type classification rules ──

FIGURE_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("gel_or_blot", ["sds-page", "western blot", "blot", "gel", "electrophoresis", "immunoblot", "coomassie"]),
    ("microscopy", ["fluorescence", "confocal", "microscop", "immunofluorescence", "tem", "sem", "cryo-em", "electron micrograph"]),
    ("bioassay_curve", ["bioassay", "feeding assay", "leaf disc", "diet overlay", "surface contamination"]),
    ("dose_response", ["dose-response", "dose response", "lc50", "ld50", "concentration-response", "mortality curve"]),
    ("binding_assay", ["binding", "competition", "ligand blot", "bbmv", "spr", "surface plasmon", "radiolabel"]),
    ("phylogeny", ["phylogenetic", "tree", "cladogram", "neighbor-joining", "maximum likelihood", "bootstrap"]),
    ("structure_model", ["structure", "cryo-em", "model", "domain", "ribbon", "cartoon", "pdb", "3d", "crystal structure"]),
    ("heatmap", ["heatmap", "heat map", "transcriptome", "rna-seq", "microarray", "expression profile", "clustering"]),
    ("bar_chart", ["bar chart", "bar graph", "histogram", "bars represent", "error bars"]),
    ("line_chart", ["line chart", "line graph", "time course", "kinetics", "growth curve"]),
    ("sequence_alignment", ["alignment", "sequence", "conserved", "residues", "weblogo", "consensus"]),
    ("domain_structure", ["domain organization", "domain architecture", "schematic", "diagram of", "domain I", "domain II"]),
    ("workflow_model", ["schematic", "workflow", "flowchart", "overview", "pipeline", "model depicting"]),
    ("table_like", ["table", "summary", "list of", "overview of", "comparison of"]),
]


class FigureAssetBuilder:
    """Builds FigureAsset records from extracted figures + reference links."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "02_figures"
        self.extractor = FigureExtractor(root)
        self.linker = FigureLinker(root)

    def build(self, paper_id: str, force: bool = False) -> list[FigureAsset]:
        """Build figure assets for a paper."""
        output_path = self.output_dir / paper_id / "figures.json"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        # Extract figures
        raw_figures = self.extractor.extract(paper_id)
        if not raw_figures:
            return []

        # Find references
        references = self.linker.find_references(paper_id)

        # Link
        linked_figures = self.linker.link_to_assets(paper_id, raw_figures, references)

        # Build FigureAssets
        timestamp = datetime.now(timezone.utc).isoformat()
        assets: list[FigureAsset] = []

        for i, fig in enumerate(linked_figures):
            caption = fig.get("caption", "")
            ref_sentences = fig.get("reference_sentences", [])

            # Source text: prefer caption, fall back to reference sentences
            source_text = caption if caption else " ".join(ref_sentences)[:2000]
            if not source_text.strip():
                source_text = fig.get("source_text", fig.get("figure_label", "unknown"))

            asset = FigureAsset(
                asset_id=f"{paper_id}:figure:{i:04d}",
                paper_id=paper_id,
                figure_id=f"{paper_id}_fig_{fig.get('figure_number', i)}",
                figure_label=fig.get("figure_label", "unknown"),
                figure_number=fig.get("figure_number", str(i)),
                caption=caption,
                caption_quality=fig.get("caption_quality", "none"),
                caption_source=fig.get("caption_source", "unknown"),
                source_text=source_text,
                source_file=f"03_Summary/raw_text/{paper_id}.txt",
                source_section=fig.get("mentioned_in_sections", ["unknown"])[0] if fig.get("mentioned_in_sections") else "unknown",
                image_path=None,
                panels=fig.get("panels", []),
                figure_type=self._classify_figure_type(caption, " ".join(ref_sentences)),
                mentioned_in_sections=fig.get("mentioned_in_sections", []),
                reference_sentences=ref_sentences,
                linked_result_assets=fig.get("linked_result_assets", []),
                linked_claim_assets=fig.get("linked_claim_assets", []),
                linked_evidence_ids=fig.get("linked_evidence_ids", []),
                confidence=Confidence(fig.get("confidence", "low")),
                linked_evidence_id=paper_id,
                linked_summary_section=None,
                extraction_method=fig.get("extraction_method", "reference_only") if fig.get("caption_source") == "reference_only" else "plain_text_caption",
                created_at=timestamp,
                metadata={
                    "extraction_method": fig.get("extraction_method", "regex_heuristic"),
                    "caption_quality": fig.get("caption_quality", "none"),
                    "caption_source": fig.get("caption_source", "unknown"),
                    "has_caption": bool(caption),
                    "has_references": len(ref_sentences) > 0,
                    "num_references": len(ref_sentences),
                },
            )
            assets.append(asset)

        self._write_output(output_path, assets)
        return assets

    def _classify_figure_type(self, caption: str, references: str) -> str:
        """Rule-based figure type classification."""
        combined = (caption + " " + references).lower()
        for ftype, keywords in FIGURE_TYPE_RULES:
            for kw in keywords:
                if kw in combined:
                    return ftype
        return "unknown"

    def _load_existing(self, path: Path) -> list[FigureAsset]:
        try:
            return [FigureAsset(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
        except Exception:
            return []

    def _write_output(self, path: Path, assets: list[FigureAsset]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.model_dump(mode="json", exclude_none=False) for a in assets]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_figure_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "figures.json"
        if not path.exists():
            return 0
        try:
            return len(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return 0
