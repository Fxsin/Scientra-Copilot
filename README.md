# Scientra Copilot — Your Literature, Structured

<p align="center">
  <b>LLM-Powered Literature Knowledge OS for Researchers</b><br>
  <sub>PDF → GROBID → Metadata → Tags → Summary → Embedding → LanceDB → API → Your Agent</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/version-0.2.0-orange.svg" alt="Version 0.2.0">
</p>

---

## What is Scientra Copilot?

Scientra Copilot transforms raw PDFs into a **structured, searchable, AI-consumable knowledge base**. It's not a PDF manager — it's a literature operating system designed for the age of AI agents.

```mermaid
flowchart LR
    PDF[📄 PDF] -->|GROBID| Parse[Parse]
    Parse --> Meta[📋 Metadata]
    Meta --> Tag[🏷️ Tag Engine]
    Tag --> Summary[📝 Summary Agent]
    Summary --> Embed[🧠 BGE-M3 Embed]
    Embed --> LanceDB[(🗄️ LanceDB)]
    LanceDB --> API[🔌 Query API]
    API --> Agent[🤖 Your Agent]
```

## ✨ Features

- **🔬 Zero-Config PDF Pipeline** — Drop PDFs in, get structured knowledge out. GROBID parsing with automatic retry and health checks.
- **🏷️ Rule-Based Tag Engine** — No LLM hallucinations. Ontology-driven tagging across TOXIN, HOST, MECHANISM, and METHOD dimensions.
- **📝 Dual-Mode Summary Agent** — Works with any LLM (Anthropic, DeepSeek, OpenAI-compatible). Falls back to prompt-file mode when no API key is available — resolved by Claude Code or any local agent.
- **🧠 Three-Level Vector Index** — BGE-M3 embeddings at metadata, summary, and chunk levels for precise retrieval at any granularity.
- **🔍 Hybrid Search** — Keyword + vector combined scoring with domain-specific field weights. Filter by toxin, species, mechanism, method, year, and DOI.
- **🛡️ Agent-First Design** — Single entry point `literature_query()`. Policy enforcement prevents agents from accessing raw PDFs, SQLite, or LanceDB directly. Every result has a traceable citation anchor.
- **⚡ Incremental Processing** — SHA256-based change detection. Only re-process what changed. Resume from any failed step.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker (for GROBID)
- 8GB+ RAM (for BGE-M3 embedding)

### 1. Clone & Install

```bash
git clone https://github.com/your-org/scientra-copilot.git
cd scientra-copilot
pip install -r requirements.txt

# Run environment check (verifies everything is ready)
python Scripts/setup_check.py
```

### 2. Start GROBID

**First time?** One command sets up everything automatically:

```bash
python Scripts/setup_grobid.py
```

This checks Docker, pulls the GROBID image, creates the container, and waits until it's ready.

**Already have Docker?** Manual one-liner:

```bash
docker run -d --name scientra_grobid -p 18070:8070 --restart unless-stopped lfoppiano/grobid:0.8.1
```

**No Docker?** [Install Docker Desktop](https://docs.docker.com/desktop/) first, then run either command above.

> 💡 The pipeline auto-detects GROBID status. If the container doesn't exist, `ensure_grobid.py` will create it for you — no manual setup needed on subsequent runs.

### 3. Drop PDFs & Run

```bash
# Put your PDFs in 00_Inbox/ or 01_PDF/
python workflow.py --all
```

That's it. Your literature is now a searchable knowledge base.

## 🔌 API & SDK

### Start the API server

```bash
python Scripts/run_api_server.py
# Server running at http://localhost:8800
```

### Query via REST

```bash
curl -X POST http://localhost:8800/v1/scientra/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Vip3Aa receptor resistance mechanism", "mode": "hybrid", "top_k": 5}'
```

### Query via Python SDK

```python
from agent_sdk import search, get_summary, get_evidence

# Hybrid search
results = search("Cry toxin receptor binding", query_type="hybrid_search", top_k=10)
for paper in results.papers:
    print(f"[{paper.year}] {paper.title}")
    print(f"  Toxin: {paper.toxin}, Mechanism: {paper.mechanism}")

# Get structured summary
summary = get_summary("paper_2247e647bb604df2")

# Get evidence chain with citations
evidence = get_evidence(query="Cry1Ac resistance ABC transporter", top_k=10)
```

## 📁 Project Structure

```
scientra-copilot/
├── 00_Inbox/            # Pending input (drop PDFs here)
├── 01_PDF/              # Source PDFs
├── 02_Metadata/         # Extracted metadata (YAML/JSON)
├── 03_Summary/          # Structured summaries & raw text
├── 04_VectorDB/         # LanceDB vector index
├── 05_Index/            # Tags, reports, embedding plans
├── 06_API/              # FastAPI query server
├── 07_Workflows/        # Pipeline orchestration
├── 08_Agent_Interface/  # Agent SDK contracts
├── Config/              # YAML configuration files
├── Scripts/             # CLI tools & utilities
├── docs/                # Architecture & design docs
├── Tests/               # Test suite
├── agent_sdk.py         # Public Agent SDK
├── workflow.py          # Pipeline entry point
└── pyproject.toml       # Project metadata
```

## 🏗️ Architecture

Scientra Copilot is a **one-way gate architecture**: PDFs enter on the left, structured knowledge exits on the right. No step can mutate upstream data.

See [Architecture Docs](docs/Scientra_Copilot_Architecture.md) for full design details, including:

- 8-step pipeline with state-machine resume
- Three-level embedding index strategy
- Tag Engine ontology design
- Hybrid search merge algorithm
- Agent SDK policy enforcement

## 🤝 Integrations

Scientra Copilot is designed to be called by any AI agent:

| Integration | Method | Guide |
|-------------|--------|-------|
| Claude Code | SDK (local mode) | [Agent SDK Design](docs/Agent_SDK_Design.md) |
| Any Web Agent | REST API | [Query API Design](docs/Query_API_Design.md) |
| MCP Clients | MCP Bridge (optional) | [Skill Integration Guide](docs/Skill_Integration_Guide.md) |

## 📊 Performance

| Operation | Typical Latency | Notes |
|-----------|----------------|-------|
| GROBID parse | 2-5s / paper | Depends on GROBID server |
| Tag assignment | <1s / paper | Pure rule matching |
| Summary (cached) | <1ms | Uses SHA256 cache key |
| Summary (LLM) | 3-15s | Depends on model/API |
| BGE-M3 embedding | 15-30s / paper | CPU; faster on GPU |
| Vector search | 100-500ms | LanceDB ANN |
| Keyword search | <10ms | In-memory scoring |

## 🧪 Running Tests

```bash
python -m pytest Tests/ -v
```

## 📖 Documentation

- [Architecture](docs/Scientra_Copilot_Architecture.md)
- [User Manual](docs/Scientra_Copilot_Manual.md)
- [Agent SDK Design](docs/Agent_SDK_Design.md)
- [Query API Design](docs/Query_API_Design.md)
- [Tag Engine Design](docs/Tag_Engine_Design.md)
- [Embedding Engine Design](docs/Embedding_Engine_Design.md)
- [Workflow Engine Design](docs/Workflow_Engine_Design.md)

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Scientra Copilot</b> — Your Literature, Structured.<br>
  Built for researchers. Designed for agents.
</p>
