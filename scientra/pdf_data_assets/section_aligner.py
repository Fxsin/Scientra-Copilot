"""
Section Aligner — aligns paper sections across metadata, summary, and evidence.

Phase 0.5B fix:
  - Aggregates section text from evidence fields (methods.quote, key_results.result,
    core_findings.finding, discussion_points.point) grouped by section label.
  - Ensures source_text is always populated (synced from text field).
  - Falls back to "unknown" if no text is available.

Outputs: 06_PDF_DataAssets/01_sections/{paper_id}/sections.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import Confidence, SectionAsset
from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter


class SectionAligner:
    """Aligns section information from multiple sources into SectionAssets."""

    SECTION_LABELS = [
        "abstract",
        "introduction",
        "methods",
        "results",
        "discussion",
        "conclusion",
    ]

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "01_sections"
        self.evidence_adapter = EvidenceAdapter(root)

    def _gather_section_text(self, paper_id: str) -> dict[str, str]:
        """Aggregate text chunks by section from evidence fields.

        Scans methods[].quote, key_results[].result/quote,
        core_findings[].finding/quote, discussion_points[].point/quote,
        grouped by their 'section' field.
        """
        gathered: dict[str, list[str]] = {label: [] for label in self.SECTION_LABELS}

        evidence = self.evidence_adapter.load_evidence(paper_id)
        if not evidence:
            return {label: "" for label in self.SECTION_LABELS}

        # Collect from all text-bearing fields
        sources: list[tuple[str, str]] = []

        for m in evidence.get("methods", []):
            if isinstance(m, dict):
                sec = str(m.get("section", "")).strip().lower()
                text = str(m.get("quote", m.get("name", ""))).strip()
                if sec and text:
                    sources.append((sec, text))

        for kr in evidence.get("key_results", []):
            if isinstance(kr, dict):
                sec = str(kr.get("section", "")).strip().lower()
                text = str(kr.get("result", kr.get("quote", ""))).strip()
                if sec and text:
                    sources.append((sec, text))

        for cf in evidence.get("core_findings", []):
            if isinstance(cf, dict):
                sec = str(cf.get("section", "")).strip().lower()
                text = str(cf.get("finding", cf.get("quote", ""))).strip()
                if sec and text:
                    sources.append((sec, text))

        for dp in evidence.get("discussion_points", []):
            if isinstance(dp, dict):
                sec = str(dp.get("section", "")).strip().lower()
                text = str(dp.get("point", dp.get("quote", ""))).strip()
                if sec and text:
                    sources.append((sec, text))

        # Map detected section names to canonical labels
        for sec_raw, text in sources:
            matched = self._match_section(sec_raw)
            if matched:
                gathered[matched].append(text)

        # Join chunks per section (cap at 16000 chars)
        result: dict[str, str] = {}
        for label in self.SECTION_LABELS:
            joined = " ".join(gathered[label])
            if joined.strip():
                result[label] = joined[:16000]
            else:
                result[label] = ""

        return result

    def _match_section(self, raw: str) -> str | None:
        """Map a raw section name to a canonical SECTION_LABEL."""
        raw_lower = raw.lower().strip()
        # Direct match
        for label in self.SECTION_LABELS:
            if label in raw_lower:
                return label
        # Common aliases
        if "result" in raw_lower and "discussion" in raw_lower:
            return "results"  # combined section → results
        if "background" in raw_lower:
            return "introduction"
        if "method" in raw_lower or "material" in raw_lower:
            return "methods"
        if "finding" in raw_lower:
            return "results"
        if "conclu" in raw_lower or "summary" in raw_lower:
            return "conclusion"
        return None

    def build(self, paper_id: str, force: bool = False) -> list[SectionAsset]:
        """Build section assets for a paper. Returns list of SectionAssets."""
        output_path = self.output_dir / paper_id / "sections.json"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        evidence_meta = self.evidence_adapter.get_evidence_meta(paper_id)
        coverage = evidence_meta.get("coverage", {})
        section_texts = self._gather_section_text(paper_id)

        assets: list[SectionAsset] = []
        timestamp = datetime.now(timezone.utc).isoformat()

        for order, label in enumerate(self.SECTION_LABELS):
            has_section = coverage.get(f"has_{label}", False)
            section_text = section_texts.get(label, "")

            # Ensure source_text is populated
            if section_text.strip():
                source_text = section_text[:2000]
                quality_notes: list[str] = []
            else:
                source_text = "unknown"
                quality_notes = ["no_section_text_found_in_evidence"]

            asset = SectionAsset(
                asset_id=f"{paper_id}:section:{order:04d}",
                paper_id=paper_id,
                section_label=label,
                section_order=order,
                text=section_text[:16000] if section_text else "",
                char_count=len(section_text),
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=label,
                source_text=source_text,
                confidence=Confidence.medium if (has_section and section_text.strip()) else Confidence.low,
                linked_evidence_id=paper_id,
                linked_summary_section=label,
                created_at=timestamp,
                metadata={
                    "has_section": has_section,
                    "evidence_version": evidence_meta.get("evidence_version", "unknown"),
                    "quality_notes": quality_notes,
                    "text_source": "aggregated_from_evidence_fields" if section_text.strip() else "no_text_available",
                },
            )
            assets.append(asset)

        self._write_output(output_path, assets)
        return assets

    def _load_existing(self, path: Path) -> list[SectionAsset]:
        """Load previously built sections from disk."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [SectionAsset(**item) for item in raw]
        except Exception:
            return []

    def _write_output(self, path: Path, assets: list[SectionAsset]) -> None:
        """Write section assets to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.model_dump(mode="json", exclude_none=False) for a in assets]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_section_count(self, paper_id: str) -> int:
        """Return the number of sections for a paper."""
        path = self.output_dir / paper_id / "sections.json"
        if not path.exists():
            return 0
        try:
            return len(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return 0
