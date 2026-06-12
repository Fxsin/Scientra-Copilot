"""
Entity Asset Builder — extracts named entities from metadata, summary, and evidence.

Phase 0: text-based heuristic extraction using regex and keyword matching.
No LLM calls. No OCR.

Outputs: 06_PDF_DataAssets/06_entities/{paper_id}/entities.json
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.schemas import Confidence, EntityAsset, EntityType
from scientra.pdf_data_assets.evidence_adapter import EvidenceAdapter


class EntityAssetBuilder:
    """Heuristic entity extractor — Phase 0 text-based only."""

    # ── Regex / keyword patterns per entity type ──
    ENTITY_PATTERNS: dict[EntityType, list[str]] = {
        EntityType.protein: [
            r"\b(Vip3A[a-z]?|Cry\d+[A-Za-z]*|Cyt\d+[A-Za-z]*|Vip\d+[A-Za-z]*)\b",
            r"\b(Bt\s+toxin|insecticidal\s+protein|crystal\s+protein|vegetative\s+insecticidal\s+protein)\b",
            r"\b(protoxin|active\s+toxin|pore.form(?:ing)?\s+toxin)\b",
        ],
        EntityType.gene: [
            r"\b([A-Z][a-z]{2,}[A-Z]\d*)\b",  # Gene symbols: Spod, Casp1, etc.
            r"\b(gene|mRNA|transcript|ORF|open\s+reading\s+frame)\b",
        ],
        EntityType.species: [
            r"\b(Spodoptera\s+frugiperda|Heliothis\s+virescens|Helicoverpa\s+armigera|Plutella\s+xylostella|Ostrinia\s+nubilalis)\b",
            r"\b(Sf9|High\s*Five|Tn5|HzAm1)\b",
            r"\b(Bacillus\s+thuringiensis|E\.?\s*coli|Escherichia\s+coli)\b",
            r"\b(lepidopteran|coleopteran|dipteran|insect)\b",
        ],
        EntityType.receptor: [
            r"\b(receptor|BBMV|brush\s+border\s+membrane|cadherin|aminopeptidase|alkaline\s+phosphatase)\b",
            r"\b(scavenger\s+receptor|fibroblast\s+growth\s+factor\s+receptor|S2)\b",
        ],
        EntityType.pathway: [
            r"\b(apoptosis|caspase|MAPK|signaling|endocytosis|hormone\s+synthesis)\b",
            r"\b(metabolic\s+pathway|insect\s+hormone\s+biosynthesis)\b",
            r"\b(KEGG|GO|Gene\s+Ontology|pathway)\b",
        ],
        EntityType.method: [
            r"\b(RNA.[Ss]eq|transcriptom|proteom|qPCR|Western\s+blot|ELISA|SPR)\b",
            r"\b(surface\s+plasmon\s+resonance|immunohistochem|confocal|electron\s+microscop)\b",
            r"\b(bioassay|feeding\s+assay|toxicity\s+assay|LC50|LD50)\b",
        ],
        EntityType.software: [
            r"\b(KEGG|Gene\s+Ontology|GO\s+term|DESeq2|edgeR|GraphPad|Prism)\b",
            r"\b(ImageJ|Fiji|Cytoscape|STRING|DAVID|ClusterProfiler|Metascape)\b",
            r"\b(GSEA|limma|Bowtie|STAR|Salmon|BLAST)\b",
        ],
        EntityType.database: [
            r"\b(GenBank|UniProt|PDB|NCBI|PubMed|CrossRef|DOI)\b",
        ],
        EntityType.host: [
            r"\b(Sf9\s*cells?|S\.?\s*frugiperda\s*larvae|midgut|BBMV)\b",
        ],
        EntityType.mutation: [
            r"\b(mutation|mutant|resistance|amino\s+acid\s+substitution)\b",
            r"\b(point\s+mutation|deletion|insertion|SNP|polymorphism)\b",
        ],
        EntityType.treatment: [
            r"\b(Vip3Aa\s+treatment|toxin\s+exposure|control\s+diet|non.toxin.added)\b",
        ],
        EntityType.dose: [
            r"\b(\d+(?:\.\d+)?\s*(?:ng|μg|mg|g|μM|nM|mM|ppm)\b)",
        ],
        EntityType.time: [
            r"\b(\d+(?:\.\d+)?\s*(?:h|hr|hour|min|minute|day|week)s?\b)",
        ],
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.output_dir = self.root / "06_PDF_DataAssets" / "06_entities"
        self.evidence_adapter = EvidenceAdapter(root)
        self._compiled: dict[EntityType, list[re.Pattern]] = {}

    def _get_patterns(self) -> dict[EntityType, list[re.Pattern]]:
        """Compile regex patterns lazily."""
        if not self._compiled:
            for etype, patterns in self.ENTITY_PATTERNS.items():
                self._compiled[etype] = [re.compile(p, re.IGNORECASE) for p in patterns]
        return self._compiled

    def build(self, paper_id: str, force: bool = False) -> list[EntityAsset]:
        """Build entity assets for a paper."""
        output_path = self.output_dir / paper_id / "entities.json"
        if output_path.exists() and not force:
            return self._load_existing(output_path)

        # Collect text from all sources
        text_corpus = self._collect_text(paper_id)
        if not text_corpus:
            return []

        assets: list[EntityAsset] = []
        timestamp = datetime.now(timezone.utc).isoformat()
        seen: set[tuple[str, str]] = set()  # (entity_name, entity_type) dedup
        patterns = self._get_patterns()
        idx = 0

        for etype, regex_list in patterns.items():
            for pattern in regex_list:
                for match in pattern.finditer(text_corpus):
                    entity_name = match.group(0).strip()
                    if len(entity_name) < 2:
                        continue
                    key = (entity_name.lower(), etype.value)
                    if key in seen:
                        continue
                    seen.add(key)

                    # Extract context (surrounding text)
                    start = max(0, match.start() - 80)
                    end = min(len(text_corpus), match.end() + 80)
                    context = text_corpus[start:end].strip()

                    asset = EntityAsset(
                        asset_id=f"{paper_id}:entity:{idx:04d}",
                        paper_id=paper_id,
                        entity_name=entity_name,
                        entity_type=etype,
                        entity_context=context,
                        source_file=f"03_Evidence/{paper_id}/evidence.json",
                        source_section="unknown",
                        source_text=context,
                        confidence=Confidence.low,  # heuristic extraction is low confidence
                        linked_evidence_id=paper_id,
                        linked_summary_section=None,
                        linked_claim_ids=[],
                        database_ids={},
                        created_at=timestamp,
                        metadata={
                            "extraction_method": "regex_heuristic",
                            "pattern": pattern.pattern[:120],
                        },
                    )
                    assets.append(asset)
                    idx += 1

        # Also scan method names and result texts for additional entities
        self._scan_structured_fields(paper_id, assets, seen, idx, timestamp)

        # Deduplicate by asset_id
        unique_assets = self._dedup_by_id(assets)

        self._write_output(output_path, unique_assets)
        return unique_assets

    def _collect_text(self, paper_id: str) -> str:
        """Gather all available text for a paper."""
        parts: list[str] = []
        evidence = self.evidence_adapter.load_evidence(paper_id)
        if evidence:
            parts.append(evidence.get("title", ""))
            for m in evidence.get("methods", []):
                if isinstance(m, dict):
                    parts.append(str(m.get("name", "")))
                    parts.append(str(m.get("quote", "")))
            for kr in evidence.get("key_results", []):
                if isinstance(kr, dict):
                    parts.append(str(kr.get("result", "")))
            for cf in evidence.get("core_findings", []):
                if isinstance(cf, dict):
                    parts.append(str(cf.get("finding", "")))
            for dp in evidence.get("discussion_points", []):
                if isinstance(dp, dict):
                    parts.append(str(dp.get("point", "")))

        # Try to read summary
        summary_text = self._read_summary(paper_id)
        if summary_text:
            parts.append(summary_text)

        return "\n".join(parts)

    def _read_summary(self, paper_id: str) -> str:
        """Attempt to read summary.md for the paper."""
        # Summary dirs are like paper_<hash>, try to match
        summary_dir = self.root / "03_Summary"
        if not summary_dir.exists():
            return ""
        # Try common naming patterns
        for subdir in summary_dir.iterdir():
            if not subdir.is_dir():
                continue
            summary_path = subdir / "summary.md"
            if summary_path.exists():
                try:
                    content = summary_path.read_text(encoding="utf-8")
                    # Check if this summary belongs to our paper
                    if paper_id[:20].lower() in subdir.name.lower() or paper_id[-12:] in subdir.name:
                        return content
                except Exception:
                    pass
        return ""

    def _scan_structured_fields(
        self,
        paper_id: str,
        assets: list[EntityAsset],
        seen: set[tuple[str, str]],
        start_idx: int,
        timestamp: str,
    ) -> None:
        """Scan method names and result texts for additional entity mentions not caught by regex."""
        idx = start_idx

        # Method names
        methods = self.evidence_adapter.get_methods(paper_id)
        for m in methods:
            if not isinstance(m, dict):
                continue
            name = str(m.get("name", "")).strip()
            if len(name) < 3:
                continue
            key = (name.lower(), "method")
            if key in seen:
                continue
            seen.add(key)
            asset = EntityAsset(
                asset_id=f"{paper_id}:entity:{idx:04d}",
                paper_id=paper_id,
                entity_name=name,
                entity_type=EntityType.method,
                entity_context=str(m.get("quote", name)),
                source_file=f"03_Evidence/{paper_id}/evidence.json",
                source_section=str(m.get("section", "unknown")),
                source_text=str(m.get("quote", name)),
                confidence=Confidence.medium,
                linked_evidence_id=f"{paper_id}:methods",
                linked_summary_section=None,
                linked_claim_ids=[],
                database_ids={},
                created_at=timestamp,
                metadata={"source": "evidence.methods.name"},
            )
            assets.append(asset)
            idx += 1

    def _dedup_by_id(self, assets: list[EntityAsset]) -> list[EntityAsset]:
        """Remove duplicates by asset_id, keeping first occurrence."""
        seen_ids: set[str] = set()
        result: list[EntityAsset] = []
        for a in assets:
            if a.asset_id not in seen_ids:
                seen_ids.add(a.asset_id)
                result.append(a)
        return result

    def _load_existing(self, path: Path) -> list[EntityAsset]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [EntityAsset(**item) for item in raw]
        except Exception:
            return []

    def _write_output(self, path: Path, assets: list[EntityAsset]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.model_dump(mode="json", exclude_none=False) for a in assets]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_entity_count(self, paper_id: str) -> int:
        path = self.output_dir / paper_id / "entities.json"
        if not path.exists():
            return 0
        try:
            return len(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return 0
