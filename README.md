# Scientra Copilot

<p align="center">
  <h3 align="center">From Literature to Discovery</h3>
  <p align="center">AI-Powered Research Discovery Platform</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg">
  <img src="https://img.shields.io/badge/license-MIT-green.svg">
  <img src="https://img.shields.io/badge/version-v1.4-blue.svg">
  <img src="https://img.shields.io/badge/status-active%20development-orange.svg">
</p>

---

## What is Scientra Copilot?

Scientra Copilot transforms scientific literature into structured, searchable, machine-readable knowledge. It automatically processes PDFs, extracts evidence, builds semantic indexes, and provides an **AI-powered chat interface** that answers research questions grounded in your literature with traceable citations.

> **Move from collecting papers to understanding knowledge and discovering ideas.**

---

## Core Capabilities

### 💬 Literature Chat (V1.0-alpha → V1.4)
- **7 intent-specific query types**: claim, research gap, method, result, supplementary entity, entity comparison, hybrid
- **Evidence Packet Builder** — structured Ref packets with evidence roles, method categories, gap signals
- **Academic citation format** — "Author et al. (Year) [Ref:N]" in all LLM answers
- **Boilerplate/disclaimer filter** — excludes publisher notes, copyright, data availability from answers
- **Domain-agnostic** — 88 generic scientific signals, no hardcoded research fields
- Dual-source retrieval: `pdf_asset_chunks` (2,718 rows) + `evidence_chunks` (1,267 rows)
- Three answer modes: **Auto**, **LLM synthesis**, **Evidence-only**
- Multi-provider LLM: **DeepSeek** + **Anthropic Claude**
- Paper-specific chat on every paper detail page
- Token usage & cost transparency (inline panel)
- Anti-hallucination: zero fabricated DOIs, zero `[object Object]`, zero disclaimers in answers
- 28-case evaluation framework: 100% pass rate

### 📊 PDF Data Assetization (Phase 0–2G)
- **11 chunk types**: section, method, result, claim, figure, table, supplementary_table, supplementary_entity, entity
- **10 asset types**: sections, methods, results, entities, claims, evidence links, figures, tables, supplementary links, agent chunks
- **Entity extraction**: 16 types (protein, gene, species, receptor, pathway, etc.)
- **Quality filtering**: entity noise removal (26%), chunk quality scoring
- **Figure extraction**: 44 figures across 30 papers, with caption extraction and rule-based type classification
- **Figure interpretation** (AI-powered, text-only): structured evidence type, strength, claims from captions

### 📋 Table + Supplementary Data Pipeline (Phase 2A–2G)

#### Table Caption & Reference Extraction (Phase 2A)
- 70 table assets across 56 papers (84.3% caption rate)
- Rule-based table type classification (12 types: toxicity, expression, binding, omics, etc.)
- Table caption quality scoring (high/medium/low/none)
- `/query/assets` supports `chunk_type=table`

#### Simple Table Structure Extraction (Phase 2B)
- Multi-strategy text-based table parsing (markdown, tab-delimited, whitespace-aligned, inline-flat)
- Column count and row detection
- Complexity classification (simple/complex/unavailable)
- Complex tables correctly skipped (41/70 complex_structure_skipped)

#### Supplementary Table Linking (Phase 2C)
- 90 supplementary references identified across 56 papers
- 10 reference detection patterns (Supplementary Table S1, Table S1, Tables S1-S3, Supplementary Data, etc.)
- Strict quality guard (Phase 2C-B): raw_text and PDFs never matched as supplementary data
- `/query/assets` supports `chunk_type=supplementary_table`

#### Manual Supplementary File Import (Phase 2D)
- User-drop directory: `00_Supplementary/inbox/`
- Auto-scan xlsx/csv/tsv/txt with lightweight preview (20 rows)
- 5-tier matching strategy with confidence gating (Phase 2D-B):
  - `manual_paper_id_label` → high confidence, auto-matched
  - `manual_label_only` → **candidate_only** (not auto-matched)
- `candidate_only` content_status for ambiguous matches
- XLSX sheet detection and preview

