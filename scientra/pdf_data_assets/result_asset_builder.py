"""
Result Asset Builder — converts key_results, core_findings, discussion_points
into ResultAsset records.

Outputs: 06_PDF_DataAssets/05_results/{paper_id}/results.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import Confidence, ResultAsset
from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter


class ResultAssetBuilder:
    """Builds ResultAsset records from 03_Evidence key_results, core_findings, discussion_points."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "05_results"
        self.evidence_adapter = EvidenceAdapter(root)

    def build(self, paper_id: str, force: bool = False) -> list[ResultAsset]:
        """Build result assets for a paper."""
        output_path = self.output_dir / paper_id / "results.json"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        assets: list[ResultAsset] = []
        timestamp = datetime.now(timezone.utc).isoformat()
        evidence_meta = self.evidence_adapter.get_evidence_meta(paper_id)

        # From key_results
        key_results = self.evidence_adapter.get_key_results(paper_id)
        for i, kr in enumerate(key_results):
            if not isinstance(kr, dict):
                continue
            result_text = str(kr.get("result", "")).strip()
            if len(result_text) < 15:
                continue
            asset = ResultAsset(
                asset_id=f"{paper_id}:result:{i:04d}",
                paper_id=paper_id,
                result_text=result_text,
                measured_variable=str(kr.get("measured_variable", "unknown")),
                direction=str(kr.get("direction", "unknown")),
                condition=str(kr.get("condition", "unknown")),
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(kr.get("section", "unknown")),
                source_text=result_text,
                confidence=Confidence(str(kr.get("confidence", "unknown"))),
                linked_evidence_id=f"{paper_id}:key_results:{i}",
                linked_summary_section=str(kr.get("section", "unknown")),
                linked_method_id=None,
                linked_figure_ids=[],
                linked_table_ids=[],
                created_at=timestamp,
                metadata={
                    "source_field": "key_results",
                    "source_index": i,
                    "title": evidence_meta.get("title", "unknown"),
                },
            )
            assets.append(asset)

        # From core_findings (continue index)
        offset = len(key_results)
        core_findings = self.evidence_adapter.get_core_findings(paper_id)
        for j, cf in enumerate(core_findings):
            if not isinstance(cf, dict):
                continue
            finding_text = str(cf.get("finding", "")).strip()
            if len(finding_text) < 15:
                continue
            asset = ResultAsset(
                asset_id=f"{paper_id}:result:{offset + j:04d}",
                paper_id=paper_id,
                result_text=finding_text,
                measured_variable="unknown",
                direction="descriptive",
                condition="unknown",
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(cf.get("section", "unknown")),
                source_text=finding_text,
                confidence=Confidence(str(cf.get("confidence", "unknown"))),
                linked_evidence_id=f"{paper_id}:core_findings:{j}",
                linked_summary_section=str(cf.get("section", "unknown")),
                linked_method_id=None,
                linked_figure_ids=[],
                linked_table_ids=[],
                created_at=timestamp,
                metadata={
                    "source_field": "core_findings",
                    "source_index": j,
                    "title": evidence_meta.get("title", "unknown"),
                },
            )
            assets.append(asset)

        # From discussion_points (continue index)
        offset2 = offset + len(core_findings)
        discussion_points = self.evidence_adapter.get_discussion_points(paper_id)
        for k, dp in enumerate(discussion_points):
            if not isinstance(dp, dict):
                continue
            point_text = str(dp.get("point", "")).strip()
            if len(point_text) < 15:
                continue
            asset = ResultAsset(
                asset_id=f"{paper_id}:result:{offset2 + k:04d}",
                paper_id=paper_id,
                result_text=point_text,
                measured_variable="unknown",
                direction="descriptive",
                condition="unknown",
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(dp.get("section", "unknown")),
                source_text=point_text,
                confidence=Confidence(str(dp.get("confidence", "unknown"))),
                linked_evidence_id=f"{paper_id}:discussion_points:{k}",
                linked_summary_section=str(dp.get("section", "unknown")),
                linked_method_id=None,
                linked_figure_ids=[],
                linked_table_ids=[],
                created_at=timestamp,
                metadata={
                    "source_field": "discussion_points",
                    "source_index": k,
                    "point_type": str(dp.get("type", "unknown")),
                    "title": evidence_meta.get("title", "unknown"),
                },
            )
            assets.append(asset)

        self._write_output(output_path, assets)
        return assets

    def _load_existing(self, path: Path) -> list[ResultAsset]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [ResultAsset(**item) for item in raw]
        except Exception:
            return []

    def _write_output(self, path: Path, assets: list[ResultAsset]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.model_dump(mode="json", exclude_none=False) for a in assets]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_result_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "results.json"
        if not path.exists():
            return 0
        try:
            return len(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return 0
