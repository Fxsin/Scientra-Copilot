<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/version-v1.5-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/status-active%20development-orange?style=flat-square" alt="Status">
</p>

<h1 align="center">Scientra Copilot</h1>
<p align="center"><b>Local-first, evidence-oriented research discovery — from PDF collection to AI-queryable scientific memory.</b></p>

---

## Table of Contents

1. [What is Scientra Copilot?](#1-what-is-scientra-copilot)
2. [Why Scientra Copilot?](#2-why-scientra-copilot)
3. [How It Works](#3-how-it-works)
4. [Features](#4-features)
5. [Quick Start](#5-quick-start)
6. [Importing Your Literature](#6-importing-your-literature)
7. [Storage Layout v3](#7-storage-layout-v3)
8. [API Reference](#8-api-reference)
9. [Web Interface](#9-web-interface)
10. [Documentation](#10-documentation)
11. [Roadmap](#11-roadmap)
12. [Data Policy](#12-data-policy)
13. [Contributing](#13-contributing)
14. [License](#14-license)

---

## 1. What is Scientra Copilot?

**Scientra Copilot** transforms scientific literature (PDFs, supplementary Excel/CSV files, figures, tables) into **structured, searchable, AI-queryable knowledge** — all running locally on your machine.

Unlike reference managers that treat papers as opaque files, Scientra Copilot **reads and understands** your literature:

- **PDF → structured assets**: sections, methods, results, claims, figures, tables, entities — all with source traceability
- **Supplementary files → entity index**: gene lists, expression tables, bioassay results become searchable by gene/protein/compound name
- **Cross-paper comparison**: ask "where does MAP2K4 appear across papers?" and get aggregated results with direction detection
- **Evidence-grounded AI chat**: ask research questions and get answers with `[Ref:N]` citations traceable to source chunks

> Scientra Copilot is **not a cloud service**. All data stays on your machine. No internet required for core functionality. LLM integration is optional.

---

## 2. Why Scientra Copilot?

| Problem with traditional tools | Scientra Copilot's approach |
|---|---|
| PDFs are stored but their content is opaque | PDFs are parsed into structured, searchable assets |
| Supplementary files are ignored | Excel/CSV/TSV files are linked to papers and indexed by entity |
| Figures, tables, claims, methods are disconnected | All assets carry cross-references and provenance |
| Keyword search only | Semantic + evidence-oriented retrieval |
| No AI-assisted reasoning on your literature | LLM chat with `[Ref:N]` citations, grounded in your data |
| Data scattered across folders | Storage Layout v3 — 10 clean directory groups |

---

## 3. How It Works

```text
 PDF + Supplementary Files
        │
        ▼
    GROBID Parsing ──► Metadata Extraction ──► AI Summarization
        │
        ▼
    Evidence Extraction (methods, results, claims, gaps)
        │
        ▼
    PDF Data Assetization (sections, figures, tables, entities, chunks)
        │
        ▼
    Supplementary Pipeline (linking, preview, entity index, comparison)
        │
        ▼
    BGE-M3 Embeddings ──► LanceDB (3 tables, 4,234 rows)
        │
        ▼
    Query Layer (assets, evidence, entities, comparison, agent)
        │
        ▼
    Web Interface (Chat, Library, Research Map, Hotspots, Gaps, Network, Report)
```

---

## 4. Features

### 🔬 Literature Chat

7 intent-aware query types, 3 answer modes. LLM answers with `[Ref:N]` citations traceable to source chunks. Token usage transparency.

| Query Type | Example |
|---|---|
| `claim_query` | "Which claims need stronger evidence?" |
| `research_gap_query` | "What research gaps can be inferred?" |
| `method_query` | "What bioassay methods are commonly used?" |
| `result_query` | "Which results are most frequently reported?" |
| `supplementary_entity_query` | "Is MAP2K4 present in supplementary tables?" |
| `supplementary_entity_comparison_query` | "Compare MAP2K4 across supplementary data." |
| `hybrid_search` | General literature questions |

**Answer modes:** Auto (LLM if configured), LLM synthesis, Evidence-only (deterministic, no API call, <100ms).

### 📊 PDF Data Assetization

10 asset types extracted: sections, methods, results, entities, claims, evidence links, figures, tables, supplementary links, agent chunks. 11 chunk types in LanceDB. Quality filtering, entity noise removal.

### 📋 Supplementary Data Pipeline

- **Article Bundle Import**: one folder per paper — main PDF auto-detected, supplementary files auto-classified
- **Table caption extraction**: 70 tables across 56 papers (84.3% caption rate)
- **Supplementary entity index**: gene, protein, compound extraction from supplementary tables
- **Cross-paper entity comparison**: direction detection (upregulated/downregulated), value aggregation
- **Conservative LLM interpretation**: optional, strict guardrails, source_link_count warnings
- **Matching confidence gating**: label-only matches → `candidate_only` (not auto-matched); folder-explicit → high confidence

### 🗂️ Storage Layout v3

```text
00_Inbox/      Import staging (article bundles, single papers, loose supplementary)
01_Sources/    Original files (papers, supplementary, datasets)
02_Parse/      Parsed intermediates (text, figures, tables)
03_Assets/     Structured, searchable assets
04_Corpus/     Long-term corpora (writing, reasoning, data, review)
05_Knowledge/  Knowledge graph, research maps, memory
06_Index/      Search indexes — LanceDB at vector/lancedb/
07_Agents/     Agent workspaces and evaluations
08_Projects/   User project workspaces
09_Exports/    Export outputs
10_System/     Config, logs, migrations, backups, legacy archive
```

### 🌐 Web Interface

13 pages across Analysis and Data categories. See [Web Interface](#9-web-interface) for full list.

### 🔒 Local-first & Traceable

- All data stored locally. No cloud dependency.
- File manifests track provenance (SHA256, import source, binding method, confidence)
- Legacy archive preserves old data — nothing auto-deleted
- All reports use relative paths only

---

## 5. Quick Start

**Requirements:** Python 3.11+, Node.js 18+, Docker (for GROBID)

```bash
# Clone the repository
git clone <repo-url>
cd Scientra_Copilot

# One-command start (backend + frontend)
python Scripts/dev_restart.py

# Or start components separately:
python -m scientra.server          # API → http://127.0.0.1:8710
cd web && npm run dev              # Web → http://127.0.0.1:3000

# Optional: configure LLM for AI chat
python Scripts/setup_llm.py        # DeepSeek or Anthropic
```

Open **http://127.0.0.1:3000/chat** and start asking questions about your literature.

---

## 6. Importing Your Literature

### Recommended: Article Bundle Import

One folder per paper. Main PDF + supplementary files together.

```
00_Inbox/article_bundles/new/
└── Example_Paper/
    ├── main.pdf                    # Main paper (auto-detected)
    ├── Table_S1.xlsx               # Supplementary table
    ├── Table_S2.csv                # Supplementary data
    ├── Source_Data.xlsx            # Source data
    └── Supplementary_Information.pdf
```

```bash
python Scripts/process_article_bundles.py --scan
python Scripts/process_article_bundles.py --process --archive-mode copy
```

**How main PDF detection works:**
1. Filename contains `main`/`paper`/`article`/`manuscript` → priority
2. Filename contains `supplementary`/`supporting`/`appendix` → **demoted**
3. Only one PDF → auto-selected
4. Multiple PDFs, no keyword match → largest file selected (with warning)
5. No PDF → `failed_no_main_pdf`

**How supplementary binding works:**
- All non-main-PDF files in the folder are linked to that paper via **folder_explicit binding**
- Match confidence = **high** — no filename guessing needed
- **loose supplementary** (files without a parent article folder) require manual confirmation and will NOT enter entity index automatically

### Legacy: Single PDF import (still supported)

```bash
# Place PDFs in 00_Inbox/single_papers/new/
python workflow.py run
```

---

## 7. Storage Layout v3

Scientra Copilot uses a clean 10-group directory structure designed for long-term scientific knowledge building.

| Directory | Purpose | User Modifiable? |
|---|---|---|
| `00_Inbox/` | Import staging — article bundles, single papers, loose supplementary | ✅ Drop files here |
| `01_Sources/` | Original files with manifests | ❌ Managed by system |
| `02_Parse/` | Parsed text, figures, tables | ❌ Managed by system |
| `03_Assets/` | Structured assets (JSON) | ❌ Managed by system |
| `04_Corpus/` | Long-term corpora (writing, reasoning, data) | ❌ Managed by system |
| `05_Knowledge/` | Knowledge graph, maps, memory | ❌ Managed by system |
| `06_Index/` | Search indexes (LanceDB at `vector/lancedb/`) | ❌ Managed by system |
| `07_Agents/` | Agent workspaces | 🔧 For developers |
| `08_Projects/` | User project workspaces | ✅ User workspace |
| `09_Exports/` | Export outputs | ✅ Safe to read |
| `10_System/` | Config, logs, migrations, backups, legacy archive | ⚠️ Read-only |

**LanceDB primary path:** `06_Index/vector/lancedb/` — 3 tables (evidence_chunks, literature_vectors, pdf_asset_chunks), 4,234 rows.

**Legacy archive:** Old directories (01_PDF, 03_Evidence, 04_VectorDB, etc.) are preserved at `10_System/legacy_archive/`. They can be deleted after confirming all systems work.

---

## 8. API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/v1/agent/ask` | POST | Literature Agent — AI-powered Q&A with citations |
| `/query/assets` | POST | Search asset chunks (11 types, filterable) |
| `/query/evidence` | POST | Search evidence chunks |
| `/query/supplementary-entities` | POST | Search indexed supplementary entities |
| `/query/supplementary-entity-comparison` | POST | Cross-paper entity comparison |
| `/health` | GET | API and LanceDB status |

**SDK usage:**

```python
from scientra.sdk import (
    query_assets,
    query_supplementary_entities,
    query_supplementary_entity_comparison,
    ask_literature,
)

# Search assets
r = query_assets("protein expression", top_k=10, chunk_types=["method"])
print(r["count"])  # number of results

# Search supplementary entities
r = query_supplementary_entities("MAP2K4", entity_type="gene")
for match in r["matches"]:
    print(match["entity_text"], match["value_columns"])

# Cross-paper comparison
r = query_supplementary_entity_comparison("MAP2K4")
print(r["total_matches"], r["direction_summary"])

# AI-powered Q&A
r = ask_literature("What does MAP2K4 show in supplementary data?", use_llm=False)
print(r["answer"])
```

---

## 9. Web Interface

| Page | Description | Status |
|---|---|---|
| `/chat` | AI literature chat — 7 query types, cited answers | ✅ |
| `/library` | Paginated paper library with search and filter | ✅ |
| `/paper/{id}` | Paper detail: metadata, summary, evidence, "Ask this paper" | ✅ |
| `/evidence` | Evidence chunk search with type filter | ✅ |
| `/research-map` | Facet-first hierarchical topic explorer | ✅ |
| `/hotspots` | Trending topics, hot papers, emerging facets | ✅ |
| `/research-gaps` | Auto-detected evidence gaps | ✅ |
| `/knowledge-network` | Paper-facet-method-finding network graph | ✅ |
| `/report` | Auto-generated library intelligence report | ✅ |
| `/topic-explorer` | Browse topics by research facet | ✅ |
| `/import` | Import dashboard — article bundles, supplementary status | 🔨 Planned |
| `/assets` | Assets viewer — browse figures, tables, entities | 🔨 Planned |
| `/settings` | Application settings | ✅ |

---

## 10. Documentation

| Document | Format | Language |
|---|---|---|
| [User Manual v2.0](Scientra_Copilot_User_Manual_v2_bilingual.docx) | Word | English + 中文 |
| [User Manual v2.0 (Markdown)](docs/manual/Scientra_Copilot_User_Manual_v2_bilingual.md) | Markdown | English + 中文 |
| [File Placement Guide / 文件存放指引](docs/manual/Scientra_Copilot_文件存放指引_v1.md) | Markdown | English + 中文 |
| [File Placement Guide / 文件存放指引 (DOCX)](docs/manual/Scientra_Copilot_文件存放指引_v1.docx) | Word | English + 中文 |
| [Storage Layout Config](Config/storage_layout.yaml) | YAML | — |
| [Article Bundle Import Guide](docs/article_bundle_import_v1.md) | Markdown | English |

---

## 11. Roadmap

**Short-term (v1.6)**
- Import Dashboard and Assets Viewer web pages
- Manual Binding UI for loose supplementary files

**Mid-term (v1.7–1.8)**
- Corpus builders: expression, introduction, discussion, method, claim, gap
- Dataset / Gene Evidence expansion
- Cross-study entity comparison enhancements

**Long-term (v2.0+)**
- Knowledge Graph (nodes, edges, snapshots)
- Scientific Memory (field, project, topic)
- Scientific Reasoning Engine
- Experimental Design Agent
- AI Reviewer Agent

---

## 12. Data Policy

- **No automatic deletion**: all file operations default to `copy` mode. `move` requires explicit `--archive-mode move`.
- **Legacy archive**: old directories preserved at `10_System/legacy_archive/`. Safe to delete after verification.
- **API keys**: stored in `Config/llm_config.yaml` (gitignored). Never committed.
- **Relative paths only**: all reports, manifests, and API responses use relative paths.
- **LanceDB**: stored at `06_Index/vector/lancedb/`. Backups at `10_System/backups/`.
- **User data**: papers, supplementary files, and generated data should NOT be committed to git.

---

## 13. Contributing

This project is under active development. Contributions are welcome.

```bash
# Run tests
python Scripts/test_storage_layout_v3.py
python Scripts/test_query_assets_api.py
python Scripts/test_supplementary_entity_index.py

# Build web frontend
cd web && npm run build
```

---

## 14. License

MIT License — see [LICENSE](LICENSE) file.

---

<p align="center"><b>Scientra Copilot</b> — From Literature to Discovery.</p>

---

# 中文版本

## 1. 项目简介

**Scientra Copilot** 是一个本地优先、证据导向的科研文献发现平台。它将科学论文（PDF）、补充文件（Excel/CSV/TSV）、图表和表格转化为**结构化、可检索、可供 AI 查询的知识**——全部运行在你的本地机器上。

核心能力：

- **PDF → 结构化资产**：章节、方法、结果、论断、图表、表格、实体——全部带溯源
- **补充文件 → 实体索引**：基因列表、表达表格、生测结果可按基因/蛋白质/化合物名搜索
- **跨论文比较**：问"MAP2K4 在哪些论文的补充数据中出现？"得到聚合结果
- **证据驱动的 AI 对话**：文献问答带 `[Ref:N]` 引用，可追溯到源片段

> Scientra Copilot **不是云服务**。所有数据在你的电脑上。LLM 集成是可选的。

## 2. 为什么需要 Scientra Copilot？

| 传统工具的问题 | Scientra Copilot 的做法 |
|---|---|
| PDF 只是存储，内容不透明 | PDF 被解析为结构化、可检索的资产 |
| 补充文件被忽略 | Excel/CSV/TSV 与论文关联并按实体索引 |
| 图表、表格、论断、方法相互孤立 | 所有资产带有交叉引用和溯源 |
| 只有关键词搜索 | 语义 + 证据导向检索 |
| 不能在自有文献上做 AI 辅助推理 | LLM 对话带 `[Ref:N]` 引用，基于你的数据 |
| 数据分散在各处 | Storage Layout v3——10 组清晰目录 |

## 3. 工作流程

```text
 PDF + 补充文件
        │
        ▼
    GROBID 解析 ──► 元数据提取 ──► AI 摘要
        │
        ▼
    证据提取（方法、结果、论断、空白）
        │
        ▼
    PDF 数据资产化（章节、图表、表格、实体、片段）
        │
        ▼
    补充数据流水线（关联、预览、实体索引、比较）
        │
        ▼
    BGE-M3 嵌入 ──► LanceDB（3 表，4,234 行）
        │
        ▼
    查询层（资产、证据、实体、比较、智能体）
        │
        ▼
    Web 界面（对话、文库、研究地图、热点、空白、网络、报告）
```

## 4. 功能概览

### 🔬 文献对话

7 种意图识别，3 种回答模式。LLM 回答带 `[Ref:N]` 引用。Token 用量透明显示。

**3 种回答模式：** Auto（自动判断）、LLM synthesis（LLM 综合）、Evidence-only（纯证据，无 API 调用，<100ms）。

### 📊 PDF 数据资产化

10 种资产类型，11 种 LanceDB 片段类型。质量过滤，实体去噪。

### 📋 补充数据流水线

- **Article Bundle Import**：一篇文章一个文件夹——正文自动识别，补充文件自动分类
- **表格标题提取**：56 篇论文 70 张表格（84.3% 标题率）
- **补充实体索引**：从补充表格提取基因、蛋白质、化合物
- **跨论文实体比较**：方向检测（上调/下调），数值聚合
- **保守 LLM 解释**：可选，带严格安全限制
- **匹配置信度控制**：仅标签匹配 → `candidate_only`；文件夹绑定 → high confidence

## 5. 快速开始

**环境：** Python 3.11+, Node.js 18+, Docker（用于 GROBID）

```bash
git clone <repo-url>
cd Scientra_Copilot

# 一键启动
python Scripts/dev_restart.py

# 或分别启动：
python -m scientra.server          # API → http://127.0.0.1:8710
cd web && npm run dev              # Web → http://127.0.0.1:3000

# 配置 LLM（可选）
python Scripts/setup_llm.py        # DeepSeek 或 Anthropic
```

打开 **http://127.0.0.1:3000/chat** 开始对话。

## 6. 文档

| 文档 | 格式 | 语言 |
|---|---|---|
| [用户手册 v2.0](Scientra_Copilot_User_Manual_v2_bilingual.docx) | Word | English + 中文 |
| [用户手册 v2.0 (Markdown)](docs/manual/Scientra_Copilot_User_Manual_v2_bilingual.md) | Markdown | English + 中文 |
| [文件存放指引](docs/manual/Scientra_Copilot_文件存放指引_v1.md) | Markdown | English + 中文 |
| [文件存放指引 (DOCX)](docs/manual/Scientra_Copilot_文件存放指引_v1.docx) | Word | English + 中文 |
| [Storage Layout 配置](Config/storage_layout.yaml) | YAML | — |

## 7. 路线图

**近期（v1.6）**：导入仪表盘、资产查看器、手动绑定界面

**中期（v1.7–1.8）**：语料构建器、基因证据扩展、跨研究比较增强

**远期（v2.0+）**：知识图谱、科学记忆、推理引擎、实验设计助手、AI 审稿助手

## 8. 数据安全

- **不自动删除**：所有文件操作默认 `copy` 模式
- **旧数据归档**：旧目录保留在 `10_System/legacy_archive/`
- **API key**：保存在 `Config/llm_config.yaml`（已 gitignore）
- **仅使用相对路径**：所有报告和清单使用相对路径
- **LanceDB**：`06_Index/vector/lancedb/`，备份在 `10_System/backups/`

## 9. 许可证

MIT License

---

<p align="center"><b>Scientra Copilot</b> — From Literature to Discovery.</p>