#### Supplementary Entity Index (Phase 2E)
- Column classification rules (gene, protein, compound, treatment, sample, phenotype, statistical_value)
- Entity extraction from high-confidence supplementary files only
- Deduplication by (file, sheet, row, column, entity) key (Phase 2E-B)
- 77 raw candidates → 7 deduplicated gene records
- `/query/supplementary-entities` exact + substring search
- SDK: `query_supplementary_entities()`

#### Entity Query Intent + Chat (Phase 2F)
- `supplementary_entity_query` intent detection (7/7 eval, 0 false positives)
- Deterministic entity lookup (<100ms, no LLM)
- Optional conservative LLM interpretation (Phase 2F-B): strict prompt guardrails
- Live smoke test verified (DeepSeek deepseek-chat, Phase 2F-C)
- Forbidden phrase detection and auto-sanitization

#### Cross-Paper Entity Comparison (Phase 2G)
- Cross-paper entity aggregation across all indexed supplementary data
- Direction summary (upregulated/downregulated/unknown) from FC/log2FC/Expression
- `supplementary_entity_comparison_query` intent detection
- Optional LLM conservative comparison summary (Phase 2G-B)
- Single-record/papers limitation explicitly stated
- `/query/supplementary-entity-comparison` endpoint

### 📄 Literature Processing
- PDF ingestion → GROBID parsing → metadata extraction → AI summarization
- Incremental processing with resume-from-failure
- Automatic tagging and knowledge extraction

### 🔬 Evidence Extraction V2.3
- **Key results**, **Core findings**, **Methods**, **Discussion points**
- Result-discussion linking with confidence scoring
- 1,267 evidence chunks embedded in LanceDB with BGE-M3

### 🗺️ Research Map V3
- 14 generic research facets, hierarchical subtopics
- Topic Evolution with evidence-rich phase cards
- Facet View and Topic View toggle

### 🔍 Semantic Search
- `/query/assets` — search quality-filtered asset chunks (11 chunk types)
- `/query/evidence` — search evidence chunks
- `/query/supplementary-entities` — search indexed supplementary entities
- `/query/supplementary-entity-comparison` — cross-paper entity comparison
- Filter by chunk type: section, method, result, claim, figure, table, supplementary_table, supplementary_entity

### 🔥 Hotspots · 🕳️ Research Gaps · 🕸️ Knowledge Network · 📊 Report
- Trending topics, hot papers, emerging facets
- Auto-detected research gaps from facet distribution
- 123 nodes × 330 edges network graph
- Auto-generated library intelligence report

---

## Quick Start

### 1. Install & Run

```bash
# Requirements: Python 3.11+, Docker (for GROBID), Node.js 18+

# Start everything (API + Web)
python Scripts/dev_restart.py

# Or start components separately:
python -m scientra.server          # API on http://127.0.0.1:8710
cd web && npm run dev              # Web on http://127.0.0.1:3000
```

### 2. Import Literature

```bash
# Place PDFs in 00_Inbox/
python workflow.py run
```

### 3. Set Up LLM for Chat (Recommended)

```bash
# Interactive setup — choose DeepSeek or Anthropic
python Scripts/setup_llm.py

# Or set environment variable:
# PowerShell:  $env:DEEPSEEK_API_KEY = "sk-..."
# Linux/macOS: export DEEPSEEK_API_KEY="sk-..."
```

The key is stored in `Config/llm_config.yaml` (gitignored, never committed).

### 4. Build Supplementary Data Assets (Optional)

```bash
# Import manually downloaded supplementary files
python -m scientra.pdf_data_assets.build_assets --import-supplementary

# Build supplementary links
python -m scientra.pdf_data_assets.build_assets --supplementary --all --force

# Index supplementary entities
python -m scientra.pdf_data_assets.build_assets --supplementary-entities --all --force

# Quality check + re-embedding
python -m scientra.pdf_data_assets.build_assets --quality-check
python -m scientra.pdf_data_assets.asset_embedding --all --force
```

### 5. Open Chat

```
http://127.0.0.1:3000/chat
```

