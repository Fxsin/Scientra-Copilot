# Scientra Copilot

<p align="center">
  <h3 align="center">From Literature to Discovery</h3>
  <p align="center">AI-Powered Research Discovery Platform</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg">
  <img src="https://img.shields.io/badge/license-MIT-green.svg">
  <img src="https://img.shields.io/badge/status-active%20development-orange.svg">
</p>

---

## What is Scientra Copilot?

Scientra Copilot transforms scientific literature into structured, searchable, machine-readable knowledge. It automatically processes PDFs, extracts evidence (key results, methods, core findings, discussion points), builds semantic indexes, organizes papers into research facets with hierarchical subtopics, and exposes everything through APIs and an interactive web interface.

> **Move from collecting papers to understanding knowledge and discovering ideas.**

---

## Core Capabilities

### 📄 Literature Processing
- PDF ingestion → GROBID parsing → metadata extraction → AI summarization
- Incremental processing with resume-from-failure
- Automatic tagging and knowledge extraction

### 🔬 Evidence Extraction V2.3
- **Key results** — experimental findings with direction detection (increase/decrease/no change/association)
- **Core findings** — author-level conclusions from abstract/conclusion
- **Methods** — 73-term vocabulary matching + pattern extraction
- **Discussion points** — 7-type classification (interpretation, mechanism, comparison, limitation, etc.)
- **Result-discussion links** — automatic linking between results and their interpretations
- Multi-section fallback (Results → Discussion → Abstract → Full text)
- 1267 evidence chunks embedded in LanceDB with BGE-M3

### 🗺️ Research Map V3 — Facet-First Hierarchical
- **14 generic research facets** classify papers by research type (not by keyword similarity)
- **Hierarchical structure**: Facets → Subtopics (with controlled intent-based naming)
- **Facet View** and **Topic View** toggle
- **Topic Deduplication** — automatically merges similar clusters
- **Topic Evolution** — vertical timeline with evidence-rich phase cards (Early/Middle/Recent)
- **Evidence Coverage** tracking per topic and subtopic
- **Research Facets** distribution with horizontal bar charts
- **Phase Comparison** table across Early/Middle/Recent phases
- **Stable & cached** — consistent results via `research_map_v3_facet_hierarchical` cache

### 🔍 Evidence Search
- Search 1267 structured evidence chunks via `/query/evidence`
- Filter by chunk type: Key results, Core findings, Methods, Discussion, Limitations, Open questions
- Integrated into Topic Detail pages and available as standalone `/evidence` page
- Real-time semantic search powered by BGE-M3 + LanceDB

### 🔥 Hotspots
- **Trending Topics** — growth score based on recency + evidence richness
- **Hot Papers** — scored by recency, topic relevance, and evidence content
- **Emerging Facets** — research areas with high recent publication activity
- **Method Shifts** — detected changes in experimental methods over time
- **Evidence Signals** — chunk type distribution statistics
- Cached with automatic invalidation on research map changes

### 🕳️ Research Gaps
- Auto-detected from facet distribution analysis
- Identifies under-represented research areas (<10% paper share)
- Flags topics with low structured evidence coverage
- Method diversity assessment
- Suggested actions based on data

### 🕸️ Knowledge Network
- 123 nodes × 330 edges connecting papers, facets, subtopics, methods, and findings
- 7 edge types: paper→facet, paper→subtopic, paper→method, paper→finding, etc.
- Filterable node explorer and relationship table
- Insights based on network statistics

### 📊 Library Intelligence Report
- Auto-generated executive summary from all data modules
- Coverage summary, Research Map overview, Hotspots, Gaps, Knowledge Network
- Evidence statistics and recommended next actions
- Aggregates data from all real modules — no mock content

### 🧠 Semantic Retrieval
- Three-level search: Metadata → Summary → Chunk-level Evidence
- Keyword, Vector, and Hybrid modes
- Powered by BGE-M3 embeddings + LanceDB

### 🤖 Agent-Ready
- Query API + Agent SDK
- Context Packs with citation-grounded evidence
- Safe retrieval: agents never access raw PDFs or internal databases

---

## Web Interface — All 10 Pages with Real Data

