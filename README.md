# Scientra Copilot

<p align="center">
  <h3 align="center">From Literature to Discovery</h3>
  <p align="center">
    AI-Powered Research Discovery Platform
  </p>
</p>

<p align="center">
Transform scientific literature into structured knowledge, research maps, semantic retrieval systems, and agent-ready workflows.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg">
  <img src="https://img.shields.io/badge/license-MIT-green.svg">
  <img src="https://img.shields.io/badge/status-active%20development-orange.svg">
</p>

---

# What is Scientra Copilot?

Scientra Copilot is an AI-powered research discovery platform designed for researchers, engineers, and AI agents.

Unlike traditional reference managers that focus on storing PDFs and citations, Scientra transforms scientific literature into a structured, searchable, and machine-readable knowledge system.

The goal is simple:

> Move researchers from collecting papers to understanding knowledge and discovering ideas.

Scientra automatically processes research papers, extracts structured information, generates summaries, builds semantic indexes, and exposes the resulting knowledge through APIs and Agent SDKs.

Whether you are a scientist building a literature database, an AI engineer creating research agents, or a student exploring a new field, Scientra provides a unified foundation for literature-driven research.

---

# Why Scientra?

Most literature tools solve only one piece of the workflow:

| Tool             | Primary Focus                                                 |
| ---------------- | ------------------------------------------------------------- |
| Zotero           | Reference Management                                          |
| EndNote          | Citation Management                                           |
| Mendeley         | Library Organization                                          |
| ResearchRabbit   | Literature Exploration                                        |
| NotebookLM       | Document Q&A                                                  |
| Scientra Copilot | Knowledge Extraction + Research Discovery + Agent Integration |

Scientra is designed as a complete research knowledge platform rather than a PDF storage system.

---

# Architecture Overview

```text
PDF Papers
    ↓
GROBID Parsing
    ↓
Metadata Extraction
    ↓
Knowledge Tagging
    ↓
AI Summarization
    ↓
BGE-M3 Embeddings
    ↓
LanceDB Knowledge Store
    ↓
Query API
    ↓
Agent SDK
    ↓
Scientra Copilot
```

---

# Core Capabilities

## 📄 Literature Processing Pipeline

Automatically converts raw scientific PDFs into structured research assets.

Features:

* PDF ingestion
* GROBID parsing
* Metadata extraction
* DOI recognition
* Structured summaries
* Incremental processing
* Resume-from-failure workflow

---

## 🏷️ Knowledge Extraction

Scientra transforms papers into searchable knowledge.

Current extraction layers:

* Metadata
* Tags
* Summaries
* Evidence Chunks
* Embeddings

Future layers:

* Topic Extraction
* Citation Networks
* Research Evolution Tracking

---

## 🧠 Semantic Retrieval

Three-level retrieval architecture:

* Metadata Search
* Summary Search
* Chunk-Level Evidence Search

Supported modes:

* Keyword Search
* Vector Search
* Hybrid Search

Powered by:

* BGE-M3
* LanceDB

---

## 🗺️ Research Discovery

Scientra goes beyond document retrieval.

Researchers can explore:

* Related Papers
* Knowledge Networks
* Research Maps
* Topic Clusters
* Emerging Research Areas
* Potential Research Gaps

The objective is not only to find papers but to understand the structure of a research field.

---

## 🤖 Agent-Ready Design

Scientra is designed from the beginning for AI agents.

Agents never access:

* Raw PDFs
* Internal databases
* Vector stores

Instead they interact through:

* Query API
* Agent SDK
* Context Packs
* Citation-Grounded Evidence

This architecture provides:

* Traceability
* Reproducibility
* Safer retrieval
* Model independence

---

# Current Modules

## Backend

* PDF Engine
* Metadata Engine
* Tag Engine
* Summary Agent
* Embedding Engine
* Query API
* Agent SDK
* Workflow Engine

## Frontend

* Dashboard
* Library
* Import Center
* Knowledge Explorer
* Research Map
* AI Chat (Context Mode)

## Infrastructure

* GROBID
* LanceDB
* BGE-M3
* FastAPI
* SQLite

---

# Quick Start

## Requirements

* Python 3.11+
* Docker
* 8GB+ RAM
* GROBID
* BGE-M3

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/scientra-copilot.git

cd scientra-copilot