Select **Answer Mode: Auto** and ask questions about your literature.

---

## Web Interface — 11 Pages

| Page | Description |
|---|---|
| `/chat` | **AI Chat** — ask questions, get cited answers |
| `/research-map` | Facet-first hierarchical topic explorer |
| `/research-map/topic/{id}` | Topic detail with evidence, evolution |
| `/library` | Paginated paper library with search/filter |
| `/paper/{id}` | Paper metadata, summary, evidence, **Ask this paper** |
| `/evidence` | Standalone evidence chunk search |
| `/hotspots` | Trending topics, hot papers, emerging facets |
| `/research-gaps` | Auto-detected evidence gaps |
| `/knowledge-network` | Paper-facet-method-finding network |
| `/report` | Auto-generated library intelligence report |
| `/topic-explorer` | Browse topics by research facet |

---

## Chat Query Types

The Literature Agent automatically detects your query intent:

| Intent | Example Questions | Output |
|---|---|---|
| `claim_query` | "Which claims need stronger evidence?" | Claim → Evidence → Missing → Sources |
| `research_gap_query` | "What research gaps can be inferred?" | Evidence-based + inferred gaps |
| `method_query` | "What methods are commonly used for bioassay?" | Grouped by category |
| `result_query` | "Which results are most frequently reported?" | Result + evidence strength |
| `supplementary_entity_query` | "Is MAP2K4 present in supplementary tables?" | Entity values + source |
| `supplementary_entity_comparison_query` | "Compare MAP2K4 across supplementary data." | Cross-paper aggregation |
| `hybrid_search` | General literature questions | Mixed retrieval |

### Chat Advanced Options

- **Answer Mode**: Auto / LLM synthesis / Evidence-only
- **Chunk Types**: section, method, result, claim, figure, table, supplementary, sup_entity
- **top_k**: Number of chunks to retrieve (1-50)
- **Paper filter**: Limit to a specific paper

---

## Supplementary Data Features (Phase 2)

### Manual File Import

Place downloaded supplementary data files in `00_Supplementary/inbox/`:

```bash
00_Supplementary/inbox/
├── {paper_id}__Table_S1.xlsx      # High-confidence match
├── {paper_id}__Supplementary_Data_1.csv
└── {label_only}__Table_S2.csv     # candidate_only (rename needed)
```

```bash
python -m scientra.pdf_data_assets.build_assets --import-supplementary
```

### Entity Query Examples

```
Chat: "Is MAP2K4 present in supplementary tables?"
Chat: "What are the FC and p-value for CASP3?"
Chat: "What does TRAF4 show in supplementary data?" (use LLM for interpretation)
Chat: "Compare MAP2K4 across supplementary data."
```

### SDK Usage

```python
from scientra.sdk import (
    query_assets,
    query_supplementary_entities,
    query_supplementary_entity_comparison,
    ask_literature,
)

# Search supplementary entities
results = query_supplementary_entities("MAP2K4", entity_type="gene")

# Compare across papers
comparison = query_supplementary_entity_comparison("MAP2K4")

# Ask with entity intent
answer = ask_literature("What does CASP3 show in supplementary data?", use_llm=False)
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | API + LanceDB status |
| `GET /papers` | Paginated paper list |
| `GET /paper/{id}/metadata` | Paper metadata |
| `GET /paper/{id}/summary` | AI-generated summary |
| `GET /paper/{id}/evidence` | Structured evidence |
| `POST /query/evidence` | Semantic evidence chunk search |
| `POST /query/assets` | Search quality-filtered asset chunks |
| `POST /query/supplementary-entities` | Search indexed supplementary entities |
| `POST /query/supplementary-entity-comparison` | Cross-paper entity comparison |
| `POST /v1/agent/ask` | Literature Agent — AI-powered Q&A |
| `GET /research-map` | Facet-first hierarchical topics |
| `GET /hotspots` | Trending topics, hot papers |
| `GET /research-gaps` | Auto-detected research gaps |
| `GET /knowledge-network` | Paper-facet-method-finding network |
| `GET /report` | Library intelligence report |

---

## Architecture

```text
PDF Papers
    ↓