| Page | Description | Data Source |
|------|-------------|-------------|
| `/research-map` | Facet-first hierarchical topic explorer | Research Map cache |
| `/research-map/topic/{id}` | Topic detail with evidence, evolution, search | Cache + paper metadata |
| `/library` | Paginated paper library with search/filter | `/papers` API |
| `/paper/{id}` | Paper metadata, summary, evidence, related papers | API endpoints |
| `/evidence` | Standalone evidence chunk search | `/query/evidence` |
| `/hotspots` | Trending topics, hot papers, emerging facets | `/hotspots` API |
| `/research-gaps` | Auto-detected evidence gaps and limitations | `/research-gaps` API |
| `/knowledge-network` | Paper-facet-method-finding relationship explorer | `/knowledge-network` API |
| `/report` | Auto-generated library intelligence report | `/report` API |
| `/topic-explorer` | Browse topics by research facet | `/research-map` API |

**All pages use real data. No mock/demo content in any user-facing page.**

---

## Quick Start

### Requirements
- Python 3.11+
- Docker (for GROBID)
- 8GB+ RAM

### Development Start (Recommended)

```bash
# One-command startup with port detection, cache sync, and schema validation
python Scripts/dev_restart.py

# With auto browser open
python Scripts/dev_restart.py --open

# API only
python Scripts/dev_restart.py --no-web
```

Options: `--api-port`, `--web-port`, `--kill-old`, `--no-web`, `--no-cache-clean`, `--open`, `--strict`

### Production Start

```bash
python Scripts/start_all.py              # Full: GROBID + API + Web
python Scripts/start_all.py --no-browser # Skip auto browser
python Scripts/start_all.py --api-only   # API only
```

### Import Literature

```bash
# Place PDFs in 00_Inbox/
python workflow.py run
```

Pipeline: PDF → Metadata → Tags → Summary → Evidence → Embedding → Search Index

### Rebuild Research Map

```bash
python -m scientra.research_map_builder --force
python -m scientra.research_map_builder --status
```

### Regenerate Evidence Chunks

```bash
python -m scientra.evidence_chunks --force
python -m scientra.evidence_embedding --force
```

---

## Testing

```bash
cd web

npm run test:summary-parser       # 149 tests — summary parsing integrity
npm run test:topic-evolution      # 27 tests — topic evolution analysis
npm run test:research-map         # 17 tests — research map data integrity
npm run test:hotspots             # 20 tests — hotspots real data
npm run test:knowledge-network    # 10 tests — knowledge network integrity
npm run test:report               # 15 tests — report generation
npm run test:no-mock-pages        # 4 tests — mock data guard
npm run build                     # TypeScript + Next.js build
```

---

## Architecture

```text
PDF Papers
    ↓
GROBID Parsing
    ↓
Metadata Extraction → Tags → AI Summarization
    ↓
Evidence Extraction V2.3 (key_results, core_findings, methods, discussion_points, links)
    ↓
Research Facet Classification (14 generic facets, 45 intents)
    ↓
BGE-M3 Embeddings → LanceDB (evidence_chunks + literature_vectors)
    ↓
Research Map Cache (facet-first hierarchical, stable, fingerprint-validated)
    ↓
Query API (/research-map, /hotspots, /research-gaps, /knowledge-network, /report, /query/evidence)
    ↓
Web Frontend (10 pages, all real data)
```

---

## Backend Modules

| Module | Description |
|--------|-------------|
| `scientra/evidence_extraction.py` | V2.3 engine — key_results, methods, core_findings, discussion_points, result-discussion links |
| `scientra/research_facets.py` | 14 generic research facets with 320+ signals |
| `scientra/research_map_builder.py` | Facet-first hierarchical cache builder with dedup + subtopic clustering |
| `scientra/evidence_chunks.py` | Converts evidence.json → searchable chunks |
| `scientra/evidence_embedding.py` | BGE-M3 embedding → LanceDB |
| `scientra/server.py` | FastAPI server with 10+ endpoints |
| `scientra/embedding.py` | BGE-M3 embedder wrapper |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | API + LanceDB status |
| `GET /version` | Schema version (research_map_schema: v2) |
| `GET /stats` | Paper count, tag/year distributions |
| `GET /papers` | Paginated paper list with search/filter |
| `GET /paper/{id}/metadata` | Paper metadata |
| `GET /paper/{id}/summary` | AI-generated summary |
| `GET /paper/{id}/evidence` | Structured evidence (key_results, methods, etc.) |
| `GET /paper/{id}/related` | Related papers by vector similarity |
| `GET /research-map` | Facet-first hierarchical topics + relationships |
| `GET /research-map/topic/{id}` | Topic detail, evolution phases, evidence |
| `POST /query/evidence` | Semantic evidence chunk search |
| `GET /hotspots` | Trending topics, hot papers, emerging facets |
| `GET /research-gaps` | Auto-detected research gaps |
| `GET /knowledge-network` | Paper-facet-method-finding network |
| `GET /report` | Auto-generated library intelligence report |

