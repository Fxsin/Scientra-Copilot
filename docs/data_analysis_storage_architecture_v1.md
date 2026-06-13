# Scientra Copilot — Data Analysis & Storage Architecture (V1)

**Version:** 1.0
**Date:** 2026-06-12
**Status:** Phase 0 Implemented

---

## 1. Overview

This document defines the complete data flow and directory architecture of
Scientra Copilot, from raw PDF ingestion through to agent-consumable structured
knowledge. The architecture is organized into **7 data layers**, each with a
clear responsibility, input, output, and dependency relationship.

### Guiding Principles

1. **Traceability** — every derived asset must preserve `source_text` back to the original paper.
2. **Non-destructive** — new layers enhance existing ones; they never replace or delete.
3. **Domain-agnostic** — no hardcoded research fields, species, toxins, or paper-specific logic.
4. **Missing data is explicit** — `unknown`, `null`, `[]` — never fabricated.
5. **API is the contract** — the web UI consumes only the REST API, never direct file access.

---

## 2. Complete Data Flow

```
                          ┌─────────────────────────────────────┐
                          │          00_Inbox/                   │
                          │    Raw PDF drop zone                 │
                          └──────────────┬──────────────────────┘
                                         │ import_pdf
                                         ▼
                          ┌─────────────────────────────────────┐
                          │          01_PDF/                     │
                          │    Imported & numbered PDFs          │
                          └──────────────┬──────────────────────┘
                                         │ GROBID parse
                                         ▼
                          ┌─────────────────────────────────────┐
                          │        02_Metadata/                  │
                          │  TEI XML, YAML metadata, state       │
                          │  (DOI, Crossref, PubMed lookup)      │
                          └──────────────┬──────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
          ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
          │  03_Summary/     │  │  Tag Engine      │  │  03_Evidence/   │
          │  AI-generated    │  │ (regex rules)    │  │  V2.3 Evidence  │
          │  paper summaries │  │ → 05_Index/tags/ │  │  Extraction     │
          └────────┬────────┘  └─────────────────┘  └────────┬────────┘
                   │                                         │
                   │              (reads from)                │
                   │                                         │
                   └──────────────────┬──────────────────────┘
                                      │
                                      ▼
                          ┌─────────────────────────────────────┐
                          │     06_PDF_DataAssets/  ← NEW       │
                          │  Structured PDF internal assets:    │
                          │  sections, methods, results,        │
                          │  entities, claims, evidence links,  │
                          │  agent chunks                       │
                          └──────────────┬──────────────────────┘
                                         │
                          ┌──────────────┼──────────────┐
                          │              │              │
                          ▼              ▼              ▼
                ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                │04_VectorDB/  │ │  05_Index/   │ │ Agent SDK    │
                │ LanceDB       │ │ Research Map,│ │ + Web API    │
                │ BGE-M3        │ │ Hotspots,    │ │ (FastAPI)    │
                │ embeddings    │ │ Gaps, Net,   │ │              │
                │               │ │ Report       │ │              │
                └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 3. Directory Responsibilities

### 3.1 `00_Inbox/` — PDF Drop Zone

| Item | Description |
|---|---|
| **Purpose** | Receives new PDFs for processing |
| **Input** | User-dropped or agent-submitted PDF files |
| **Output** | PDFs moved to `01_PDF/` after import |
| **Dependencies** | None |
| **Consumer** | `workflow.py` step: `import_pdf` |

### 3.2 `01_PDF/` — Processed PDFs

| Item | Description |
|---|---|
| **Purpose** | Stores imported and numbered PDFs as the canonical source |
| **Input** | PDFs from `00_Inbox/` |
| **Output** | Read by GROBID parser |
| **Dependencies** | `00_Inbox/` |
| **Consumer** | `Scripts/pdf_parser.py` (GROBID) |

### 3.3 `02_Metadata/` — Literature Metadata

| Item | Description |
|---|---|
| **Purpose** | Stores structured paper-level metadata |
| **Input** | GROBID TEI XML, DOI/Crossref/PubMed APIs |
| **Output** | `yaml/*.metadata.yaml`, `tei/*.tei.xml`, state databases |
| **Dependencies** | `01_PDF/` (GROBID output) |
| **Consumer** | Summary Agent, Evidence Extraction, Tag Engine, Query Service |

Key files:
- `yaml/{paper_id}.metadata.yaml` — structured metadata per paper
- `tei/{paper_id}.tei.xml` — GROBID full-text TEI XML
- `metadata.yaml` — aggregated metadata
- `metadata_extractor_state.json` — extractor progress
- `parse_status.sqlite` — parse tracking

### 3.4 `03_Summary/` — AI Summaries

| Item | Description |
|---|---|
| **Purpose** | Stores LLM-generated paper summaries |
| **Input** | Raw text from `02_Metadata/` (TEI XML parsed text) |
| **Output** | `paper_{hash}/summary.md` per paper |
| **Dependencies** | `02_Metadata/`, LLM API (Claude / DeepSeek) |
| **Consumer** | Evidence Extraction, Entity Builder, Claim Builder |

### 3.5 `03_Evidence/` — Structured Evidence (V2.3)

| Item | Description |
|---|---|
| **Purpose** | Stores structured evidence extracted from papers |
| **Input** | Parsed text + summaries |
| **Output** | `{paper_id}/evidence.json` per paper |
| **Dependencies** | `03_Summary/`, `02_Metadata/` |
| **Consumer** | `06_PDF_DataAssets/` (via EvidenceAdapter), Evidence Chunks, Evidence Embedding |

Evidence JSON structure:
```json
{
  "paper_id": "...",
  "methods": [{ "name": "...", "section": "...", "quote": "...", "confidence": "..." }],
  "key_results": [{ "result": "...", "direction": "...", "section": "..." }],
  "core_findings": [{ "finding": "...", "section": "..." }],
  "discussion_points": [{ "point": "...", "type": "...", "section": "..." }],
  "claims": [],
  "result_discussion_links": [{ "result_index": 0, "discussion_index": 3, "link_type": "interprets" }]
}
```

**IMPORTANT: This format must NOT be modified.** The `06_PDF_DataAssets/` layer
reads from it via the adapter but never alters the original files.

### 3.6 `06_PDF_DataAssets/` — PDF Internal Data Assets (NEW)

| Item | Description |
|---|---|
| **Purpose** | Converts existing evidence + summaries into fine-grained, traceable, linkable, agent-ready assets |
| **Input** | `03_Evidence/`, `03_Summary/`, `02_Metadata/` |
| **Output** | Structured asset JSON/JSONL per paper across 10 subdirectories |
| **Dependencies** | `03_Evidence/`, `03_Summary/`, `02_Metadata/` |
| **Consumer** | `04_VectorDB/` (future), `05_Index/` (future), Agent SDK |

Subdirectory structure:
```
06_PDF_DataAssets/
├── 00_registry/         asset_registry.json (per-paper build tracking)
├── 01_sections/         {paper_id}/sections.json
├── 02_figures/          (Phase 1 — reserved)
├── 03_tables/           (Phase 2 — reserved)
├── 04_methods/          {paper_id}/methods.json
├── 05_results/          {paper_id}/results.json
├── 06_entities/         {paper_id}/entities.json
├── 07_claims_evidence/  {paper_id}/claims_evidence.json
├── 08_supplementary_links/  (Phase 3 — reserved)
├── 09_agent_chunks/     {paper_id}/agent_chunks.jsonl
└── README.md
```

### 3.7 `04_VectorDB/` — Vector Embeddings

| Item | Description |
|---|---|
| **Purpose** | Stores BGE-M3 embeddings for semantic search |
| **Input** | Metadata, summaries, evidence chunks, (future: agent_chunks) |
| **Output** | LanceDB tables: `metadata_embeddings`, `summary_embeddings`, `chunk_embeddings`, `evidence_chunks` |
| **Dependencies** | `02_Metadata/`, `03_Summary/`, `03_Evidence/` (chunks), (future: `06_PDF_DataAssets/`) |
| **Consumer** | Query Service (`hybrid_search`), Research Map |

### 3.8 `05_Index/` — Aggregated Indices

| Item | Description |
|---|---|
| **Purpose** | Caches aggregated analytics: Research Map clusters, Hotspots, Research Gaps, Knowledge Network, Reports |
| **Input** | Vector DB query results, metadata, tags |
| **Output** | JSON cache files: `research_map_clusters.json`, `hotspots_cache.json`, etc. |
| **Dependencies** | `04_VectorDB/`, `02_Metadata/`, Tag Engine |
| **Consumer** | Web UI (via API), Agent SDK |

### 3.9 `web/` — Next.js Frontend

| Item | Description |
|---|---|
| **Purpose** | User-facing web application |
| **Input** | REST API only (`scientra/server.py`) |
| **Rules** | Never reads filesystem directly; never accesses `06_PDF_DataAssets/` directly |
| **Consumer** | End users |

### 3.10 `agent_sdk.py` / `scientra/sdk.py` — Agent SDK

| Item | Description |
|---|---|
| **Purpose** | Programmatic interface for LLM agents |
| **Input** | `literature_query()` → REST API → LanceDB |
| **Rules** | No direct PDF access; no direct LanceDB access; all through query service |
| **Future** | May consume `agent_chunks.jsonl` via API |

---

## 4. New Layer: `06_PDF_DataAssets/` Deep Dive

### 4.1 Relationship to Existing Layers

```
03_Evidence/                         06_PDF_DataAssets/
┌────────────────────┐              ┌────────────────────────────┐
│ evidence.json      │──reads──→   │ EvidenceAdapter            │
│  ├─ methods[]      │              │   ↓                        │
│  ├─ key_results[]  │              │ MethodAssetBuilder  → 04_methods/
│  ├─ core_findings[]│              │ ResultAssetBuilder  → 05_results/
│  ├─ discussion_... │              │ EntityAssetBuilder  → 06_entities/
│  ├─ claims[]       │              │ ClaimEvidenceBuilder→ 07_claims_evidence/
│  └─ result_disc_   │              │ SectionAligner      → 01_sections/
│     links[]        │              │ AgentChunkBuilder   → 09_agent_chunks/
└────────────────────┘              └────────────────────────────┘
        ▲                                      │
        │ (never modified)                     ▼ (feeds)
        │                              ┌──────────────────┐
        │                              │ 04_VectorDB/     │
        └──────────────────────────────│ 05_Index/        │
                                       │ Agent SDK        │
                                       └──────────────────┘
```

### 4.2 Asset Schema

Every asset extends `PDFAssetBase` (defined in `scientra/pdf_data_assets/schemas.py`):

| Field | Type | Description |
|---|---|---|
| `asset_id` | str | Unique ID: `{paper_id}:{type}:{index}` |
| `paper_id` | str | Source paper identifier |
| `asset_type` | enum | section / method / result / entity / claim / figure / table / agent_chunk |
| `source_file` | str | Originating file path |
| `source_section` | str | Section within the paper |
| `source_text` | str | Original text (MANDATORY for traceability) |
| `linked_evidence_id` | str? | Cross-reference to 03_Evidence item |
| `linked_summary_section` | str? | Cross-reference to 03_Summary |
| `confidence` | enum | high / medium / low / unknown |
| `created_at` | str | ISO 8601 timestamp |

### 4.3 Phase 0 Scope (Current)

| Capability | Status | Details |
|---|---|---|
| Section alignment | ✅ Implemented | Aligns abstract, intro, methods, results, discussion, conclusion across sources |
| Method assets | ✅ Implemented | From evidence methods with category classification |
| Result assets | ✅ Implemented | From key_results, core_findings, discussion_points |
| Entity extraction | ✅ Implemented | Heuristic regex + keyword, 16 entity types |
| Claim-evidence links | ✅ Implemented | From result_discussion_links, text-based only |
| Agent chunks | ✅ Implemented | JSONL with entity enrichment |
| Registry | ✅ Implemented | Per-paper build tracking |
| OCR | ❌ Skipped | Recorded as `skipped_ocr` |
| Figure extraction | ❌ Reserved | Phase 1 |
| Table extraction | ❌ Reserved | Phase 2 |
| Supplementary linking | ❌ Reserved | Phase 3 |

---

## 5. Configuration

All feature flags and paths are in `Config/pdf_data_assets.yaml`:

```yaml
features:
  enabled: true
  reuse_03_evidence: true
  reuse_03_summary: true
  generate_agent_chunks: true
  figure_extraction: { enabled: false }   # Phase 1
  table_extraction: { enabled: false }    # Phase 2
  supplementary_linking: { enabled: false } # Phase 3
  skip_ocr: true
  skip_complex_table_parsing: true
```

---

## 6. API Compatibility

### 6.1 Existing APIs (UNCHANGED)

| Route | Status |
|---|---|
| `GET /paper/{id}/evidence` | ✅ Unchanged |
| `POST /query/evidence` | ✅ Unchanged |
| `GET /research-map` | ✅ Unchanged |
| `GET /knowledge-network` | ✅ Unchanged |
| `GET /hotspots` | ✅ Unchanged |
| `GET /research-gaps` | ✅ Unchanged |
| `GET /report` | ✅ Unchanged |

### 6.2 Reserved Future APIs (NOT implemented)

| Route | Purpose | Phase |
|---|---|---|
| `GET /paper/{id}/assets` | List all assets for a paper | Phase 1+ |
| `GET /paper/{id}/figures` | Return figure assets | Phase 1 |
| `GET /paper/{id}/tables` | Return table assets | Phase 2 |
| `GET /paper/{id}/claims` | Return claim assets | Phase 1+ |
| `POST /query/assets` | Semantic search across assets | Phase 2+ |

---

## 7. Extension Roadmap

### Phase 1: Figure + Caption Extraction
- Parse figure captions from GROBID TEI XML / raw text
- Extract figure references (`Figure 1`, `Fig. 2`) with context
- Build `FigureAsset` records in `02_figures/`
- Cross-link figures with results that reference them
- Enable `GET /paper/{id}/figures`

### Phase 2: Table Extraction
- Parse table structures from GROBID TEI XML
- Normalize headers + rows into `TableAsset` records
- Build table assets in `03_tables/`
- Cross-link tables with results
- Enable `GET /paper/{id}/tables`

### Phase 3: Supplementary File Linking
- Extract supplementary file references from paper text
- Index supplementary file names, types, descriptions
- Build `SupplementaryLink` records in `08_supplementary_links/`
- Enable supplementary file lookup

### Phase 4+: Full Agent Integration
- Feed `agent_chunks.jsonl` into LanceDB as `agent_chunks` table
- Enable chunk-level retrieval with confidence scoring
- Add `POST /query/assets` for semantic asset search
- Build claim-evidence graph visualization

---

## 8. File Reference

### Core Modules

| Module | Path | Role |
|---|---|---|
| `schemas.py` | `scientra/pdf_data_assets/schemas.py` | All Pydantic asset models |
| `asset_registry.py` | `scientra/pdf_data_assets/asset_registry.py` | Registry CRUD |
| `evidence_adapter.py` | `scientra/pdf_data_assets/evidence_adapter.py` | 03_Evidence reader |
| `section_aligner.py` | `scientra/pdf_data_assets/section_aligner.py` | Section alignment |
| `method_asset_builder.py` | `scientra/pdf_data_assets/method_asset_builder.py` | Method assets |
| `result_asset_builder.py` | `scientra/pdf_data_assets/result_asset_builder.py` | Result assets |
| `entity_asset_builder.py` | `scientra/pdf_data_assets/entity_asset_builder.py` | Entity extraction |
| `claim_evidence_builder.py` | `scientra/pdf_data_assets/claim_evidence_builder.py` | Claims + links |
| `agent_chunk_builder.py` | `scientra/pdf_data_assets/agent_chunk_builder.py` | Agent chunks |
| `build_assets.py` | `scientra/pdf_data_assets/build_assets.py` | CLI entry point |

### Config & Docs

| File | Path |
|---|---|
| Configuration | `Config/pdf_data_assets.yaml` |
| Data assets README | `06_PDF_DataAssets/README.md` |
| Architecture doc | `docs/data_analysis_storage_architecture_v1.md` |

---

## 9. Usage

```bash
# Check current status
python -m scientra.pdf_data_assets.build_assets --status

# Build assets for one paper
python -m scientra.pdf_data_assets.build_assets --paper-id "example_paper_id_here"

# Build assets for all papers
python -m scientra.pdf_data_assets.build_assets --all

# Force rebuild
python -m scientra.pdf_data_assets.build_assets --all --force
```

---

## 10. Design Decisions

1. **Adapter pattern for 03_Evidence** — evidence_adapter.py wraps existing data; no changes to `evidence_extraction.py` required.
2. **Heuristic entities (Phase 0)** — regex-based extraction avoids LLM cost and stays domain-agnostic. Confidence is `low` for all heuristic entities.
3. **File-per-paper-per-type** — each paper's assets are stored in separate files rather than a single monolithic database, keeping the system composable and easy to debug.
4. **JSONL for agent chunks** — line-delimited JSON is streamable, appendable, and LLM-friendly.
5. **Reserved directories exist now** — `02_figures/`, `03_tables/`, `08_supplementary_links/` are created with placeholder READMEs so the structure is stable from Phase 0 onward.
