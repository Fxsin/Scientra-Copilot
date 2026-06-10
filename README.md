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

Windows:

```bash
start_scientra.bat
```

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File start_scientra.ps1
```

This automatically starts:

* GROBID
* Query API
* Web Frontend

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
