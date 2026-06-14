# Scientra Copilot 文献导入后解析详细过程报告

> 生成日期：2026-06-14 | 版本：v1.5+hybrid-parser

---

## 目录

1. [整体架构概览](#1-整体架构概览)
2. [导入入口（三种路径）](#2-导入入口三种路径)
3. [步骤一：import_pdf — PDF 入站](#3-步骤一import_pdf--pdf-入站)
4. [步骤二：parse — GROBID 解析](#4-步骤二parse--grobid-解析)
5. [步骤三：metadata — 元数据提取与 DOI 补全](#5-步骤三metadata--元数据提取与-doi-补全)
6. [步骤四：tag — 标签引擎打标](#6-步骤四tag--标签引擎打标)
7. [步骤五：summary — AI 摘要生成](#7-步骤五summary--ai-摘要生成)
8. [步骤六：evidence — 证据提取](#8-步骤六evidence--证据提取)
9. [步骤七：embedding — BGE-M3 向量化](#9-步骤七embedding--bge-m3-向量化)
10. [步骤八：lancedb — 索引验证](#10-步骤八lancedb--索引验证)
11. [步骤九：index_update — 索引报告](#11-步骤九index_update--索引报告)
12. [Hybrid Parser 并行流程（NEW）](#12-hybrid-parser-并行流程new)
13. [Web Import Center 路径](#13-web-import-center-路径)
14. [数据流追踪：一个 PDF 的完整旅程](#14-数据流追踪一个-pdf-的完整旅程)
15. [各步骤输入输出对照表](#15-各步骤输入输出对照表)
16. [容错与降级策略](#16-容错与降级策略)

---

## 1. 整体架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    导入入口（三种路径）                    │
│  ① CLI: workflow.py run                 ② Web 上传       │
│  ③ 手动放入 00_Inbox/                                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  WorkflowRunner (scientra/workflow.py)                  │
│  按顺序执行 9 个步骤，每个步骤可独立启用/禁用              │
│  核心调度器：STEP_ORDER = [import_pdf, parse, metadata,  │
│    tag, summary, evidence, embedding, lancedb,          │
│    index_update]                                        │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┬──────────────┬──────────────┐
     ▼               ▼               ▼              ▼              ▼
  import_pdf      parse          metadata         tag          summary
  (PDF入站)    (GROBID解析)   (元数据提取)    (标签引擎)    (AI摘要)
     │               │               │              │              │
     ▼               ▼               ▼              ▼              ▼
  evidence      embedding       lancedb      index_update
  (证据提取)   (向量嵌入)     (索引验证)    (索引报告)
```

**关键设计原则：**
- 每一步都是独立的 Python 脚本/模块，通过 subprocess 调用
- `optional: true` 的步骤失败不阻塞后续步骤
- `changed_only` 模式：只有 PDF 变化时才重新处理
- `resume` 模式：从上次失败的步骤继续
- 所有步骤共享同一个 `workflow_state.json` 状态文件

---

## 2. 导入入口（三种路径）

### 路径 A：Article Bundle Import（推荐）

**入口：** `00_Inbox/article_bundles/new/` 下每个文件夹 = 一篇论文

```
00_Inbox/article_bundles/new/
└── Example_Paper/
    ├── main.pdf           ← 主论文（自动检测）
    ├── Table_S1.xlsx      ← 补充表格
    └── Supplementary.pdf  ← 补充材料
```

**执行流程：**
```bash
# 1. 扫描
python Scripts/process_article_bundles.py --scan
  → 遍历 00_Inbox/article_bundles/new/
  → 每个文件夹: 检测主 PDF (关键词 "main"/"paper"/"article" 优先)
  → 分类补充文件: .xlsx/.csv/.tsv → tabular, .pdf → supplementary
  → 生成 ArticleBundleRecord (bundle_id, paper_id, SHA256)

# 2. 处理
python Scripts/process_article_bundles.py --process --archive-mode copy
  → 主 PDF → 01_Sources/papers/{paper_id}/
  → 补充文件 → 01_Sources/supplementary/{paper_id}/
  → 源文件夹 → 00_Inbox/article_bundles/processed/
  → 生成 import_manifest.json (含 SHA256, 时间戳, 来源路径)
```

**主 PDF 检测规则（优先级从高到低）：**
1. 文件名含 `main`/`paper`/`article`/`manuscript` → +2 分
2. 文件名含 `supplementary`/`supporting`/`appendix` → -5 分
3. 仅一个 PDF → 自动选中
4. 多 PDF 无关键词 → 选最大文件（附警告）
5. 无 PDF → `failed_no_main_pdf`

### 路径 B：Web Import Center（拖拽上传）

**入口：** Web 界面 `http://localhost:3000/import`

```
POST /import/upload-session          → 创建上传会话
POST /{session_id}/files             → 多文件上传 (multipart)
POST /{session_id}/plan              → 生成导入计划
PATCH /{session_id}/plan             → 用户手动调整
POST /{session_id}/confirm           → 确认执行
```

**执行流程：**
1. 文件上传到 `00_Inbox/web_uploads/staging/{session_id}/`
2. 系统自动检测主 PDF + 补充文件，生成计划
3. 用户确认/调整后，文件复制到 `00_Inbox/single_papers/new/` 或 `00_Inbox/article_bundles/new/`
4. 后续跟路径 A 的流程一致

### 路径 C：手动放入 00_Inbox/

```bash
# 单论文本
cp paper.pdf 00_Inbox/

# 然后运行 workflow
python workflow.py run
```

---

## 3. 步骤一：import_pdf — PDF 入站

**执行模块：** `WorkflowRunner.import_inputs()` (内置于 workflow runner)

**输入：**
- `00_Inbox/*.pdf`（直接放入的 PDF）
- `--file` 或 `--input-dir` 参数指定的 PDF
- `01_PDF/*.pdf`（已存在的 PDF，自动注册）

**输出：**
- `01_PDF/{filename}.pdf`（SHA256 去重后的目标路径）
- `07_Workflows/workflow_state.json` 更新 pdfs 注册表

**详细流程：**

```
1. collect_input_pdfs()
   ├── --file 指定的单个 PDF
   ├── --input-dir 指定的目录下所有 *.pdf
   └── 00_Inbox/*.pdf (默认)
        │
2. import_inputs() 对每个 PDF:
   ├── 计算 SHA256
   ├── 与上次状态对比 (changed 判断)
   ├── 若 changed or --force:
   │   └── shutil.copy2 → 01_PDF/
   └── 更新 workflow_state.json["pdfs"][target_path]
        │
3. 返回 List[ImportedPdf] → 供后续步骤使用
```

**changed 判断逻辑：**
```python
changed = (
    previous is None               # 新 PDF
    or previous["sha256"] != hash  # 内容变化
    or not target.exists()         # 目标缺失
)
```

**关键文件位置：**
- 状态文件：`07_Workflows/workflow_state.json`
- 目标目录：`01_PDF/`（legacy 路径，与 workflow_config.yaml 中 `paths.pdf_dir` 对应）

---

## 4. 步骤二：parse — GROBID 解析

**执行脚本：** `Scripts/pdf_parser.py`（调用 `grobid_client.py`）

**输入：**
- `01_PDF/*.pdf` — 待解析的 PDF 文件
- Docker GROBID 容器 → `http://localhost:18070`

**输出：**
- `02_Metadata/papers/{paper_id}.tei.xml` — GROBID TEI XML 完整输出
- `03_Summary/raw_text/{paper_id}.txt` — 提取的纯文本正文
- `02_Metadata/papers/{paper_id}.parse_report.json` — 解析报告
- `02_Parse/text/{paper_id}.txt` — v3 存储布局中的纯文本副本

**详细流程：**

```
1. 遍历 01_PDF/*.pdf
        │
2. 对每个 PDF:
   ├── 发送到 GROBID Docker API:
   │   POST http://localhost:18070/api/processFulltextDocument
   │   Headers: multipart/form-data (PDF binary)
   │   Params: consolidateHeader=0, consolidateCitations=0
   │   Timeout: 120s, Retry: 4次 (间隔 10/30/60s)
   │
   ├── 接收 TEI XML 响应:
   │   <?xml version="1.0" encoding="UTF-8"?>
   │   <TEI xmlns="http://www.tei-c.org/ns/1.0">
   │     <teiHeader>...</teiHeader>    ← 元数据
   │     <text>                          ← 正文
   │       <body>...</body>
   │       <back>                        ← 参考文献
   │         <div type="references">...</div>
   │       </back>
   │     </text>
   │   </TEI>
   │
   └── 提取纯文本:
       └── XML → 移除 namespace → 提取 <body> 文本
           → 保存为 {paper_id}.txt
```

**并发控制：**
- `grobid_max_workers: 1`（GROBID 默认单线程，避免 OOM）
- `grobid_request_interval_seconds: 2`（请求间隔，避免过载）

**容错：**
- GROBID 不可达 → 跳过，后续步骤可通过 DOI 补全元数据
- 单个 PDF 解析失败 → 记录到 parse_report，继续下一个
- TEI XML 解析异常 → 保存原始 XML，标记 `parse_status: partial`

---

## 5. 步骤三：metadata — 元数据提取与 DOI 补全

**执行脚本：** `Scripts/metadata_extractor.py`

**输入：**
- `02_Metadata/papers/{paper_id}.tei.xml` — GROBID 解析结果
- `03_Summary/raw_text/{paper_id}.txt` — 纯文本正文
- 在线 API（DOI 补全时）

**输出：**
- `02_Metadata/papers/{paper_id}.metadata.json` — 结构化元数据 JSON
- `02_Metadata/yaml/{paper_id}.metadata.yaml` — 元数据 YAML
- `02_Metadata/metadata.yaml` — 聚合元数据文件（供 API 查询）

**提取字段：**

| 字段 | 来源 | 提取方式 |
|------|------|---------|
| `paper_id` | 文件名 | SHA256 截取 12 位 |
| `title` | TEI XML `<title>` | XPath 提取 |
| `authors` | TEI XML `<author>` | forename + surname |
| `abstract` | TEI XML `<abstract>` | 段落拼接 |
| `doi` | TEI XML `<idno type="DOI">` | 直接提取 |
| `journal` | TEI XML `<monogr><title>` | 提取 |
| `year` | TEI XML `<date when="...">` | 提取 |
| `references` | TEI XML `<back><div type="references">` | 逐条解析 |
| `keywords` | 标题+摘要 | TF-IDF 关键词提取 |

**DOI 补全流程：**
```
若 GROBID 未提取到 DOI:
  ├── 1. 从 PDF 文件名搜索 DOI 模式: 10.XXXX/...
  ├── 2. 从 raw_text 前 2000 字符搜索 DOI
  ├── 3. 用标题查询 Crossref API:
  │     GET https://api.crossref.org/works?query.title={title}&rows=1
  └── 4. 用标题+作者查询 PubMed:
        GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
```

**输出示例 (`{paper_id}.metadata.yaml`)：**
```yaml
paper_id: paper_a1b2c3d4e5f6
title: "A Comprehensive Study of Bt Toxins"
authors: ["Smith, John", "Doe, Jane"]
year: 2024
journal: "Journal of Insect Science"
doi: "10.1234/example.2024"
abstract: "This paper explores..."
tags: ["Bt", "Vip3Aa", "insecticidal"]
species: ["Spodoptera frugiperda"]
toxin: ["Vip3Aa"]
method: ["RNA-seq", "bioassay"]
mechanism: ["apoptosis", "receptor binding"]
```

---

## 6. 步骤四：tag — 标签引擎打标

**执行脚本：** `Scripts/retag.py --all`

**输入：**
- `02_Metadata/yaml/{paper_id}.metadata.yaml` — 元数据
- `03_Summary/{paper_id}/summary.md` — AI 摘要（如果已存在）
- `Config/tag_dictionary.yaml` — 标签词典
- `Config/tag_ontology.yaml` — 标签层级关系

**输出：**
- `02_Metadata/yaml/{paper_id}.metadata.yaml` — 更新 tags/species/toxin/method/mechanism 字段
- `05_Index/tags/` — 标签索引

**打标策略：**

```
1. 加载标签词典 (tag_dictionary.yaml):
   toxin:
     - Vip3Aa, Vip3Af, Cry1Ab, Cry1Ac...
   species:
     - Spodoptera frugiperda, Helicoverpa armigera...
   method:
     - RNA-seq, bioassay, qPCR, western blot...
   mechanism:
     - apoptosis, receptor binding, pore formation...

2. 对每篇论文:
   ├── 标题 + 摘要 中匹配标签词典
   ├── 全文 raw_text 中进一步匹配
   ├── AI 摘要中提取的方法/物种/毒素
   └── 写入 metadata.yaml 的 tags/species/toxin/method/mechanism

3. 构建标签索引:
   └── 05_Index/tags/{tag_name}.json → 包含该标签的论文列表
```

---

## 7. 步骤五：summary — AI 摘要生成

**执行模块：** `scientra.summary`（agent 模式）或 `scientra.summary_engine`（direct_api 模式）

**输入：**
- `02_Metadata/yaml/{paper_id}.metadata.yaml` — 元数据
- `03_Summary/raw_text/{paper_id}.txt` — 纯文本正文

**输出：**
- `03_Summary/{paper_id}/summary.md` — AI 结构化摘要（Markdown/JSON）

**两种模式：**

### Agent 模式（默认）
```
1. 从 raw_text 中提取核心段落（摘要 + 引言 + 结果 + 讨论）
2. 构建 prompt → 发送到 LLM (Claude/DeepSeek)
3. 若无 API key → 写入 prompt 文件到 03_Summary/agent_prompts/
   供 Claude Code Agent 手动解析
4. 返回 JSON:
   {
     "Core Finding": [{text, quote, confidence}],
     "Evidence": [...],
     "Methods": [...],
     "Key Results": [...],
     "Limitations": [...],
     "Relevance to My Research": [...]
   }
```

### Direct API 模式
```
1. 直接调用 DeepSeek API
2. 发送完整的 raw_text + 结构化 prompt
3. 解析 JSON 响应 → summary.md
```

---

## 8. 步骤六：evidence — 证据提取

**执行模块：** `scientra.evidence_extraction`

**输入：**
- `03_Summary/{paper_id}/summary.md` — AI 摘要
- `02_Parse/text/{paper_id}.txt` — 全文

**输出：**
- `03_Evidence/{paper_id}/evidence.json` — 结构化证据

**证据类型（11 种 chunk 类型）：**

| Chunk 类型 | 说明 | 示例 |
|-----------|------|------|
| `core_finding` | 核心发现 | "Vip3Aa induces apoptosis in Sf9 cells" |
| `key_result` | 关键结果 | "LC50 = 2.3 ug/ml at 48h" |
| `method` | 实验方法 | "RNA-seq analysis of midgut tissue" |
| `claim` | 学术论断 | "Vip3Aa resistance is polygenic" |
| `discussion_point` | 讨论观点 | 对结果的解释和分析 |
| `limitation` | 局限性 | "Sample size limited to 3 replicates" |
| `open_question` | 开放问题 | "Receptor identity remains unknown" |
| `figure` | 图表引用 | 正文中对图表的描述 |
| `table` | 表格引用 | 正文中对表格的描述 |
| `section` | 章节段落 | Introduction/Methods/Results 等 |
| `entity` | 实体 | 基因名、蛋白质名、化合物名 |

**提取流程：**
```
1. LLM 提取 (evidence_llm_extractor.py):
   ├── 将 summary.md 转化为结构化 evidence chunks
   ├── 每个 chunk 带有: text, quote, confidence, source_section
   └── 质量过滤: confidence < 阈值 → 丢弃

2. 证据链接 (evidence_chunks.py):
   ├── result → discussion 关联
   ├── claim → evidence 关联
   └── entity → paper 关联
```

---

## 9. 步骤七：embedding — BGE-M3 向量化

**执行模块：** `scientra.embedding index`

**输入：**
- `02_Metadata/yaml/{paper_id}.metadata.yaml` — 元数据
- `03_Summary/{paper_id}/summary.md` — 摘要
- `03_Evidence/{paper_id}/evidence.json` — 证据 chunks

**输出：**
- `04_VectorDB/lancedb/` — LanceDB 向量数据库（3 张表）
- `04_VectorDB/embedding_report.json` — 嵌入报告

**三张向量表：**

| 表名 | 嵌入内容 | 向量维度 | 用途 |
|------|---------|---------|------|
| `literature_vectors` | 元数据 (title+abstract+tags) | 1024 | 论文级别语义搜索 |
| `evidence_chunks` | 证据 chunks (text) | 1024 | 证据级别精确检索 |
| `pdf_asset_chunks` | PDF 资产 chunks | 1024 | 细粒度资产检索 |

**嵌入流程：**
```
1. 加载 BAAI/bge-m3 模型 (SentenceTransformer)
2. 对每个文本块:
   ├── tokenize → 生成 embedding vector
   └── 写入 LanceDB 表
3. 生成 embedding_report.json:
   {
     embedding_model: "BAAI/bge-m3",
     total_chunks: 4234,
     tables: ["literature_vectors", "evidence_chunks", "pdf_asset_chunks"],
     generated_at: "2026-06-14T..."
   }
```

---

## 10. 步骤八：lancedb — 索引验证

**执行模块：** 内置步骤 (`builtin: "verify_lancedb"`)

**输入：**
- `04_VectorDB/embedding_report.json`

**输出：**
- 步骤状态 (PASS/FAIL)

**验证逻辑：**
```python
def run_builtin_step(step, builtin="verify_lancedb"):
    report_path = vector_db_dir.parent / "embedding_report.json"
    if report_path.exists():
        return StepResult(status="succeeded")
    else:
        return StepResult(status="failed", error="embedding report not found")
```

---

## 11. 步骤九：index_update — 索引报告

**执行模块：** 内置步骤 (`builtin: "index_update"`)

**输入：**
- 所有前序步骤的产物

**输出：**
- `05_Index/workflow_index_update.json` — 最终索引报告

```json
{
  "workflow_runner_version": "0.1.0",
  "metadata_yaml": "02_Metadata/metadata.yaml",
  "tag_dir": "05_Index/tags",
  "summary_dir": "03_Summary",
  "vector_db_dir": "04_VectorDB/lancedb",
  "agent_entrypoint": "literature_query"
}
```

---

## 12. Hybrid Parser 并行流程（NEW）

**⚠️ 当前默认 `enabled: false`**，开启后与 GROBID 传统流程并行运行。

**执行模块：** `scientra.parsers.parser_router.run_hybrid_parse()`

**触发时机：** 在步骤二 (parse) 中 GROBID 解析完成后

**独立流程（不影响 legacy 管道）：**

```
PDF 文件
  │
  ├──► PyMuPDF scan (pymupdf_adapter.py)
  │      ├── 检测: page_count, has_text_layer, image_count
  │      ├── 分类: normal / supplementary / scanned / table_heavy / image_heavy
  │      ├── 输出: 02_Parse/reports/pymupdf/{paper_id}.json
  │      └── 输出: 02_Parse/text/pymupdf/{paper_id}.txt
  │
  ├──► OpenDataLoader PDF (opendataloader_adapter.py)
  │      ├── markdown: 02_Parse/markdown/opendataloader/{paper_id}.md
  │      ├── layout:  02_Parse/layout/opendataloader/{paper_id}.json
  │      └── tables:  02_Parse/tables/opendataloader/{paper_id}.json
  │      (requires Java 11+, auto-detected)
  │
  ├──► Marker (marker_adapter.py) — 可选，默认不启用
  │      └── markdown: 02_Parse/markdown/marker/{paper_id}.md
  │
  └──► Hybrid Merge (hybrid_merge.py)
         ├── metadata 优先: GROBID
         ├── markdown 优先: OpenDataLoader
         ├── layout 优先: OpenDataLoader
         ├── figures 优先: OpenDataLoader → PyMuPDF fallback
         ├── 输出: 02_Parse/markdown/final/{paper_id}.md
         └── 输出: 02_Parse/reports/hybrid/{paper_id}_parse_manifest.json
```

**质量评分 (quality.py)：**
```
score_parse_result()
  ├── metadata_score:  title + DOI + abstract + authors + year
  ├── markdown_score:  文本长度 + section headings + 乱码检测
  ├── layout_score:    bbox 存在 + reading order + page 信息
  ├── reference_score: 参考文献数量 + 完整性
  ├── figure_score:    图片数量 + markdown 中引用
  ├── table_score:     表格数据 + markdown 中引用
  └── overall_score:   (加权平均)
```

---

## 13. Web Import Center 路径

**Web 上传的完整流程：**

```
[浏览器]                          [API Server]                    [文件系统]
   │                                  │                               │
   │ POST /import/upload-session      │                               │
   ├─────────────────────────────────►│                               │
   │                                  ├── 创建 session_id (UUID)      │
   │                                  ├── mkdir staging/{session_id}  │
   │  ← {session_id, expires_at}     │                               │
   │                                  │                               │
   │ POST /{session_id}/files         │                               │
   ├─────────────────────────────────►│                               │
   │  (multipart files)               ├── 逐个接收文件                  │
   │                                  ├── SHA256 去重                  │
   │                                  ├── 复制到 staging/{session_id}/  │
   │  ← {files: [...], total}        │                               │
   │                                  │                               │
   │ POST /{session_id}/plan          │                               │
   ├─────────────────────────────────►│                               │
   │                                  ├── 扫描 staging 目录             │
   │                                  ├── 检测主 PDF                    │
   │                                  ├── 分类补充文件                  │
   │                                  ├── 生成导入计划                  │
   │  ← {plan: {...}, detected:...}  │                               │
   │                                  │                               │
   │ PATCH /{session_id}/plan         │  (用户可选: 手动调整分类)        │
   ├─────────────────────────────────►│                               │
   │                                  │                               │
   │ POST /{session_id}/confirm       │                               │
   ├─────────────────────────────────►│                               │
   │                                  ├── 按计划复制文件:               │
   │                                  │   main PDF → 00_Inbox/single_ │
   │                                  │     papers/new/              │
   │                                  │   supplementary → 00_Inbox/   │
   │                                  │     loose_supplementary/new/  │
   │                                  ├── 生成 import_manifest.json   │
   │                                  ├── staging → imported/         │
   │  ← {status: "completed",        │                               │
   │     paper_id, files_copied}      │                               │
```

---

## 14. 数据流追踪：一个 PDF 的完整旅程

以一篇题为 *"Bacillus thuringiensis Vip3Aa toxin resistance in Heliothis virescens"* 的 PDF 为例：

```
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 0: 入站                                                     │
│                                                                  │
│ 00_Inbox/article_bundles/new/Vip3Aa_Resistance/                  │
│   ├── main.pdf (2.3 MB, SHA256: a1b2...)                        │
│   └── Table_S1.xlsx                                              │
│                                                                  │
│ → process_article_bundles.py --process                            │
│                                                                  │
│ 01_Sources/papers/bundle_Vip3Aa_Resistance_a1b2/                 │
│   ├── main.pdf                                                   │
│   └── import_manifest.json                                       │
│ 01_Sources/supplementary/bundle_Vip3Aa_Resistance_a1b2/           │
│   └── Table_S1.xlsx                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 1: GROBID 解析                                              │
│                                                                  │
│ POST PDF → GROBID Docker :18070/api/processFulltextDocument      │
│                                                                  │
│ → 02_Metadata/papers/paper_f405c3eb414a.tei.xml (156 KB)        │
│ → 03_Summary/raw_text/paper_f405c3eb414a.txt (48 KB)            │
│ → 02_Parse/text/paper_f405c3eb414a.txt (48 KB)                  │
│   提取 9,234 words 正文                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 2: 元数据提取                                                │
│                                                                  │
│ → 02_Metadata/papers/paper_f405c3eb414a.metadata.json            │
│ → 02_Metadata/yaml/paper_f405c3eb414a.metadata.yaml              │
│   title: "Bacillus thuringiensis Vip3Aa toxin resistance..."     │
│   authors: ["Gahan LJ", "Pauchet Y", "Vogel H", "Heckel DG"]    │
│   year: 2010                                                     │
│   journal: "Proceedings of the National Academy of Sciences"     │
│   doi: "10.1073/pnas.0909889107"                                 │
│   references: 42 条                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 3: 标签引擎                                                  │
│                                                                  │
│ 标题+摘要匹配 tag_dictionary.yaml:                                │
│   tags: ["Vip3Aa", "Bt toxin", "resistance", "Heliothis"]        │
│   species: ["Heliothis virescens"]                               │
│   toxin: ["Vip3Aa"]                                              │
│   mechanism: ["resistance mechanism", "midgut receptor"]          │
│   method: ["bioassay", "genetic crossing"]                       │
│                                                                  │
│ → 更新 metadata.yaml                                             │
│ → 05_Index/tags/Vip3Aa.json ← 添加 paper_f405c3eb414a            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 4: AI 摘要                                                   │
│                                                                  │
│ → 03_Summary/paper_f405c3eb414a/summary.md                       │
│                                                                  │
│ Core Finding:                                                    │
│   "Vip3Aa resistance in H. virescens is conferred by a           │
│    single major gene on linkage group 10"                        │
│                                                                  │
│ Evidence:                                                        │
│   - Genetic crosses show recessive inheritance pattern           │
│   - No cross-resistance to Cry proteins                          │
│                                                                  │
│ Methods:                                                         │
│   - Bioassay: diet overlay with Vip3Aa toxin                     │
│   - Genetic mapping: backcross + F2 analysis                     │
│                                                                  │
│ Relevance:                                                       │
│   "First documentation of Vip3Aa resistance allele — critical    │
│    for Bt crop resistance management strategies"                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 5: 证据提取                                                  │
│                                                                  │
│ → 03_Evidence/paper_f405c3eb414a/evidence.json                   │
│                                                                  │
│ Chunks extracted: 23                                             │
│   core_finding: 3   key_result: 5   method: 4                   │
│   discussion_point: 4  limitation: 2  claim: 4                  │
│   figure: 1 (genetic map of LG10)                                │
│                                                                  │
│ Result-Discussion Links: 5                                       │
│   "LC50 = 2.3 ug/ml" ↔ "This represents a moderate resistance..." │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 6: 向量嵌入 (BGE-M3)                                         │
│                                                                  │
│ → 04_VectorDB/lancedb/                                           │
│   literature_vectors: +1 row (metadata embedding, 1024-dim)      │
│   evidence_chunks: +23 rows (chunk embeddings, 1024-dim)         │
│   pdf_asset_chunks: +8 rows (sections, figures, tables)          │
│                                                                  │
│ → 04_VectorDB/embedding_report.json                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 阶段 7: API 可查询                                                │
│                                                                  │
│ GET /papers?q=Vip3Aa+resistance → 返回此论文                     │
│ GET /paper/paper_f405c3eb414a/metadata → 完整元数据               │
│ GET /paper/paper_f405c3eb414a/summary → AI 摘要                  │
│ GET /paper/paper_f405c3eb414a/evidence → 证据 chunks             │
│ POST /v1/agent/ask → "What is the inheritance pattern..."        │
│   → 返回答案 + [Ref:1][Ref:3] 引用                               │
│                                                                  │
│ 如启用 Hybrid Parser:                                             │
│ GET /paper/paper_f405c3eb414a/parse-report → 解析质量报告         │
│   02_Parse/markdown/final/paper_f405c3eb414a.md → 最终 Markdown  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 15. 各步骤输入输出对照表

| 步骤 | 执行单元 | 输入 | 输出 | 耗时 (典型) |
|------|---------|------|------|------------|
| **import_pdf** | workflow runner 内置 | 00_Inbox/*.pdf | 01_PDF/*.pdf | <1s |
| **parse** | `Scripts/pdf_parser.py` | 01_PDF/*.pdf | 02_Metadata/papers/*.tei.xml, 02_Parse/text/*.txt | 30-120s/PDF |
| **metadata** | `Scripts/metadata_extractor.py` | TEI XML + raw_text | 02_Metadata/yaml/*.metadata.yaml | 2-10s/PDF |
| **tag** | `Scripts/retag.py` | metadata YAML + 词典 | 标签更新 + 05_Index/tags/ | 1-3s/PDF |
| **summary** | `scientra.summary` | raw_text | 03_Summary/*/summary.md | 30-60s/PDF (LLM) |
| **evidence** | `scientra.evidence_extraction` | summary.md + 全文 | 03_Evidence/*/evidence.json | 10-30s/PDF |
| **embedding** | `scientra.embedding index` | metadata + summary + evidence | 04_VectorDB/lancedb/ (3 tables) | 5-20s/PDF |
| **lancedb** | 内置 | embedding_report.json | 状态验证 | <1s |
| **index_update** | 内置 | 所有产物 | 05_Index/workflow_index_update.json | <1s |
| **hybrid_parse** *(NEW)* | `scientra.parsers` | 01_Sources/*.pdf | 02_Parse/markdown/final/, 02_Parse/reports/hybrid/ | 10-60s/PDF |
| **article_bundle** | `process_article_bundles.py` | 00_Inbox/article_bundles/new/ | 01_Sources/{paper_id}/ | 1-5s/bundle |

---

## 16. 容错与降级策略

| 场景 | 处理方式 |
|------|---------|
| GROBID Docker 未启动 | parse 步骤失败 → DOI 补全仍可提取部分元数据 |
| 某个 PDF 解析失败 | 跳过该 PDF，继续处理其他 PDF |
| 无 LLM API key | summary 写入 prompt 文件，供手动处理 |
| evidence 提取失败 | `optional: true` → 不阻塞后续 embedding |
| LanceDB 写入失败 | embedding_report 标记 missing → lancedb 步骤 FAIL |
| OpenDataLoader 未安装 | skipped → 不中断，不报错 |
| OpenDataLoader Java 版本不兼容 | `_find_java11_home()` 自动检测 → 设置 JAVA_HOME → 重试 |
| Marker 未安装 | 默认不启用 → 不影响流程 |
| PyMuPDF 未安装 | scan 失败 → pdf_type=unknown → 走通用处理 |
| 扫描版 PDF (无文字层) | PyMuPDF 检测 → `suspected_scanned_pdf=True` → 低质量标记 |
| SHA256 去重匹配 | 内容相同的 PDF 跳过重复处理 |
| workflow 中断 | `--resume` 从上次失败的步骤继续 |
```

---

*报告基于 Scientra Copilot v1.5+ 代码实际追踪生成。*
