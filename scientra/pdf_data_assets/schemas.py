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


# ── Figure Asset (Phase 1) ──

class FigureAsset(PDFAssetBase):
    """A figure extracted from the paper with caption and reference links."""
    asset_type: AssetType = AssetType.figure
    figure_id: str = Field(default="unknown", description="Unique figure identifier")
    figure_label: str = Field(default="unknown", description="e.g. 'Figure 1', 'Fig. 2A'")
    figure_number: str = Field(default="unknown", description="e.g. '1', '2A', 'S1'")
    caption: str = Field(default="", description="Full figure caption text")
    caption_quality: str = Field(default="none", description="high / medium / low / none")
    caption_source: str = Field(default="unknown", description="plain_text_caption / tei_figure_block / reference_only")
    image_path: str | None = Field(default=None, description="Path to extracted figure image (null if not extracted)")
    panels: list[str] = Field(default_factory=list, description="e.g. ['A', 'B', 'C']")
    figure_type: str = Field(default="unknown")
    mentioned_in_sections: list[str] = Field(default_factory=list, description="Sections referencing this figure")
    reference_sentences: list[str] = Field(default_factory=list, description="Sentences that reference this figure")
    linked_result_assets: list[str] = Field(default_factory=list)
    linked_claim_assets: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    extraction_method: str = Field(default="regex_heuristic", description="How the figure was extracted")
    page_number: int | None = Field(default=None)


# ── Figure Interpretation Asset (Phase 1B) ──

class FigureInterpretationAsset(BaseModel):
    """AI-generated interpretation of a figure from caption + references. No image analysis."""
    asset_id: str = Field(..., description="Unique ID: {paper_id}:fig_interp:{index}")
    paper_id: str
    asset_type: str = Field(default="figure_interpretation")
    figure_id: str = Field(default="unknown")
    figure_label: str = Field(default="unknown")
    figure_type: str = Field(default="unknown")
    caption: str = Field(default="")
    caption_quality: str = Field(default="unknown")
    reference_sentences: list[str] = Field(default_factory=list)
    linked_result_assets: list[str] = Field(default_factory=list)
    linked_claim_assets: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    figure_main_message: str = Field(default="", description="One sentence describing what this figure shows")
    experimental_evidence_type: str = Field(default="unknown")
    supported_claims: list[str] = Field(default_factory=list)
    evidence_strength: str = Field(default="unclear")
    limitations: list[str] = Field(default_factory=list)
    interpretation_confidence: str = Field(default="low")
    interpretation_source: str = Field(default="unknown")
    status: str = Field(default="pending", description="pending / interpreted / skipped")
    model_name: str = Field(default="")
    prompt_version: str = Field(default="0.1.0")
    source_text: str = Field(default="")
    created_at: str = Field(default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())

# ── Table Asset (Phase 2A) ──

class TableStructureStatus(str, Enum):
    caption_only = "caption_only"
    structure_pending = "structure_pending"
    simple_structure_extracted = "simple_structure_extracted"
    complex_structure_skipped = "complex_structure_skipped"


class TableAsset(PDFAssetBase):
    """A table extracted from the paper with caption and reference links.

    Phase 2A: Caption + Reference extraction. No complex table structure parsing.
    Phase 2B: Simple table structure extraction from raw text.
    """
    asset_type: AssetType = AssetType.table
    table_id: str = Field(default="unknown", description="Unique table identifier")
    table_label: str = Field(default="unknown", description="e.g. 'Table 1', 'Supplementary Table S1'")
    table_number: str = Field(default="unknown", description="e.g. '1', 'S1', '2A'")
    caption: str = Field(default="", description="Full table caption text")
    source_text: str = Field(default="", description="Caption text or reference-only source for traceability")
    source_file: str = Field(default="unknown")
    source_section: str = Field(default="unknown")
    table_type: str = Field(default="unknown", description="Rule-based classification")
    mentioned_in_sections: list[str] = Field(default_factory=list)
    reference_sentences: list[str] = Field(default_factory=list)
    linked_result_assets: list[str] = Field(default_factory=list)
    linked_claim_assets: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = Field(default=Confidence.unknown)
    created_at: str = Field(
        default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    )
    extraction_method: str = Field(default="regex_heuristic")
    caption_quality: str = Field(default="none", description="high / medium / low / none")
    caption_source: str = Field(default="unknown", description="plain_text_caption / reference_only")
    structure_status: str = Field(default="caption_only", description="caption_only / structure_pending / simple_structure_extracted / complex_structure_skipped")
    # ── Phase 2B: Simple structure fields ──
    structured_rows: list[dict[str, str]] = Field(default_factory=list, description="Parsed table rows as list of {col_name: value}")
    structured_columns: list[str] = Field(default_factory=list, description="Column header names")
    raw_table_text: str | None = Field(default=None, description="Raw table body text block, if available")
    structure_confidence: str = Field(default="none", description="high / medium / low / none")
    structure_extraction_method: str = Field(default="unavailable", description="raw_text_delimited / markdown_like / whitespace_aligned / skipped_complex / unavailable")
    structure_notes: list[str] = Field(default_factory=list, description="Notes about structure extraction")


# ── Supplementary Table Link (Phase 2C) ──

