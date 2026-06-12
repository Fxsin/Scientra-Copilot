"""
Claim-Evidence Builder — builds ClaimAssets and EvidenceLinks from existing data.

Phase 0: text-based claim-evidence linking from core_findings, key_results,
discussion_points, and existing result_discussion_links.
Figure and table links are reserved for future phases.

Outputs: 06_PDF_DataAssets/07_claims_evidence/{paper_id}/claims_evidence.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import (
    ClaimAsset,
    Confidence,
    EvidenceLink,
)
from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter


class ClaimEvidenceBuilder:
    """Builds ClaimAssets and EvidenceLinks from 03_Evidence data."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "07_claims_evidence"
        self.evidence_adapter = EvidenceAdapter(root)

    def build(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        """Build claims and evidence links for a paper.

        Returns dict with 'claims' and 'evidence_links' keys.
        """
        output_path = self.output_dir / paper_id / "claims_evidence.json"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        timestamp = datetime.now(timezone.utc).isoformat()
        evidence_meta = self.evidence_adapter.get_evidence_meta(paper_id)

        claims: list[ClaimAsset] = []
        evidence_links: list[EvidenceLink] = []

        # ── Build claims from core_findings ──
        core_findings = self.evidence_adapter.get_core_findings(paper_id)
        for i, cf in enumerate(core_findings):
            if not isinstance(cf, dict):
                continue
            finding_text = str(cf.get("finding", "")).strip()
            if len(finding_text) < 15:
                continue
            claim = ClaimAsset(
                asset_id=f"{paper_id}:claim:{i:04d}",
                paper_id=paper_id,
                claim_text=finding_text,
                claim_type="finding",
                supporting_evidence=[],
                opposing_evidence=[],
                linked_result_ids=[],
                linked_figure_ids=[],
                linked_table_ids=[],
                citation_refs=self._extract_citations(finding_text),
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(cf.get("section", "unknown")),
                source_text=finding_text,
                confidence=Confidence(str(cf.get("confidence", "unknown"))),
                linked_evidence_id=f"{paper_id}:core_findings:{i}",
                linked_summary_section=str(cf.get("section", "unknown")),
                created_at=timestamp,
                metadata={
                    "source_field": "core_findings",
                    "source_index": i,
                    "title": evidence_meta.get("title", "unknown"),
                },
            )
            claims.append(claim)

        # ── Build claims from discussion_points ──
        offset = len(core_findings)
        discussion_points = self.evidence_adapter.get_discussion_points(paper_id)
        for j, dp in enumerate(discussion_points):
            if not isinstance(dp, dict):
                continue
            point_text = str(dp.get("point", "")).strip()
            if len(point_text) < 15:
                continue
            dp_type = str(dp.get("type", "interpretation"))
            claim_type = self._map_discussion_type(dp_type)
            claim = ClaimAsset(
                asset_id=f"{paper_id}:claim:{offset + j:04d}",
                paper_id=paper_id,
                claim_text=point_text,
                claim_type=claim_type,
                supporting_evidence=[],
                opposing_evidence=[],
                linked_result_ids=[],
                linked_figure_ids=[],
                linked_table_ids=[],
                citation_refs=self._extract_citations(point_text),
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(dp.get("section", "unknown")),
                source_text=point_text,
                confidence=Confidence(str(dp.get("confidence", "unknown"))),
                linked_evidence_id=f"{paper_id}:discussion_points:{j}",
                linked_summary_section=str(dp.get("section", "unknown")),
                created_at=timestamp,
                metadata={
                    "source_field": "discussion_points",
                    "source_index": j,
                    "point_type": dp_type,
                    "title": evidence_meta.get("title", "unknown"),
                },
            )
            claims.append(claim)

        # ── Build claims from existing claims list ──
        offset2 = offset + len(discussion_points)
        raw_claims = self.evidence_adapter.get_claims(paper_id)
        for k, rc in enumerate(raw_claims):
            if not isinstance(rc, dict):
                continue
            claim_text = str(rc.get("claim", rc.get("text", ""))).strip()
            if len(claim_text) < 15:
                continue
            claim = ClaimAsset(
                asset_id=f"{paper_id}:claim:{offset2 + k:04d}",
                paper_id=paper_id,
                claim_text=claim_text,
                claim_type=str(rc.get("type", "unknown")),
                supporting_evidence=[],
                opposing_evidence=[],
                linked_result_ids=[],
                linked_figure_ids=[],
                linked_table_ids=[],
                citation_refs=self._extract_citations(claim_text),
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(rc.get("section", "unknown")),
                source_text=claim_text,
                confidence=Confidence(str(rc.get("confidence", "unknown"))),
                linked_evidence_id=f"{paper_id}:claims:{k}",
                linked_summary_section=str(rc.get("section", "unknown")),
                created_at=timestamp,
                metadata={
                    "source_field": "claims",
                    "source_index": k,
                    "title": evidence_meta.get("title", "unknown"),
                },
            )
            claims.append(claim)

        # ── Build evidence links from result_discussion_links ──
        rd_links = self.evidence_adapter.get_result_discussion_links(paper_id)
        for li, rdl in enumerate(rd_links):
            if not isinstance(rdl, dict):
                continue
            result_idx = rdl.get("result_index", -1)
            discussion_idx = rdl.get("discussion_index", -1)
            if result_idx < 0 or discussion_idx < 0:
                continue
            link = EvidenceLink(
                link_id=f"{paper_id}:ev_link:{li:04d}",
                paper_id=paper_id,
                source_asset_id=f"{paper_id}:result:{result_idx:04d}",
                target_asset_id=f"{paper_id}:claim:{discussion_idx:04d}",
                link_type=str(rdl.get("link_type", "interprets")),
                basis=str(rdl.get("basis", "unknown")),
                confidence=Confidence(str(rdl.get("confidence", "medium"))),
                created_at=timestamp,
            )
            evidence_links.append(link)

        # ── Link claims to results ──
        self._cross_link_claims_results(claims, paper_id, evidence_links, timestamp)

        result = {
            "paper_id": paper_id,
            "claim_count": len(claims),
            "evidence_link_count": len(evidence_links),
            "claims": [c.model_dump(mode="json", exclude_none=False) for c in claims],
            "evidence_links": [el.model_dump(mode="json", exclude_none=False) for el in evidence_links],
            "build_version": "0.1.0",
            "built_at": timestamp,
        }

        self._write_output(output_path, result)
        return result

    def _cross_link_claims_results(
        self,
        claims: list[ClaimAsset],
        paper_id: str,
        evidence_links: list[EvidenceLink],
        timestamp: str,
    ) -> None:
        """Create bidirectional links between claims and results via evidence links."""
        key_results = self.evidence_adapter.get_key_results(paper_id)
        result_ids = [f"{paper_id}:result:{i:04d}" for i in range(len(key_results))]

        for link in evidence_links:
            # Add result -> claim link in supporting_evidence
            for claim in claims:
                if claim.asset_id == link.target_asset_id:
                    if link.source_asset_id not in claim.linked_result_ids:
                        claim.linked_result_ids.append(link.source_asset_id)
                    if link.source_asset_id not in claim.supporting_evidence:
                        claim.supporting_evidence.append(link.link_id)
                    break

    def _map_discussion_type(self, dp_type: str) -> str:
        """Map discussion point type to claim type."""
        mapping = {
            "interpretation": "interpretation",
            "mechanism": "hypothesis",
            "limitation": "gap",
            "question": "gap",
            "future": "conclusion",
            "conclusion": "conclusion",
        }
        return mapping.get(dp_type.lower(), "interpretation")

    def _extract_citations(self, text: str) -> list[str]:
        """Extract in-text citation markers like [1], [6,7], [9][10][11]."""
        import re
        pattern = r"\[(\d+(?:[,，]\d+)*)\]"
        citations: list[str] = []
        for match in re.finditer(pattern, text):
            citations.append(match.group(0))
        return citations

    def _load_existing(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"paper_id": "", "claims": [], "evidence_links": [], "claim_count": 0, "evidence_link_count": 0}

    def _write_output(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_claim_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "claims_evidence.json"
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("claim_count", 0)
        except Exception:
            return 0

    def get_evidence_link_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "claims_evidence.json"
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("evidence_link_count", 0)
        except Exception:
            return 0