pip install -r requirements.txt
```

---

## Start Scientra

### Quick Start

```bash
python Scripts/start_all.py
```

This automatically starts:
* GROBID (Docker)
* Query API
* Web Frontend
* Opens browser to the Web UI

> **Note:** The script now runs a preflight check before starting services.
> If any issues are found, it displays clear error messages with solutions.

### Custom Ports

If the default ports (3000 for Web, 8710 for API, 18070 for GROBID) are occupied,
configure custom ports via environment variables:

**Windows PowerShell:**
```powershell
$env:SCIENTRA_WEB_PORT="3001"
$env:SCIENTRA_API_PORT="8720"
$env:SCIENTRA_GROBID_PORT="18071"
python Scripts/start_all.py
```

**Linux/macOS:**
```bash
SCIENTRA_WEB_PORT=3001 SCIENTRA_API_PORT=8720 python Scripts/start_all.py
```

### Command Options

```bash
python Scripts/start_all.py              # Full startup (GROBID + API + Web)
python Scripts/start_all.py --no-browser # Don't open browser automatically
python Scripts/start_all.py --api-only   # Only GROBID + API, skip Web
python Scripts/start_all.py --web-only   # Only Web frontend
```

### Startup Diagnostics

Each run generates a diagnostics report at `reports/startup_diagnostics_report.md`
containing port detection results, service status, and failure recommendations.

### Common Issues

<details>
<summary><b>Web port 3000 is occupied</b></summary>

Scientra Copilot auto-detects port conflicts and finds the next available port
(3001, 3002, ...). You will see a message like:

```
Port 3000 is occupied. Using port 3001 instead.
```

To permanently change the default Web port:
```powershell
$env:SCIENTRA_WEB_PORT="3005"
python Scripts/start_all.py
```
</details>

<details>
<summary><b>API port 8710 is occupied</b></summary>

If port 8710 is occupied by a non-Scientra process, you will see an error
with the process name and PID. Solutions:

1. Close the conflicting program.
2. Use a different port:
```powershell
$env:SCIENTRA_API_PORT="8720"
python Scripts/start_all.py
```
</details>

<details>
<summary><b>GROBID port 18070 is occupied</b></summary>

If port 18070 is occupied but the service is not GROBID, you will see an error.
Solutions:

1. Close the conflicting program.
2. Use a different port:
```powershell
$env:SCIENTRA_GROBID_PORT="18071"
python Scripts/start_all.py
# Then create the GROBID container with the new port:
docker run -d --name scientra_grobid -p 18071:8070 -p 18072:8071 lfoppiano/grobid:0.8.1
```
</details>

<details>
<summary><b>Docker Desktop is not running</b></summary>

Error message:
```
Docker Desktop is installed but the Docker daemon is not running.
Please open Docker Desktop and wait for it to fully start.
```

Open Docker Desktop from the Start Menu and wait for the whale icon to
stop animating, then re-run `python Scripts/start_all.py`.
</details>

<details>
<summary><b>Web frontend is slow on first run</b></summary>

Next.js/Turbopack compiles the application on first run, which can take
1-2 minutes. You will see:

```
Web frontend is compiling (Next.js/Turbopack). This may take 1-2 minutes on first run...
```

The startup script now waits up to 120 seconds. Subsequent starts are much faster.
</details>

<details>
<summary><b>Browser doesn't open automatically</b></summary>

If the browser doesn't open, you can manually visit the Web URL shown in the
startup output. For example: `http://localhost:3000`

Use `--no-browser` to skip auto-opening:
```bash
python Scripts/start_all.py --no-browser
```
</details>

---

## Import Literature

Place PDFs into:

```text
00_Inbox/
```

Run:

```bash
python workflow.py run
```

The workflow will automatically:

```text
PDF
→ Metadata
→ Tags
→ Summary
→ Embedding
→ Search Index
```

---

## Web 显示 Demo Data 排查指南

如果浏览器打开了 Scientra Copilot 但页面显示 demo/mock 数据而不是你的真实文献，
请按以下步骤排查：

### 1. 运行验证脚本

```bash
python Scripts/verify_real_data.py
```

该脚本自动检查 API、CORS、Web 是否正常工作。全部 PASS 即为正常。

### 2. 确认服务都在运行

| 服务 | 默认地址 | 检查方式 |
|------|---------|---------|
| GROBID | `http://localhost:18070` | `curl http://localhost:18070/api/isalive` |
| API | `http://127.0.0.1:8710` | `curl http://127.0.0.1:8710/health` |
| Web | `http://localhost:3000` | 浏览器直接打开 |

