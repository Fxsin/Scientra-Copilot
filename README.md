# Scientra Copilot

<p align="center">
  <h3 align="center">From Literature to Discovery</h3>
  <p align="center">AI-Powered Research Discovery Platform</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg">
  <img src="https://img.shields.io/badge/license-MIT-green.svg">
  <img src="https://img.shields.io/badge/version-v1.0--alpha-blue.svg">
  <img src="https://img.shields.io/badge/status-active%20development-orange.svg">
</p>

---

## What is Scientra Copilot?

Scientra Copilot transforms scientific literature into structured, searchable, machine-readable knowledge. It automatically processes PDFs, extracts evidence, builds semantic indexes, and provides an **AI-powered chat interface** that answers research questions grounded in your literature with traceable citations.

> **Move from collecting papers to understanding knowledge and discovering ideas.**

---

## Core Capabilities

### 💬 Literature Chat (V1.0-alpha)
- **4 intent-specific query types**: claim, research gap, method, result
- **Evidence Packet Builder** — structured Ref packets with evidence roles, method categories, gap signals
- **Academic citation format** — "Author et al. (Year) [Ref:N]" in all LLM answers
- **Boilerplate/disclaimer filter** — excludes publisher notes, copyright, data availability from answers
- **Domain-agnostic** — 88 generic scientific signals, no hardcoded research fields
- Dual-source retrieval: `pdf_asset_chunks` (2,484 rows) + `evidence_chunks` (1,267 rows)
- Three answer modes: **Auto**, **LLM synthesis**, **Evidence-only**
- Multi-provider LLM: **DeepSeek** + **Anthropic Claude**
- Paper-specific chat on every paper detail page
- Token usage & cost transparency (inline panel)
- Anti-hallucination: zero fabricated DOIs, zero `[object Object]`, zero disclaimers in answers
- 28-case evaluation framework: 100% pass rate

### 📊 PDF Data Assetization (Phase 0–1B)
- **10 asset types**: sections, methods, results, entities, claims, evidence links, agent chunks
- **Entity extraction**: 16 types (protein, gene, species, receptor, pathway, etc.)
- **Quality filtering**: entity noise removal (26% → 272 clean entities), chunk quality scoring
- **Figure extraction**: 44 figures across 30 papers, with caption extraction and rule-based type classification
- **Figure interpretation** (AI-powered, text-only): structured evidence type, strength, claims from captions
- **Agent embedding**: 2,484 quality-filtered chunks in LanceDB (BGE-M3, 1024-dim)

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
- `/query/assets` — search quality-filtered asset chunks
- `/query/evidence` — search evidence chunks
- Filter by chunk type: section, method, result, claim, figure
- BGE-M3 vector search + keyword hybrid

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

### 4. Open Chat

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

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | API + LanceDB status |
| `GET /papers` | Paginated paper list |
| `GET /paper/{id}/metadata` | Paper metadata |
| `GET /paper/{id}/summary` | AI-generated summary |
| `GET /paper/{id}/evidence` | Structured evidence |
| `POST /query/evidence` | Semantic evidence chunk search |
| **`POST /query/assets`** | **Search quality-filtered asset chunks** |
| **`POST /v1/agent/ask`** | **Literature Agent — AI-powered Q&A** |
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
┌─────────────────────────────────────────────┐
│  PDF Data Assetization Layer                │
│  sections · methods · results · entities    │
│  claims · evidence links · agent chunks      │
│  figures · figure interpretations           │
│  quality checks · noise filtering           │
└─────────────────────────────────────────────┘
    ↓
BGE-M3 Embeddings → LanceDB
├── evidence_chunks (1,267 rows)
├── literature_vectors (319 rows)
└── pdf_asset_chunks (2,484 rows)
    ↓
┌─────────────────────────────────────────────┐
│  Query Layer                                │
│  /query/assets · /query/evidence            │
│  /v1/agent/ask (Literature Agent)           │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  Literature Agent V1                        │
│  Intent Detection → Dual-Source Retrieval   │
│  → Context Merge → DeepSeek/Claude → Answer │
│  Anti-hallucination guardrails              │
│  28-case evaluation (100% pass)             │
└─────────────────────────────────────────────┘
    ↓
Web Frontend (11 pages, all real data)
Chat · Research Map · Paper Detail · Evidence · Hotspots · Gaps · Network · Report
```

---

## Backend Modules

| Module | Description |
|---|---|
| `scientra/agent/` | **Literature Agent V1** — chat, context builder, eval framework |
| `scientra/pdf_data_assets/` | **PDF Data Assetization** — builders, quality, embedding, figures |
| `scientra/evidence_extraction.py` | Evidence Extraction V2.3 |
| `scientra/embedding.py` | BGE-M3 embedder + embedding engine |
| `scientra/research_map_builder.py` | Research Map cache builder |
| `scientra/server.py` | FastAPI server (39 routes) |

---

## Project Structure

```text
Scientra_Copilot/
├── 00_Inbox/              # PDF import directory
├── 01_PDF/                # Processed PDFs
├── 02_Metadata/           # Extracted metadata (YAML)
├── 03_Evidence/           # Evidence extraction output
├── 03_Summary/            # AI-generated summaries + raw text
├── 04_VectorDB/           # LanceDB vector store
├── 05_Index/              # Research map + hotspots cache
├── 06_PDF_DataAssets/     # Structured data assets (gitignored)
├── Config/                # Configuration files
│   ├── llm_config.yaml    # LLM API key (gitignored)
│   └── pdf_data_assets.yaml
├── Scripts/               # Setup, dev restart, verification
│   ├── setup_llm.py       # First-time LLM setup
│   └── dev_restart.py     # One-command startup
├── docs/                  # Documentation
├── scientra/              # Backend Python modules
│   ├── agent/             # Literature Agent V1
│   └── pdf_data_assets/   # Data assetization
├── web/                   # Next.js frontend
│   ├── app/chat/          # Chat page
│   ├── app/paper/         # Paper detail (with Ask this paper)
│   └── components/agent/  # Shared agent UI components
├── workflow.py            # Main processing workflow
└── README.md
```

---

## LLM Setup (First-Time Users)

```bash
# Interactive setup
python Scripts/setup_llm.py

# Choose provider:
#   1. DeepSeek  (https://platform.deepseek.com)
#   2. Anthropic (https://console.anthropic.com)

# Paste your API key when prompted.
# Config saved to Config/llm_config.yaml (gitignored).
```

The Chat page defaults to **Auto** mode — uses LLM if configured, otherwise shows evidence-only fallback. No API key is ever exposed to the frontend.

---

## Testing

```bash
# Web tests
cd web
npm run test:summary-parser       # 149 tests
npm run test:no-mock-pages        # Mock data guard
npm run build                     # TypeScript + Next.js

# Agent evaluation
python -m scientra.agent.eval.regression_runner --use-llm false --case-type all

# Figure extraction test
python Scripts/test_figure_extraction.py

# API tests
python Scripts/test_query_assets_api.py
python Scripts/test_agent_api.py
```

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
- Mock Data Decommission (all pages use real data)
- **v1.0-alpha** — stable pre-release node

### Upcoming
- Figure AI Interpretation at scale (with LLM key)
- Table Extraction (Phase 2)
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
