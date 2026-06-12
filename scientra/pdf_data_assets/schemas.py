"""
Unified asset schemas for PDF internal data assetization.

All assets extend PDFAssetBase and MUST include source_text for traceability.
Missing fields default to "unknown", null, or empty arrays — never fabricated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──

class AssetType(str, Enum):
    section = "section"
    method = "method"
    result = "result"
    figure = "figure"
    table = "table"
    entity = "entity"
    claim = "claim"
    evidence_link = "evidence_link"
    supplementary_link = "supplementary_link"
    agent_chunk = "agent_chunk"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class EntityType(str, Enum):
    protein = "protein"
    gene = "gene"
    species = "species"
    strain = "strain"
    vector = "vector"
    host = "host"
    treatment = "treatment"
    dose = "dose"
    time = "time"
    method = "method"
    receptor = "receptor"
    mutation = "mutation"
    domain = "domain"
    pathway = "pathway"
    software = "software"
    database = "database"
    unknown = "unknown"


class BuildStatus(str, Enum):
    pending = "pending"
    success = "success"
    partial = "partial"
    failed = "failed"
    skipped_ocr = "skipped_ocr"
    skipped_no_evidence = "skipped_no_evidence"


# ── Base Asset ──

class PDFAssetBase(BaseModel):
    """Every asset shares these core fields."""
    asset_id: str = Field(..., description="Unique asset identifier, e.g. {paper_id}:section:0001")
    paper_id: str = Field(..., description="Source paper identifier")
    asset_type: AssetType = Field(..., description="Category of asset")
    source_file: str = Field(default="unknown", description="Originating file path (relative to project root)")
    source_section: str = Field(default="unknown", description="Section within the source paper")
    source_text: str = Field(default="", description="Original text excerpt — REQUIRED for traceability")
    linked_evidence_id: str | None = Field(default=None, description="Cross-reference to 03_Evidence item")
    linked_summary_section: str | None = Field(default=None, description="Cross-reference to 03_Summary section")
    confidence: Confidence = Field(default=Confidence.unknown)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extensible metadata bag")


# ── Section Asset ──

class SectionAsset(PDFAssetBase):
    """A labeled section of the paper text."""
    asset_type: AssetType = AssetType.section
    section_label: str = Field(default="unknown", description="Human-readable section name (e.g. 'Introduction')")
    section_order: int = Field(default=0, description="Position in the paper")
    text: str = Field(default="", description="Full section text (may be truncated)")
    char_count: int = Field(default=0)
    parent_section: str | None = Field(default=None)


# ── Method Asset ──

class MethodAsset(PDFAssetBase):
    """A single method described in the paper."""
    asset_type: AssetType = AssetType.method
    method_name: str = Field(default="unknown", description="Method name or label")
    evidence_type: str = Field(default="unknown", description="e.g. experiment, sequencing, computational")
    method_category: str = Field(default="unknown", description="Broad category: wet-lab, dry-lab, field, clinical, etc.")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Extracted parameters (dose, time, temp, etc.)")
    equipment: list[str] = Field(default_factory=list)
    reagents: list[str] = Field(default_factory=list)
    software: list[str] = Field(default_factory=list)
    linked_results: list[str] = Field(default_factory=list, description="asset_ids of related ResultAssets")


# ── Result Asset ──

class ResultAsset(PDFAssetBase):
    """A single result or finding from the paper."""
    asset_type: AssetType = AssetType.result
    result_text: str = Field(default="", description="The complete result statement")
    measured_variable: str = Field(default="unknown")
    direction: str = Field(default="unknown", description="increase / decrease / no_change / descriptive")
    condition: str = Field(default="unknown")
    linked_method_id: str | None = Field(default=None, description="asset_id of related MethodAsset")
    linked_figure_ids: list[str] = Field(default_factory=list)
    linked_table_ids: list[str] = Field(default_factory=list)


# ── Figure Asset (Phase 1 — reserved) ──

class FigureAsset(PDFAssetBase):
    """A figure and its caption. Phase 1: populated; Phase 0: placeholder."""
    asset_type: AssetType = AssetType.figure
    figure_label: str = Field(default="unknown", description="e.g. 'Figure 1'")
    caption_text: str = Field(default="")
    figure_path: str | None = Field(default=None, description="Path to extracted figure image")
    figure_type: str = Field(default="unknown", description="graph / microscopy / diagram / photo / unknown")
    linked_results: list[str] = Field(default_factory=list)
    page_number: int | None = Field(default=None)


# ── Table Asset (Phase 2 — reserved) ──

class TableAsset(PDFAssetBase):
    """A table from the paper. Phase 2: populated; Phase 0: placeholder."""
    asset_type: AssetType = AssetType.table
    table_label: str = Field(default="unknown", description="e.g. 'Table 1'")
    caption_text: str = Field(default="")
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    row_count: int = Field(default=0)
    column_count: int = Field(default=0)
    linked_results: list[str] = Field(default_factory=list)
    page_number: int | None = Field(default=None)


# ── Entity Asset ──

class EntityAsset(PDFAssetBase):
    """A named entity extracted from the paper."""
    asset_type: AssetType = AssetType.entity
    entity_name: str = Field(..., description="The entity text as it appears in the paper")
    entity_type: EntityType = Field(default=EntityType.unknown)
    normalized_name: str | None = Field(default=None, description="Normalized / canonical form")
    entity_context: str = Field(default="", description="Surrounding sentence context")
    linked_claim_ids: list[str] = Field(default_factory=list)
    database_ids: dict[str, str] = Field(default_factory=dict, description="e.g. {'uniprot': 'P0A...', 'ncbi_gene': '...'}")


# ── Claim Asset ──

class ClaimAsset(PDFAssetBase):
    """A scientific claim with supporting evidence links."""
    asset_type: AssetType = AssetType.claim
    claim_text: str = Field(default="", description="The claim statement")
    claim_type: str = Field(default="unknown", description="finding / hypothesis / interpretation / conclusion / gap")
    supporting_evidence: list[str] = Field(default_factory=list, description="asset_ids of supporting EvidenceLinks")
    opposing_evidence: list[str] = Field(default_factory=list, description="asset_ids of opposing EvidenceLinks")
    linked_result_ids: list[str] = Field(default_factory=list)
    linked_figure_ids: list[str] = Field(default_factory=list)
    linked_table_ids: list[str] = Field(default_factory=list)
    citation_refs: list[str] = Field(default_factory=list, description="In-text citation markers")


# ── Evidence Link ──

class EvidenceLink(BaseModel):
    """A directional link between two pieces of evidence (e.g. result ↔ discussion)."""
    link_id: str = Field(..., description="Unique link identifier")
    paper_id: str
    source_asset_id: str = Field(..., description="From asset")
    target_asset_id: str = Field(..., description="To asset")
    link_type: str = Field(default="interprets", description="interprets / supports / contradicts / extends / replicates")
    basis: str = Field(default="unknown", description="Why the link exists (shared terms, semantic, etc.)")
    confidence: Confidence = Field(default=Confidence.medium)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Supplementary Link (Phase 3 — reserved) ──

class SupplementaryLink(BaseModel):
    """A reference to a supplementary file. Phase 3: populated; Phase 0: placeholder."""
    link_id: str = Field(..., description="Unique link identifier")
    paper_id: str
    reference_text: str = Field(default="", description="How the supplement is referenced in the paper")
    file_name: str | None = Field(default=None)
    file_type: str = Field(default="unknown", description="pdf / xlsx / csv / fasta / pdb / zip / unknown")
    description: str = Field(default="")
    url: str | None = Field(default=None)
    local_path: str | None = Field(default=None)
    linked_sections: list[str] = Field(default_factory=list)
    confidence: Confidence = Field(default=Confidence.unknown)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Agent Chunk Asset ──

class AgentChunkAsset(BaseModel):
    """A self-contained chunk of knowledge for LLM / agent consumption."""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    paper_id: str
    chunk_type: str = Field(default="unknown", description="section / method / result / entity / claim / composite")
    text: str = Field(..., description="The chunk content")
    source_asset_ids: list[str] = Field(default_factory=list, description="Upstream asset_ids this chunk derives from")
    source_section: str = Field(default="unknown")
    entities: list[str] = Field(default_factory=list, description="Entity names mentioned")
    linked_claims: list[str] = Field(default_factory=list, description="claim asset_ids")
    linked_methods: list[str] = Field(default_factory=list, description="method asset_ids")
    linked_evidence_id: str | None = Field(default=None, description="Primary 03_Evidence cross-reference")
    linked_evidence_ids: list[str] = Field(default_factory=list, description="All 03_Evidence cross-references from source assets")
    citation_ready: bool = Field(default=False, description="True if chunk can be used in a citation")
    confidence: Confidence = Field(default=Confidence.medium)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Asset Registry Entry ──

class RegistryEntry(BaseModel):
    """Per-paper registry record tracking all generated assets."""
    paper_id: str
    metadata_path: str | None = Field(default=None)
    evidence_path: str | None = Field(default=None)
    summary_path: str | None = Field(default=None)
    section_assets: int = Field(default=0)
    method_assets: int = Field(default=0)
    result_assets: int = Field(default=0)
    entity_assets: int = Field(default=0)
    claim_assets: int = Field(default=0)
    agent_chunks: int = Field(default=0)
    figure_assets: int = Field(default=0)
    table_assets: int = Field(default=0)
    supplementary_links: int = Field(default=0)
    build_status: BuildStatus = Field(default=BuildStatus.pending)
    error_message: str | None = Field(default=None)
    built_at: str | None = Field(default=None)


class AssetRegistryFile(BaseModel):
    """Top-level registry file (00_registry/asset_registry.json)."""
    version: str = Field(default="0.1.0")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_papers: int = Field(default=0)
    entries: list[RegistryEntry] = Field(default_factory=list)
