# Scientra Copilot — 完整用户手册

版本：v0.2.0 | 更新日期：2026-06-10

---

## 目录

1. [Scientra Copilot 是什么](#1-scientra-copilot-是什么)
2. [系统各组件的作用](#2-系统各组件的作用)
3. [安装与首次设置](#3-安装与首次设置)
4. [完整工作流程](#4-完整工作流程)
5. [如何检索文献](#5-如何检索文献)
6. [Agent SDK 使用指南](#6-agent-sdk-使用指南)
7. [API 服务](#7-api-服务)
8. [配置说明](#8-配置说明)
9. [常见问题与故障排查](#9-常见问题与故障排查)
10. [进阶用法](#10-进阶用法)

---

## 1. Scientra Copilot 是什么

Scientra Copilot 是一个**文献知识操作系统**。它把 PDF 论文转换成可检索、可引用、可被 AI Agent 安全访问的结构化知识库。

### 它不是什么

- 不是 PDF 管理器（不会帮你整理文件）
- 不是 Zotero / EndNote 替代品（不管理引用格式）
- 不是论文写作工具

### 核心设计原则

```
PDF(数据源) → Metadata(元数据层) → Tag(标签层) → Summary(知识层) → Embedding(向量化) → LanceDB(检索层) → API(查询边界) → Agent(消费层)
```

**单向门架构**：数据只能从左往右流，下游不能修改上游数据。Agent 必须通过 `literature_query()` 唯一入口访问文献知识，禁止直接接触 PDF、SQLite 或 LanceDB。

---

## 2. 系统各组件的作用

### 2.1 GROBID — PDF 结构解析引擎

**作用**：把 "人读" 的 PDF 变成 "机器读" 的结构化文本。识别标题、作者、摘要、正文段落、参考文献。

**为什么需要它**：PDF 是为打印设计的格式，不是为机器阅读设计的。没有 GROBID，PDF 就是一堆无法检索的二进制数据。

**运行方式**：Docker 容器，监听 18070 端口。Scientra Copilot 通过 HTTP API 调用。

### 2.2 Tag Engine — 标签引擎

**作用**：基于规则给每篇论文打四维标签，不使用 LLM（无幻觉风险，结果可重复）。

| 维度 | 说明 | 示例 |
|------|------|------|
| TOXIN | 毒素类型 | Cry1Ac, Vip3Aa, Cyt1Aa, Tc |
| HOST | 宿主生物 | Helicoverpa, C. elegans, Drosophila |
| MECHANISM | 作用机制 | Receptor binding, Pore formation, Resistance |
| METHOD | 实验方法 | CRISPR screen, Cryo-EM, RNAi |

配置文件：`Config/tag_ontology.yaml`（类别定义）、`Config/tag_dictionary.yaml`（匹配规则）。

### 2.3 Summary Agent — 摘要生成器

**作用**：为每篇论文生成 6 节结构化摘要（Core Finding / Evidence / Methods / Key Results / Limitations / Relevance）。

**两种模式**：
- **Agent Mode**（默认）：有 API Key 时自动调用 LLM 生成摘要
- **Prompt-Only Mode**：无 API Key 时生成 prompt 文件，等待人工或 Agent 处理

摘要是一级知识层——第一个 "人可以直接读" 的知识产物，也是后续向量检索的重要数据源。

### 2.4 BGE-M3 Embedding — 向量嵌入引擎

**作用**：用 BAAI/bge-m3 模型把文本变成 1024 维数学向量，实现语义相似度搜索。

**三层索引**：metadata（论文级）→ summary（章节级）→ chunk（段落级），支持不同粒度的检索。首次使用会下载约 2GB 模型文件。

### 2.5 LanceDB — 嵌入式向量数据库

**作用**：存储和检索向量。不需要单独服务器，数据直接存在 `04_VectorDB/lancedb/`。支持毫秒级 ANN（近似最近邻）搜索。

### 2.6 Query API — 统一查询边界

**作用**：所有搜索必须通过 API。支持三种检索模式：关键词（<10ms）、向量（100-500ms）、混合（100-500ms）。

### 2.7 Agent SDK — 安全查询接口

**作用**：为 AI Agent 提供四个安全函数：`search()`、`retrieve()`、`get_summary()`、`get_evidence()`。运行时强制检查——禁止 Agent 直接访问 PDF、SQLite 或 LanceDB。

### 2.8 Workflow Runner — 工作流引擎

**作用**：编排 import_pdf → parse → metadata → tag → summary → embedding → lancedb → index_update 八步流水线。支持 SHA256 增量处理和断点恢复。

---

## 3. 安装与首次设置

### 3.1 系统要求

| 组件 | 要求 |
|------|------|
| Python | 3.11+ |
| Docker | Docker Desktop 20.10+ |
| 内存 | 8GB+（16GB 推荐，BGE-M3 需约 2.5GB） |
| 磁盘 | 5GB+（含模型缓存和向量数据） |

### 3.2 安装步骤

```bash
# 1. 克隆
git clone https://github.com/your-org/scientra-copilot.git
cd scientra-copilot

# 2. 安装依赖
pip install -r requirements.txt

# 3. 环境检查（验证所有依赖就绪）
python Scripts/setup_check.py
```

### 3.3 GROBID 设置

**自动设置（推荐新手）**：

```bash
python Scripts/setup_grobid.py
```

这个命令自动完成：检查 Docker → 拉取镜像 → 创建容器 → 等待就绪。

**手动一条命令**：

```bash
docker run -d --name scientra_grobid -p 18070:8070 --restart unless-stopped lfoppiano/grobid:0.8.1
```

**验证**：`curl http://localhost:18070/api/isalive` 应返回 `true`。首次启动需等待 30-60 秒加载模型。

### 3.4 API Key（可选）

没有 API Key 也能用——摘要会生成 prompt 文件由 Claude Code Agent 处理。

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Linux/Mac
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## 4. 完整工作流程

### 4.1 第一次运行

```bash
# 1. 把 PDF 放入 00_Inbox/
# 2. 运行流水线
python workflow.py --all
```

### 4.2 常用命令

```bash
python workflow.py --all                  # 全量处理
python workflow.py --all --changed-only   # 仅处理新文件
python workflow.py --all --resume         # 从失败步骤恢复
python workflow.py --all --dry-run        # 预览（不执行）
python workflow.py --all --from-step tag --force  # 从 tag 步骤重新开始
python workflow.py status                 # 查看处理状态
```

### 4.3 运行后得到什么

| 产物 | 位置 | 用途 |
|------|------|------|
| 结构化摘要（6 节） | `03_Summary/paper_*/summary.md` | 直接阅读 |
| 纯文本全文 | `03_Summary/raw_text/` | 关键词搜索 |
| 四维标签 | `05_Index/tags/paper_*/tags.yaml` | 过滤和分类 |
| 向量索引 | `04_VectorDB/lancedb/` | 语义搜索 |

---

## 5. 如何检索文献

### 5.1 Python SDK

```python
from agent_sdk import search, get_summary, get_evidence

# 混合搜索
r = search("Vip3Aa receptor resistance in lepidopteran pests",
           query_type="hybrid_search", top_k=10)
for p in r.papers:
    print(f"[{p.year}] {p.title}: Toxin={p.toxin}, Mechanism={p.mechanism}")

# 获取摘要
s = get_summary(r.papers[0].paper_id)

# 获取证据链
e = get_evidence(query="Cry1Ac resistance ABC transporter", top_k=10)
```

### 5.2 REST API

```bash
# 启动服务
python Scripts/run_api_server.py

# 搜索
curl -X POST http://localhost:8710/v1/scientra/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Cry toxin receptor","mode":"hybrid","top_k":5}'

# 带过滤条件
curl -X POST http://localhost:8710/v1/scientra/query \
  -H "Content-Type: application/json" \
  -d '{"query":"resistance","mode":"hybrid","top_k":10,"filters":{"toxin":"Cry1Ac","year_gte":2018}}'

# 端点一览
# GET  /health
# POST /v1/scientra/query
# GET  /v1/paper/{id}/summary
# GET  /v1/paper/{id}/metadata
# GET  /v1/paper/{id}/tags
# GET  /v1/stats
```

---

## 6. Agent SDK 使用指南

### 6.1 本地模式

```python
from agent_sdk import LiteratureAgentSDK
sdk = LiteratureAgentSDK(mode="local")
results = sdk.search("Vip3Aa receptor", query_type="hybrid_search", top_k=10)
```

### 6.2 API 模式（远程）

```python
sdk = LiteratureAgentSDK(mode="api", base_url="http://remote-server:8710")
```

### 6.3 为 Agent 添加 Tool Use 定义

```python
{
    "name": "search_literature",
    "description": "Search the literature knowledge base",
    "parameters": {
        "query": "Natural language query",
        "query_type": "hybrid_search | keyword_search | vector_search",
        "top_k": "1-100",
        "filters": {"toxin": "...", "species": "...", "year_gte": 2018}
    }
}
```

---

## 7. 配置说明

### 工作流配置 `Config/workflow_config.yaml`

```yaml
steps:
  parse:    { enabled: true }
  metadata: { enabled: true }
  tag:      { enabled: true }
  summary:  { mode: "agent", fallback_mode: "direct_api" }
  embedding:{ enabled: true }
```

### GROBID 配置 `Config/grobid.yaml`

```yaml
docker_image: "lfoppiano/grobid:0.8.1"
docker_container: "scientra_grobid"
host_port: 18070
grobid_max_workers: 1           # 并发数（1=最稳定）
grobid_request_interval_seconds: 2
timeout: { connect: 10, read: 120, total: 600 }
retry: { max_attempts: 4 }
```

### 添加自定义标签 `Config/tag_dictionary.yaml`

```yaml
TOXIN:
  MyNewToxin:
    synonyms: ["MTX", "MyTox"]
    weight: 1.0
    min_score: 1.0
```
修改后运行 `python Scripts/retag.py --all` 重标注。

---

## 8. 常见问题与故障排查

### Docker / GROBID

| 问题 | 解决 |
|------|------|
| `docker: command not found` | 安装 Docker Desktop: https://docs.docker.com/desktop/ |
| GROBID 返回 503 | 正常现象，等待 30-60 秒加载模型 |
| `port 18070 already in use` | 检查占用: `netstat -ano \| findstr 18070`，或修改 Config/grobid.yaml |
| Docker Desktop 启动后连不上 | 等几秒让 Docker 引擎启动，先跑 `docker ps` 验证 |

### 依赖安装

| 问题 | 解决 |
|------|------|
| `sentence-transformers` 安装失败 | `pip install torch --index-url https://download.pytorch.org/whl/cpu` 然后重试 |
| `ModuleNotFoundError` | `pip install -r requirements.txt`，然后 `python Scripts/setup_check.py` |

### 工作流运行

| 问题 | 解决 |
|------|------|
| 处理中断 | `python workflow.py --all --resume`（从最后成功步骤继续） |
| Summary 一直 blocked | 设置 `ANTHROPIC_API_KEY` 环境变量，或运行 `python summary_agent.py --all --prompt-only` |
| Embedding 很慢 | CPU 上 49 篇约 20-40 分钟，有 GPU 可装 CUDA 版 PyTorch 提速 |
| 搜索返回 0 结果 | 检查向量索引: `python Scripts/system_check.py --no-bge-load`，如显示 missing tables 需运行 embedding |
| `00_Inbox` vs `01_PDF` | Inbox 是待处理区（自动导入），01_PDF 是正式存储区 |

---

## 9. 进阶用法

```bash
# 一键启动所有服务
start_scientra.bat             # Windows 双击即可

# 批量处理限制
python workflow.py --all --limit 10

# 更换嵌入模型
# 编辑 Config/workflow_config.yaml 中的 embedding.model

# 自定义标签后重新标注
python Scripts/retag.py --all

# 重新生成摘要
python summary_agent.py --all --force

# 重建向量索引
python Scripts/build_embeddings.py --root . --real-run
```

---

## 附录：命令速查表

| 命令 | 用途 |
|------|------|
| `python Scripts/setup_check.py` | 首次环境检测 |
| `python Scripts/setup_grobid.py` | GROBID 一键安装 |
| `python workflow.py --all` | 运行完整流水线 |
| `python workflow.py --all --resume` | 从失败恢复 |
| `python workflow.py --all --dry-run` | 预览模式 |
| `python workflow.py --all --changed-only` | 仅新文件 |
| `python workflow.py status` | 查看状态 |
| `python Scripts/run_api_server.py` | 启动 API |
| `python Scripts/system_check.py` | 系统诊断 |
| `python Scripts/search_test.py` | 搜索测试 |
| `python Scripts/retag.py --all` | 重标注 |
| `python summary_agent.py --all` | 重生成摘要 |
| `start_scientra.bat` | Windows 一键启动 |