GROBID Parsing → Metadata → Tags → AI Summarization
    ↓
Evidence Extraction V2.3
    ↓
┌─────────────────────────────────────────────────┐
│  PDF Data Assetization Layer                     │
│  sections · methods · results · entities         │
│  claims · evidence links · agent chunks           │
│  figures · figure interpretations                │
│  tables · table captions · table structures      │
│  supplementary links · supplementary previews    │
│  supplementary entities · entity comparisons     │
│  quality checks · noise filtering                │
└─────────────────────────────────────────────────┘
    ↓
BGE-M3 Embeddings → LanceDB
├── evidence_chunks (1,267 rows)
├── literature_vectors (319 rows)
└── pdf_asset_chunks (2,718 rows, 11 chunk types)
    ↓
┌─────────────────────────────────────────────────┐
│  Query Layer                                    │
│  /query/assets · /query/evidence                │
│  /query/supplementary-entities                  │
│  /query/supplementary-entity-comparison         │
│  /v1/agent/ask (Literature Agent)               │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  Literature Agent V1.4                          │
│  7 intents → Dual-Source Retrieval              │
│  → DeepSeek/Claude → Cited Answer               │
│  Conservative entity interpretation (Phase 2F)  │
│  Cross-paper comparison summary (Phase 2G)      │
│  Anti-hallucination guardrails                  │
│  28-case evaluation (100% pass)                 │
└─────────────────────────────────────────────────┘
    ↓
Web Frontend (11 pages, all real data)
Chat · Research Map · Paper Detail · Evidence · Hotspots · Gaps · Network · Report
```

---

## Project Structure

```text
Scientra_Copilot/
├── 00_Inbox/                  # PDF import directory
├── 00_Supplementary/          # Manual supplementary file import
│   ├── inbox/                 # Drop downloaded xlsx/csv/tsv here
│   ├── matched/               # Matched files (optional)
│   ├── unmatched/             # Unmatched files (optional)
│   └── registry/              # Import reports and file index
├── 01_PDF/                    # Processed PDFs
├── 02_Metadata/               # Extracted metadata (YAML)
├── 03_Evidence/               # Evidence extraction output
├── 03_Summary/                # AI-generated summaries + raw text
├── 04_VectorDB/               # LanceDB vector store
├── 05_Index/                  # Research map + hotspots cache
├── 06_PDF_DataAssets/         # Structured data assets (gitignored)
│   ├── 00_registry/           # Asset registry and reports
│   ├── 02_figures/            # Figure assets
│   ├── 03_tables/             # Table assets
│   ├── 08_supplementary_links/# Supplementary link records
│   ├── 09_supplementary_entities/ # Entity index records
│   ├── 09_agent_chunks/       # Agent-ready knowledge chunks
│   └── 10_entity_comparisons/ # Cross-paper comparison results
├── Config/                    # Configuration files
│   ├── llm_config.yaml        # LLM API key (gitignored)
│   └── pdf_data_assets.yaml
├── Scripts/                   # Setup, tests, verification
│   ├── setup_llm.py           # First-time LLM setup
│   ├── dev_restart.py         # One-command startup
│   ├── test_table_extraction.py
│   ├── test_supplementary_linking.py
│   ├── test_supplementary_entity_index.py
│   ├── test_supplementary_entity_query_agent.py
│   ├── test_supplementary_entity_comparison.py
│   └── test_query_assets_api.py
├── docs/                      # Documentation
├── scientra/                  # Backend Python modules
│   ├── agent/                 # Literature Agent
│   │   ├── literature_agent.py
│   │   ├── entity_query_parser.py
│   │   └── context_builder.py
│   └── pdf_data_assets/       # Data assetization
│       ├── table_extractor.py
│       ├── table_linker.py
│       ├── table_asset_builder.py
│       ├── table_structure_extractor.py
│       ├── supplementary_linker.py
│       ├── supplementary_preview.py
│       ├── supplementary_importer.py
│       ├── supplementary_entity_indexer.py
│       ├── supplementary_entity_comparator.py
│       └── figure_asset_builder.py
├── web/                       # Next.js frontend
│   ├── app/chat/              # Chat page
│   ├── app/paper/             # Paper detail (with Ask this paper)
│   └── components/agent/      # Shared agent UI components
├── workflow.py                # Main processing workflow
└── README.md
```

---

## Backend Modules

| Module | Description |
|---|---|
| `scientra/agent/` | **Literature Agent V1.4** — 7 intents, context builder, entity parser, eval framework |
| `scientra/pdf_data_assets/` | **PDF Data Assetization Phase 0–2G** — tables, figures, supplementary, entities, comparison |
| `scientra/evidence_extraction.py` | Evidence Extraction V2.3 |
| `scientra/embedding.py` | BGE-M3 embedder + embedding engine |
| `scientra/research_map_builder.py` | Research Map cache builder |
| `scientra/server.py` | FastAPI server (42+ routes) |

---

## Testing

```bash
# Agent evaluation
python -m scientra.agent.eval.regression_runner --use-llm false --case-type all