### 3. 确认 API 返回真实数据

```bash
curl http://127.0.0.1:8710/stats
# 应返回: {"paper_count": 55, ...}
```

如果 `paper_count` 为 0，需要先运行工作流：`python workflow.py run`

### 4. 确认 CORS 配置生效

在浏览器中按 F12 → Console，如果看到 CORS 相关错误，
说明 API 的跨域配置未生效。重启 API 服务即可：

```bash
python Scripts/run_api_server.py --port 8711 --host 0.0.0.0
```

然后重启 Web 时指定新的 API 地址：

```powershell
$env:NEXT_PUBLIC_SCIENTRA_API_URL="http://127.0.0.1:8711"
cd web && npm run dev -- -p 3000
```

### 5. 清除 Web 编译缓存

如果 API 地址变更后 Web 仍访问旧地址：

```bash
rm -rf web/.next
cd web && npm run dev -- -p 3000
```

### 已知问题 (V1.1 已修复)

| 问题 | 根因 | 状态 |
|------|------|:--:|
| Parse 步骤零处理 | Config 中 `--check-grobid` 导致早期退出 | ✅ |
| 模块找不到 (`No module named 'scientra'`) | `cwd` 指向父目录 + PYTHONPATH 缺失 | ✅ |
| Windows 状态文件 PermissionError | `os.replace` 无重试 | ✅ |
| 已有 PDF 未被识别 | `import_pdf` 仅扫描 `00_Inbox/` | ✅ |
| API 搜索返回 0 结果 | `PROJECT_ROOT` 指向 `scientra/` 子目录 | ✅ |
| Web 显示 Demo Data | CORS 配置使用不支持的端口通配符 `localhost:*` | ✅ |
| Library 页面报错 `paper_count` | Hook 返回值格式变更未同步页面 | ✅ |
| Research Map 显示全零 | API 返回空数组时未回退 mock 数据 | ✅ |
| Settings 显示过时信息 | 硬编码旧数据（34 papers, Mock Intelligence Layer） | ✅ |
| Web 启动超时误报 | Next.js 首次编译 >30s 但脚本判定失败 | ✅ |
| 端口冲突无提示 | 固定端口无检测机制 | ✅ |

---

# Project Structure

```text
Scientra_Copilot/

00_Inbox/
01_PDF/
02_Metadata/
03_Summary/
04_VectorDB/
05_Index/

06_API/
07_Workflows/
08_Agent_Interface/

Config/
Scripts/
docs/
Tests/

workflow.py
agent_sdk.py
```

---

# Use Cases

Scientra can be used in:

* Life Sciences
* Medicine
* Bioinformatics
* AI & Computer Science
* Materials Science
* Chemistry
* Environmental Science
* Social Sciences

and any research field that relies on literature analysis.

---

# Roadmap

## Current

* PDF Processing Pipeline
* Knowledge Extraction
* Semantic Retrieval
* Research Maps
* Knowledge Explorer
* Agent SDK

## Upcoming

* Topic Engine
* AI Research Copilot
* Citation Extraction
* Citation Network
* Research Evolution Analysis

## Long-Term

* Word Integration
* Zotero Integration
* Cloud Workspace
* Multi-Agent Research Workflows

---

# 中文简介

## Scientra Copilot 是什么？

Scientra Copilot 是一个面向科研工作者的 AI 研究发现平台（AI-Powered Research Discovery Platform）。

与传统文献管理工具不同，Scientra 不仅关注 PDF 存储和文献引用管理，更关注将文献转化为结构化知识，并进一步支持 AI Agent 调用和科研发现。

核心理念：

> 从文献到知识，从知识到发现。

---

## 核心能力

### 📄 文献自动处理

* PDF 导入
* GROBID 解析
* Metadata 提取
* 标签生成
* AI 摘要

### 🧠 知识发现

* Knowledge Explorer
* Research Map
* Related Papers
* Semantic Search
* Topic Discovery

### 🤖 Agent 调用

* Query API
* Agent SDK
* Context Pack
* AI Copilot

---

## 适用于

* 生物学
* 医学
* 材料科学
* AI与计算机科学
* 化学
* 环境科学
* 社会科学

以及所有依赖文献调研的科研领域。

---

# Contributing

Contributions are welcome.

Please see:

```text
CONTRIBUTING.md
```

for development setup and contribution guidelines.

---

# License

MIT License

---

<p align="center">
<b>Scientra Copilot</b><br>
From Literature to Discovery.
</p>
