"""
Method Asset Builder — converts evidence methods into MethodAsset records.

Outputs: 06_PDF_DataAssets/04_methods/{paper_id}/methods.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import Confidence, MethodAsset
from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter


class MethodAssetBuilder:
    """Builds MethodAsset records from 03_Evidence methods."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "04_methods"
        self.evidence_adapter = EvidenceAdapter(root)

    def build(self, paper_id: str, force: bool = False) -> list[MethodAsset]:
        """Build method assets for a paper."""
        output_path = self.output_dir / paper_id / "methods.json"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        raw_methods = self.evidence_adapter.get_methods(paper_id)
        evidence_meta = self.evidence_adapter.get_evidence_meta(paper_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        assets: list[MethodAsset] = []

        for i, m in enumerate(raw_methods):
            if not isinstance(m, dict):
                continue
            name = str(m.get("name", "unknown")).strip()
            if len(name) < 2:
                continue

            asset = MethodAsset(
                asset_id=f"{paper_id}:method:{i:04d}",
                paper_id=paper_id,
                method_name=name,
                evidence_type=str(m.get("evidence_type", "unknown")),
                method_category=self._classify_category(name, m),
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(m.get("section", "unknown")),
                source_text=str(m.get("quote", name)),
                confidence=Confidence(str(m.get("confidence", "unknown"))),
                linked_evidence_id=f"{paper_id}:methods:{i}",
                linked_summary_section=str(m.get("section", "unknown")),
                parameters={},
                equipment=[],
                reagents=[],
                software=self._extract_software(name),
                linked_results=[],
                created_at=timestamp,
                metadata={
                    "evidence_type": str(m.get("evidence_type", "unknown")),
                    "source_index": i,
                    "title": evidence_meta.get("title", "unknown"),
                },
            )
            assets.append(asset)

        self._write_output(output_path, assets)
        return assets

    def _classify_category(self, name: str, raw: dict[str, Any]) -> str:
        """Heuristic category classification."""
        name_lower = name.lower()
        if any(kw in name_lower for kw in ["seq", "rna-seq", "pcr", "blot", "gel", "electrophoresis"]):
            return "wet-lab"
        if any(kw in name_lower for kw in ["microscop", "imaging", "stain", "histolog"]):
            return "wet-lab"
        if any(kw in name_lower for kw in ["assay", "elisa", "binding", "spr"]):
            return "wet-lab"
        if any(kw in name_lower for kw in ["bioinformatic", "pipeline", "software", "database", "comput"]):
            return "dry-lab"
        if any(kw in name_lower for kw in ["statistic", "model", "simulation", "machine learning"]):
            return "dry-lab"
        if any(kw in name_lower for kw in ["field", "trial", "greenhouse", "plot"]):
            return "field"
        if any(kw in name_lower for kw in ["clinical", "patient", "trial", "cohort"]):
            return "clinical"
        evidence_type = str(raw.get("evidence_type", "")).lower()
        if evidence_type in ("sequencing", "computational"):
            return "dry-lab"
        if evidence_type == "experiment":
            return "wet-lab"
        return "unknown"

    def _extract_software(self, name: str) -> list[str]:
        """Attempt to identify software mentions in method name."""
        software_keywords = [
            "kegg", "go", "blast", "bowtie", "star", "salmon", "deseq2",
            "edgeR", "limma", "gsea", "cytoscape", "prism", "graphpad",
            "imagej", "fiji", "r package", "python", "spss", "sas",
            "string", "david", "panther", "clusterprofiler", "metascape",
        ]
        found = []
        name_lower = name.lower()
        for kw in software_keywords:
            if kw in name_lower:
                found.append(kw)
        return found

    def _load_existing(self, path: Path) -> list[MethodAsset]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [MethodAsset(**item) for item in raw]
        except Exception:
            return []

    def _write_output(self, path: Path, assets: list[MethodAsset]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.model_dump(mode="json", exclude_none=False) for a in assets]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_method_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "methods.json"
        if not path.exists():
            return 0
        try:
            return len(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return 0