# Table extraction tests
python Scripts/test_table_extraction.py

# Supplementary linking tests (33 cases)
python Scripts/test_supplementary_linking.py

# Entity index tests (53 cases)
python Scripts/test_supplementary_entity_index.py

# Entity query agent tests (22 cases)
python Scripts/test_supplementary_entity_query_agent.py

# Entity comparison tests (31 cases)
python Scripts/test_supplementary_entity_comparison.py

# API tests
python Scripts/test_query_assets_api.py
python Scripts/test_agent_api.py

# Web tests
cd web
npm run build                     # TypeScript + Next.js
```

---

## LanceDB Chunk Distribution

| Chunk Type | Count |
|---|---|
| result | 1,155 |
| claim | 715 |
| method | 350 |
| section | 220 |
| supplementary_table | 87 |
| supplementary_entity | 7 |
| table | 70 |
| figure | 44 |
| **Total** | **2,718** |

---

## Roadmap

### Completed ✅
- PDF Processing Pipeline
- Evidence Extraction V2.3
- Research Map V3 (facet-first hierarchical)
- Evidence Search + Hotspots + Research Gaps + Knowledge Network
- Library Intelligence Report
- **PDF Data Assetization** (sections, methods, results, entities, claims, chunks)
- **Quality filtering + entity noise removal**
- **Agent embedding** (pdf_asset_chunks in LanceDB)
- **Literature Agent V1** (chat, dual-source retrieval, citations)
- **Agent evaluation framework** (28 cases, 100% pass)
- **Web Chat** (/chat + paper detail Ask this paper)
- **Chat UX polish** (error handling, readability, answer modes, token panel)
- **Four-intent evidence packet engine** (claim, gap, method, result)
- **Academic citation answers** (structured, cited, boilerplate-filtered)
- **Figure + Caption Extraction** (44 figures, 66% caption rate)
- **Multi-provider LLM** (DeepSeek + Anthropic, config file)
- **First-time user setup** (`Scripts/setup_llm.py`)
- **Phase 2A: Table Caption + Reference Extraction** (70 tables, 84.3% caption rate)
- **Phase 2B: Simple Table Structure Extraction** (multi-strategy parsing)
- **Phase 2C: Supplementary Table Linking** (90 references, quality guard)
- **Phase 2D: Manual Supplementary File Import** (inbox, preview, matching)
- **Phase 2E: Supplementary Entity Index** (column classification, dedup, search)
- **Phase 2F: Entity Query Intent + Chat Integration** (7 intents, LLM interpretation)
- **Phase 2G: Cross-Paper Entity Comparison** (aggregation, direction summary, LLM summary)
- Mock Data Decommission (all pages use real data)
- **v1.4** — stable release

### Upcoming
- Supplementary Import UX / Assets Viewer (Phase 2H)
- Multi-project/library support
- Zotero integration

---

## License

MIT License

---

<p align="center">
<b>Scientra Copilot</b><br>
From Literature to Discovery.
</p>