---

## Research Facets (14 total)

| Facet | Typical Research |
|-------|-----------------|
| Bioactivity / Phenotype | Dose-response, toxicity, efficacy |
| Structure / Modeling | Protein structure, cryo-EM, docking |
| Domain / Mutagenesis / Engineering | Domain function, mutations, chimeras |
| Target / Binding / Interaction | Receptor ID, binding assays, affinity |
| Resistance / Genetics / Adaptation | Resistance mechanisms, alleles, fitness |
| Expression / Production / Application | Recombinant expression, field trials |
| Omics / Response Profiling | Transcriptomics, proteomics, pathways |
| Method / Resource / Review | Reviews, protocols, databases |
| Gene Function / Functional Genomics | CRISPR, knockouts, overexpression |
| Genetics / QTL Mapping / GWAS | QTL, GWAS, association mapping |
| Signaling / Regulation / Pathway | Signal transduction, transcription factors |
| Development / Morphology / Physiology | Organ development, yield, architecture |
| Subcellular Localization / Trafficking | Protein localization, organelles |
| Stress Physiology / Environmental Response | Drought, salt, oxidative stress |

All facets use generic research terminology — no domain-specific hardcoding. New facets can be added via configuration.

---

## Project Structure

```text
Scientra_Copilot/
├── 00_Inbox/           # PDF import directory
├── 01_PDF/             # Processed PDFs
├── 02_Metadata/        # Extracted metadata (YAML)
├── 03_Evidence/        # Evidence extraction output (evidence.json, chunks, sections)
├── 03_Summary/         # AI-generated summaries
├── 04_VectorDB/        # LanceDB vector store
├── 05_Index/           # Research map cache + hotspots cache
├── Config/             # Workflow and extraction configuration
├── Scripts/            # Startup, dev restart, build, verification scripts
├── docs/               # Documentation
├── scientra/           # Backend Python modules
├── web/                # Next.js frontend
│   ├── app/            # Page routes (10 pages)
│   ├── components/     # Reusable UI components
│   ├── lib/            # Types, API client, topic evolution, summary parser
│   └── scripts/        # Test suites (7 test files)
├── workflow.py         # Main processing workflow
└── agent_sdk.py        # Agent SDK
```

---

## Use Cases

Scientra is domain-agnostic and works with any research field:

- Life Sciences & Medicine
- Bioinformatics & Genomics
- Plant Molecular Biology & Agriculture
- AI & Computer Science
- Materials Science & Chemistry
- Environmental Science
- Social Sciences

---

## Roadmap

### Completed ✅
- PDF Processing Pipeline
- Evidence Extraction V2.3
- Research Map V3 (facet-first hierarchical)
- Topic Evolution with evidence-rich phases
- Evidence Search (standalone + integrated)
- Hotspots (trending topics, hot papers, method shifts)
- Research Gaps (auto-detection from facet distribution)
- Knowledge Network (paper-facet-method-finding graph)
- Library Intelligence Report (auto-generated)
- Mock Data Decommission (all 10 pages use real data)
- Stable caching with fingerprint-based invalidation

### Upcoming
- User-configurable facets and intents
- Citation network extraction and visualization
- Multi-project/library support
- Collaborative workspaces
- Zotero integration

---

## Contributing

Contributions welcome. See `CONTRIBUTING.md` for development setup and guidelines.

## License

MIT License

---

<p align="center">
<b>Scientra Copilot</b><br>
From Literature to Discovery.
</p>