class SupplementaryTableLink(BaseModel):
    """A link between a supplementary table reference and its local/remote file.

    Phase 2C: Identifies supplementary table/data references in raw text.
    Attempts to match to local files. No OCR, no LLM, no complex parsing.
    """
    asset_id: str = Field(..., description="Unique: {paper_id}:suppl_table:{index}")
    paper_id: str
    asset_type: str = Field(default="supplementary_table_link")
    supplement_label: str = Field(default="unknown", description="e.g. 'Table S1', 'Supplementary Data 1'")
    supplement_number: str = Field(default="unknown", description="e.g. 'S1', '1'")
    referenced_as: str = Field(default="", description="How the supplement is referenced in text")
    reference_sentences: list[str] = Field(default_factory=list)
    source_section: str = Field(default="unknown")
    source_text: str = Field(default="", description="Original reference text for traceability")
    linked_table_assets: list[str] = Field(default_factory=list)
    linked_result_assets: list[str] = Field(default_factory=list)
    linked_claim_assets: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    candidate_files: list[str] = Field(default_factory=list, description="Candidate local file paths (relative)")
    matched_file: str | None = Field(default=None, description="Best matched file path (relative)")
    file_type: str = Field(default="unknown", description="xlsx / csv / tsv / pdf / docx / zip / unknown")
    match_confidence: str = Field(default="none", description="high / medium / low / none")
    match_method: str = Field(default="no_match", description="exact_label_filename / paper_id_filename / title_keyword_filename / supplementary_index / manual_needed / no_match")
    content_status: str = Field(default="link_only", description="link_only / file_found / file_missing / file_unreadable / simple_preview_extracted / complex_file_skipped")
    preview_columns: list[str] = Field(default_factory=list)
    preview_rows: list[dict[str, str]] = Field(default_factory=list)
    row_count: int = Field(default=0)
    column_count: int = Field(default=0)
    # ── Phase 2D: Manual import fields ──
    imported_file_id: str | None = Field(default=None)
    imported_file_name: str | None = Field(default=None)
    imported_relative_path: str | None = Field(default=None, description="Relative path in 00_Supplementary/")
    sheet_names: list[str] = Field(default_factory=list)
    preview_status: str = Field(default="none", description="none / previewed / large_file_preview_only / file_unreadable")
    selected_sheet: str | None = Field(default=None, description="Sheet used for preview if xlsx")
    import_source: str = Field(default="none", description="none / manual_import")
    confidence: str = Field(default="low")
    created_at: str = Field(
        default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    )
    notes: list[str] = Field(default_factory=list)


# ── Supplementary Entity Record (Phase 2E) ──

class SupplementaryEntityRecord(BaseModel):
    """A lightweight entity extracted from high-confidence supplementary files.

    Phase 2E: Rule-based entity extraction from previewed supplementary data.
    Only generated for simple_preview_extracted with high/medium confidence.
    No LLM. No OCR. No external download.
    """
    entity_id: str = Field(..., description="Unique: {paper_id}:suppl_entity:{index}")
    paper_id: str
    source_asset_id: str = Field(default="")
    supplement_label: str = Field(default="unknown")
    imported_file_id: str | None = None
    imported_file_name: str | None = None
    sheet_name: str | None = None
    entity_text: str = Field(..., description="The entity text as found in the column")
    normalized_entity: str = Field(default="", description="Lowercase, stripped, normalized")
    entity_type: str = Field(default="unknown", description="gene / protein / compound / treatment / sample / phenotype / statistical_value / unknown")
    column_name: str = Field(default="")
    row_index: int = Field(default=0)
    row_preview: dict[str, str] = Field(default_factory=dict, description="Short row context (key columns only)")
    matched_columns: list[str] = Field(default_factory=list, description="Columns that triggered entity detection")
    value_columns: dict[str, str] = Field(default_factory=dict, description="Statistical/value columns in same row")
    confidence: str = Field(default="medium", description="high / medium / low")
    extraction_method: str = Field(default="column_header_rule")
    # ── Phase 2E-B: Deduplication & source identity ──
    linked_supplement_labels: list[str] = Field(default_factory=list, description="All supplement labels referencing this entity row")
    linked_source_asset_ids: list[str] = Field(default_factory=list, description="All source_asset_ids merged into this record")
    linked_reference_sentences: list[str] = Field(default_factory=list, description="Up to 5 reference sentences from merged links")
    source_link_count: int = Field(default=1, description="Number of supplementary links merged")
    dedup_key: str = Field(default="", description="{paper_id}::{file_id}::{sheet}::{row}::{col}::{norm_entity}")
    created_at: str = Field(
        default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    )


# ── Supplementary Entity Comparison Record (Phase 2G-A) ──

class SupplementaryEntityComparisonRecord(BaseModel):
    """Cross-paper entity comparison result.

    Phase 2G-A: Aggregates entity records across papers/files/sheets.
    Location and summary only — no statistical comparison, no LLM, no mechanism inference.
    """
    query_entity: str
    normalized_query: str = ""
    entity_type: str = "unknown"
    total_matches: int = 0
    unique_papers_count: int = 0
    unique_files_count: int = 0
    unique_sheets_count: int = 0
    records: list[dict] = Field(default_factory=list)
    direction_summary: dict = Field(default_factory=dict)
    value_column_summary: dict = Field(default_factory=dict)
    comparability_warning: str = (
        "Values from different papers or supplementary files may not be directly comparable "
        "unless experimental conditions, units, normalization, and statistical methods are aligned. "
        "Source link count reflects references linked to the same data row, not independent evidence."
    )
    created_at: str = Field(
        default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    )


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
