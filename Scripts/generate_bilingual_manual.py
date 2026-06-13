"""Generate bilingual user manual v2.0 — Markdown + DOCX.

Outputs:
  docs/manual/Scientra_Copilot_User_Manual_v2_bilingual.md
  docs/manual/Scientra_Copilot_User_Manual_v2_bilingual.docx

Does NOT overwrite existing v1.x manuals.
"""

import datetime, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

today = datetime.date.today().isoformat()
VERSION = "v2.0"
SOFTWARE_VERSION = "v1.5"


# ── Content structure ──

ENGLISH = [
    ("1. Introduction", [
        "Scientra Copilot is a local-first, evidence-oriented research discovery platform.",
        "It processes scientific papers (PDF), extracts structured evidence, builds semantic "
        "indexes, and provides an AI-powered chat interface that answers research questions "
        "grounded in your literature with traceable citations.",
        "",
        "Current version: " + SOFTWARE_VERSION + ". Status: active development.",
        "",
        "What it does:",
        "- Processes PDFs into structured knowledge assets",
        "- Links supplementary files (Excel, CSV, TSV) to their parent papers",
        "- Extracts gene/protein/compound entities from supplementary tables",
        "- Provides AI chat with evidence-grounded, cited answers",
        "- Enables cross-paper entity comparison",
        "",
        "What it does not claim:",
        "- It is not a cloud service — all data stays on your machine",
        "- It does not replace human scientific judgment",
        "- It does not automatically write papers or grant proposals",
        "- It does not perform statistical meta-analysis across papers",
    ]),
    ("2. Core Design Philosophy", [
        "Local-first scientific workspace: All data stored locally. No cloud dependency.",
        "Evidence-oriented knowledge extraction: From raw PDF to structured, searchable, "
        "AI-queryable knowledge chunks.",
        "Pipeline: Paper -> Asset -> Corpus -> Knowledge -> Index -> Agent",
        "Why supplementary data matters: The most valuable structured data (gene lists, "
        "expression tables, bioassay results) often lives in supplementary Excel/CSV files, "
        "not in the main PDF.",
        "folder_explicit binding: Supplementary files are linked by folder membership, "
        "not by filename guessing. This is more reliable than pattern-based matching.",
        "Traceability: Every asset, entity, and chunk carries provenance information "
        "(source file, import method, confidence, SHA256).",
    ]),
    ("3. System Architecture", [
        "Backend: Python 3.11+, FastAPI server on port 8710.",
        "Frontend: Next.js 14, React, Tailwind CSS, served on port 3000.",
        "Vector Index: LanceDB with BGE-M3 embeddings (1024-dim). "
        "3 tables: evidence_chunks, literature_vectors, pdf_asset_chunks.",
        "Primary LanceDB path: 06_Index/vector/lancedb/",
        "LLM: DeepSeek deepseek-chat or Anthropic Claude. "
        "API key stored in Config/llm_config.yaml (gitignored).",
        "PDF parsing: GROBID (Docker-based).",
        "Storage: Storage Layout v3 — 10-group directory structure.",
    ]),
    ("4. Storage Layout v3", [
        "00_Inbox/ — Import staging. article_bundles/, single_papers/, loose_supplementary/.",
        "01_Sources/ — Original files. papers/, supplementary/, datasets/.",
        "02_Parse/ — Parsed intermediates. text/, figures/, tables/, supplementary/.",
        "03_Assets/ — Structured assets. paper_assets/, figure_assets/, table_assets/, etc.",
        "04_Corpus/ — Long-term corpora. writing/, reasoning/, data/, review/.",
        "05_Knowledge/ — Knowledge graph and maps. graph/, maps/, memory/, reasoning_chains/.",
        "06_Index/ — Search indexes. vector/ (LanceDB), keyword/, entity/, citation/, paper/, asset/.",
        "07_Agents/ — Agent workspaces. chat/, writing_agent/, reviewer_agent/, evals/, etc.",
        "08_Projects/ — User project workspaces.",
        "09_Exports/ — Export outputs.",
        "10_System/ — System files. config/, logs/, cache/, migrations/, backups/, legacy_archive/.",
        "",
        "Do NOT manually modify files in 01_Sources, 03_Assets, 04_Corpus, or 06_Index "
        "unless you understand the manifest and SHA256 tracking system.",
    ]),
    ("5. Installation and Startup", [
        "Requirements: Python 3.11+, Node.js 18+, Docker (for GROBID).",
        "",
        "Quick start:",
        "  python Scripts/dev_restart.py",
        "",
        "Manual start:",
        "  python -m scientra.server          # API on port 8710",
        "  cd web && npm run dev              # Web on port 3000",
        "",
        "LLM setup:",
        "  python Scripts/setup_llm.py",
        "  Supports DeepSeek (deepseek-chat) and Anthropic (claude-sonnet-4-6).",
        "  API key stored in Config/llm_config.yaml (gitignored).",
    ]),
    ("6. Importing Papers", [
        "Recommended: Article Bundle Import.",
        "Place each paper in its own folder under 00_Inbox/article_bundles/new/:",
        "",
        "  Example_Paper/",
        "    main.pdf",
        "    Table_S1.xlsx",
        "    Source_Data.csv",
        "    Supplementary_Information.pdf",
        "",
        "Commands:",
        "  python Scripts/process_article_bundles.py --scan",
        "  python Scripts/process_article_bundles.py --process --archive-mode copy",
        "",
        "Main PDF detection rules:",
        "- Filename contains 'main', 'paper', 'article', 'manuscript' -> priority",
        "- Filename contains 'supplementary', 'supporting', 'appendix' -> demoted",
        "- Only one PDF -> auto-selected",
        "- Multiple PDFs, no keyword match -> largest file selected (with warning)",
        "- No PDF -> bundle failed",
        "",
        "Archive modes:",
        "- copy (default, safe): Copies files, preserves originals.",
        "- move: Moves files. Use ONLY when you are certain.",
        "- none: No archiving.",
        "- dry-run: Plan only, no file operations.",
    ]),
    ("7. Supplementary Files", [
        "Supported types: .xlsx, .xls, .csv, .tsv, .pdf, .docx, .zip",
        "",
        "Tabular files (.xlsx, .csv, .tsv): Can enter preview extraction and entity index.",
        "Supplementary PDFs: File-level link only. No OCR in current version.",
        "ZIP/DOCX: File-level link only.",
        "",
        "folder_explicit binding: Files in the same folder as the main PDF are "
        "automatically linked to that paper with high confidence.",
        "",
        "loose supplementary: Files without a parent article folder. "
        "They require manual confirmation and will NOT enter the entity index automatically.",
        "",
        "entity_index_status: pending -> indexed (only for high-confidence matched files).",
    ]),
    ("8. Web Interface Guide", [
        "/chat — AI literature chat. Supports 7 query types, 3 answer modes.",
        "/library — Paginated paper library with search and filter.",
        "/paper/{id} — Paper detail with metadata, summary, evidence, and 'Ask this paper'.",
        "/evidence — Evidence chunk search with type filter.",
        "/research-map — Facet-first hierarchical topic explorer.",
        "/hotspots — Trending topics, hot papers, emerging facets.",
        "/research-gaps — Auto-detected evidence gaps.",
        "/knowledge-network — Paper-facet-method-finding network visualization.",
        "/report — Auto-generated library intelligence report.",
        "/topic-explorer — Browse topics by research facet.",
        "/import — Planned: Import dashboard for article bundles and supplementary files.",
        "/assets — Planned: Assets viewer for browsing generated assets.",
    ]),
    ("9. Literature Chat", [
        "Query types: claim_query, research_gap_query, method_query, result_query, "
        "supplementary_entity_query, supplementary_entity_comparison_query, hybrid_search.",
        "",
        "Answer modes:",
        "- Auto: Uses LLM if API key configured, otherwise evidence-only fallback.",
        "- LLM synthesis: Forces LLM API call with cited answer.",
        "- Evidence-only: Deterministic, no API call. Shows retrieved evidence.",
        "",
        "How to ask good questions:",
        "- Be specific about what you want to find.",
        "- For entity queries, name the gene/protein clearly: 'Is MAP2K4 in supplementary tables?'",
        "- For comparison: 'Compare MAP2K4 across supplementary data.'",
        "- For methods: 'What bioassay methods are commonly used?'",
        "",
        "Limitations:",
        "- Answers are based only on your imported literature.",
        "- LLM may occasionally misinterpret context. Always verify citations.",
        "- Single-row data cannot prove causality. Interpretation includes caution notes.",
        "- source_link_count means the same data row is linked to multiple references "
        "— it is NOT independent evidence.",
    ]),
    ("10. Query APIs and SDK", [
        "POST /query/assets — Search asset chunks. Supports 11 chunk types.",
        "POST /query/evidence — Search evidence chunks.",
        "POST /query/supplementary-entities — Search indexed supplementary entities.",
        "POST /query/supplementary-entity-comparison — Cross-paper entity comparison.",
        "POST /v1/agent/ask — Literature Agent Q&A.",
        "",
        "SDK example:",
        "  from scientra.sdk import query_assets, query_supplementary_entities",
        "  r = query_assets('protein expression', top_k=10, chunk_types=['method'])",
        "  r = query_supplementary_entities('MAP2K4', entity_type='gene')",
    ]),
    ("11. Maintaining and Updating", [
        "Adding new papers: Place in 00_Inbox/article_bundles/new/ and run process_article_bundles.",
        "Rebuilding assets: python -m scientra.pdf_data_assets.build_assets --tables --all --force",
        "Rebuilding entity index: python -m scientra.pdf_data_assets.build_assets --supplementary-entities --all --force",
        "Rebuilding embeddings: python -m scientra.pdf_data_assets.asset_embedding --all --force",
        "",
        "When to use --force: When you have changed source data and need full regeneration.",
        "When NOT to rebuild: When only adding a few papers. Use incremental processing.",
        "",
        "Backup recommendations:",
        "- Back up 10_System/backups/ before major migrations.",
        "- Legacy archive at 10_System/legacy_archive/ is your safety net.",
        "- LanceDB at 06_Index/vector/lancedb/ should be backed up before rebuilds.",
    ]),
    ("12. Error Troubleshooting", [
        "Backend cannot start: Check port 8710 is free. Check Python dependencies.",
        "Frontend cannot start: Check port 3000 is free. Run 'npm install' in web/.",
        "GROBID not responding: Check Docker is running. GROBID runs on port 8070.",
        "API key missing: Run 'python Scripts/setup_llm.py' or set DEEPSEEK_API_KEY env var.",
        "LanceDB cannot open: Check 06_Index/vector/lancedb/ exists and has tables.",
        "Query returns no results: Check that data has been imported and embedded.",
        "Supplementary entity not found: Check that the file is high-confidence matched, "
        "not candidate_only or file_missing.",
        "Excel not parsed: Install openpyxl: 'pip install openpyxl'.",
        "Chat returns empty: Check API key and network. Try evidence-only mode.",
        "npm build error: Run 'npm install' then 'npm run build' in web/.",
    ]),
    ("13. Development and Upgrade Guide", [
        "Adding a new corpus: Create directory under 04_Corpus/. Build extraction logic.",
        "Adding a new asset type: Add schema, builder, chunk type, and embedder.",
        "Adding a new Agent: Create workspace under 07_Agents/. Add prompt and eval cases.",
        "Adding a new API endpoint: Add route to server.py. Add SDK function.",
        "Adding a new Web page: Create page.tsx under web/app/. Update sidebar navigation.",
        "Writing tests: Follow existing test patterns. Always test with real data.",
        "Safety rules: Never commit API keys, PDFs, LanceDB, or user data. "
        "Never use absolute paths in reports. Never delete user files.",
    ]),
    ("14. Data Safety and Git Rules", [
        "Never commit: PDFs, Excel/CSV/TSV files, LanceDB, API keys, raw text, generated data.",
        "Recommended .gitignore additions: 01_Sources/, 02_Parse/, 03_Assets/, 04_Corpus/, "
        "05_Knowledge/, 06_Index/, 07_Agents/, 08_Projects/, 09_Exports/, 10_System/, "
        "00_Inbox/, *.pdf, *.xlsx, *.csv, lancedb/.",
        "Config/llm_config.yaml is already gitignored. Verify before committing.",
    ]),
    ("15. FAQ", [
        "Q: Is cloud required? A: No. All data stays local.",
        "Q: Can I delete the legacy archive? A: Yes, after confirming all systems work.",
        "Q: What LLM providers are supported? A: DeepSeek and Anthropic Claude.",
        "Q: Does it work without LLM? A: Yes. Use evidence-only mode.",
        "Q: Can I add supplementary files later? A: Yes. Put them in the article bundle folder and re-process.",
        "Q: Why is my supplementary file marked candidate_only? A: It needs a paper_id in the filename or folder.",
        "Q: How to rename files for high confidence matching? A: Use {paper_id}__{label}.ext format.",
        "Q: Does it support Chinese papers? A: GROBID supports multiple languages. Chat works in Chinese.",
        "Q: Can I run it on a server? A: Yes, the API and web frontend can be deployed.",
        "Q: How large can the database grow? A: LanceDB scales to millions of vectors.",
    ]),
    ("16. Roadmap", [
        "Near-term (v1.6): Import Dashboard, Assets Viewer, Manual Binding UI.",
        "Mid-term (v1.7-1.8): Corpus builders, Dataset/Gene Evidence expansion, Cross-study comparison.",
        "Long-term (v2.0+): Knowledge Graph, Scientific Memory, Reasoning Engine, "
        "Experimental Design Agent, AI Reviewer Agent.",
    ]),
]

CHINESE = [
    ("1. 软件简介", [
        "Scientra Copilot 是一个本地优先、证据导向的科研文献发现平台。",
        "它能自动处理 PDF，提取结构化证据，构建语义索引，并提供基于文献的 AI 对话界面，所有回答都带可追溯引用。",
        "",
        "当前版本：" + SOFTWARE_VERSION + "。状态：活跃开发中。",
        "",
        "它能做什么：",
        "- 将 PDF 转化为结构化知识资产",
        "- 将补充文件（Excel、CSV、TSV）与其母论文关联",
        "- 从补充表格中提取基因/蛋白质/化合物实体",
        "- 提供基于文献的 AI 对话，回答带引用",
        "- 支持跨论文实体比较",
        "",
        "它不能做什么：",
        "- 它不是云服务——所有数据留在你的电脑上",
        "- 它不能替代人类的科学判断",
        "- 它不会自动写论文或基金申请书",
        "- 它不执行跨论文的统计荟萃分析",
    ]),
    ("2. 设计逻辑", [
        "本地优先科研工作区：所有数据本地存储，无需云端。",
        "证据导向知识提取：从原始 PDF 到结构化、可检索、可供 AI 查询的知识片段。",
        "流水线：论文 -> 资产 -> 语料 -> 知识 -> 索引 -> 智能体。",
        "为什么补充数据重要：最有价值的结构化数据（基因列表、表达表格、生测结果）"
        "往往在补充 Excel/CSV 文件中，不在正文 PDF 里。",
        "folder_explicit 绑定：补充文件通过文件夹归属性关联，不靠文件名猜测。"
        "比基于模式匹配更可靠。",
        "可追溯性：每个资产、实体、片段都携带溯源信息"
        "（来源文件、导入方式、置信度、SHA256）。",
    ]),
    ("3. 整体架构", [
        "后端：Python 3.11+，FastAPI 服务器，端口 8710。",
        "前端：Next.js 14，React，Tailwind CSS，端口 3000。",
        "向量索引：LanceDB + BGE-M3 嵌入（1024 维）。3 张表：evidence_chunks、literature_vectors、pdf_asset_chunks。",
        "LanceDB 主路径：06_Index/vector/lancedb/",
        "LLM：DeepSeek deepseek-chat 或 Anthropic Claude。API key 保存在 Config/llm_config.yaml（已 gitignore）。",
        "PDF 解析：GROBID（基于 Docker）。",
        "存储：Storage Layout v3——10 组目录结构。",
    ]),
    ("4. Storage Layout v3 文件夹系统详解", [
        "00_Inbox/ — 导入入口。article_bundles/（推荐）、single_papers/、loose_supplementary/。",
        "01_Sources/ — 原始文件。papers/、supplementary/、datasets/。",
        "02_Parse/ — 解析中间产物。text/、figures/、tables/、supplementary/。",
        "03_Assets/ — 结构化资产。paper_assets/、figure_assets/、table_assets/ 等。",
        "04_Corpus/ — 长期语料库。writing/、reasoning/、data/、review/。",
        "05_Knowledge/ — 知识图谱和地图。graph/、maps/、memory/、reasoning_chains/。",
        "06_Index/ — 检索索引。vector/（LanceDB）、keyword/、entity/、citation/、paper/、asset/。",
        "07_Agents/ — 智能体工作区。chat/、writing_agent/、reviewer_agent/、evals/ 等。",
        "08_Projects/ — 用户项目工作区。",
        "09_Exports/ — 导出输出。",
        "10_System/ — 系统文件。config/、logs/、cache/、migrations/、backups/、legacy_archive/。",
        "",
        "⚠️ 注意：不要手动修改 01_Sources、03_Assets、04_Corpus、06_Index 中的文件，"
        "除非你理解 manifest 和 SHA256 追踪系统。",
    ]),
    ("5. 安装与启动", [
        "环境要求：Python 3.11+、Node.js 18+、Docker（用于 GROBID）。",
        "",
        "快速启动：",
        "  python Scripts/dev_restart.py",
        "",
        "手动启动：",
        "  python -m scientra.server          # API 端口 8710",
        "  cd web && npm run dev              # Web 端口 3000",
        "",
        "LLM 配置：",
        "  python Scripts/setup_llm.py",
        "  支持 DeepSeek（deepseek-chat）和 Anthropic（claude-sonnet-4-6）。",
        "  API key 保存在 Config/llm_config.yaml（已 gitignore）。",
    ]),
    ("6. 如何导入文献", [
        "推荐方式：Article Bundle Import。",
        "将每篇论文放在独立文件夹中，放入 00_Inbox/article_bundles/new/：",
        "",
        "  示例论文/",
        "    main.pdf",
        "    Table_S1.xlsx",
        "    Source_Data.csv",
        "    Supplementary_Information.pdf",
        "",
        "命令：",
        "  python Scripts/process_article_bundles.py --scan      # 扫描",
        "  python Scripts/process_article_bundles.py --process --archive-mode copy  # 处理",
        "",
        "正文 PDF 识别规则：",
        "- 文件名含 main/paper/article/manuscript -> 优先",
        "- 文件名含 supplementary/supporting/appendix -> 降低优先级",
        "- 只有一个 PDF -> 自动选为正文",
        "- 多个 PDF 且无法判断 -> 选最大的（带警告）",
        "- 没有 PDF -> bundle 失败",
        "",
        "归档模式：",
        "- copy（默认，安全）：复制文件，保留原文件",
        "- move：移动文件，仅在确认无误后使用",
        "- none：不归档",
        "- dry-run：仅生成计划，不操作文件",
    ]),
    ("7. 补充文件管理", [
        "支持类型：.xlsx、.xls、.csv、.tsv、.pdf、.docx、.zip",
        "",
        "表格文件（.xlsx/.csv/.tsv）：可进入预览提取和实体索引。",
        "补充 PDF：仅文件级链接。当前版本不做 OCR。",
        "ZIP/DOCX：仅文件级链接。",
        "",
        "folder_explicit 绑定：与 main PDF 在同一文件夹的文件自动关联，置信度 high。",
        "",
        "loose supplementary（散装补充）：没有父文章文件夹的文件。"
        "需要人工确认，不会自动进入实体索引。",
        "",
        "entity_index_status：pending -> indexed（仅高置信匹配文件）。",
    ]),
    ("8. Web 页面逐项解读", [
        "/chat — AI 文献对话。支持 7 种查询类型，3 种回答模式。",
        "/library — 分页论文库，支持搜索和筛选。",
        "/paper/{id} — 论文详情页，含元数据、摘要、证据、本文提问。",
        "/evidence — 证据片段搜索，支持类型筛选。",
        "/research-map — 研究维度分层主题浏览。",
        "/hotspots — 热门话题、热点论文、新兴方向。",
        "/research-gaps — 自动检测的研究空白。",
        "/knowledge-network — 论文-维度-方法-发现关系网络。",
        "/report — 自动生成的文献库智能报告。",
        "/topic-explorer — 按研究维度浏览话题。",
        "/import — 规划中：导入仪表盘。",
        "/assets — 规划中：资产查看器。",
    ]),
    ("9. Chat 使用方法", [
        "查询类型：claim_query、research_gap_query、method_query、result_query、"
        "supplementary_entity_query、supplementary_entity_comparison_query、hybrid_search。",
        "",
        "回答模式：",
        "- Auto（推荐）：有 API key 时用 LLM，否则展示检索证据",
        "- LLM synthesis：强制 LLM，生成学术引用回答",
        "- Evidence-only：确定性回答，不调用 API",
        "",
        "如何提问：",
        "- 尽量具体：'Is MAP2K4 in supplementary tables?'",
        "- 实体比较：'Compare MAP2K4 across supplementary data.'",
        "- 方法查询：'What bioassay methods are commonly used?'",
        "",
        "注意事项：",
        "- 回答仅基于你已导入的文献",
        "- LLM 偶尔可能误读上下文，请核实引用",
        "- 单行数据不能证明因果关系，解释包含谨慎声明",
        "- source_link_count 表示同一数据行被多个标签引用——不是独立证据",
    ]),
    ("10. 检索 API 与 SDK", [
        "POST /query/assets — 搜索资产片段（11 种类型）",
        "POST /query/evidence — 搜索证据片段",
        "POST /query/supplementary-entities — 搜索补充实体",
        "POST /query/supplementary-entity-comparison — 跨论文实体比较",
        "POST /v1/agent/ask — AI 文献问答",
        "",
        "SDK 示例：",
        "  from scientra.sdk import query_assets, query_supplementary_entities",
        "  r = query_assets('protein expression', top_k=10, chunk_types=['method'])",
        "  r = query_supplementary_entities('MAP2K4', entity_type='gene')",
    ]),
    ("11. 数据库维护与升级", [
        "添加新论文：放入 00_Inbox/article_bundles/new/，运行 process_article_bundles。",
        "重建资产：python -m scientra.pdf_data_assets.build_assets --tables --all --force",
        "重建实体索引：python -m scientra.pdf_data_assets.build_assets --supplementary-entities --all --force",
        "重建嵌入：python -m scientra.pdf_data_assets.asset_embedding --all --force",
        "",
        "何时使用 --force：源数据有重大变更，需要全量重建时。",
        "何时不需要重建：仅添加少量论文时，使用增量处理。",
        "",
        "备份建议：",
        "- 重大迁移前备份 10_System/backups/",
        "- 10_System/legacy_archive/ 是你的安全网",
        "- 重建嵌入前备份 06_Index/vector/lancedb/",
    ]),
    ("12. 常见报错与维修", [
        "后端无法启动：检查端口 8710 是否被占用。检查 Python 依赖。",
        "前端无法启动：检查端口 3000。在 web/ 下运行 npm install。",
        "GROBID 无响应：检查 Docker 是否运行。GROBID 使用端口 8070。",
        "API key 缺失：运行 python Scripts/setup_llm.py 或设置 DEEPSEEK_API_KEY 环境变量。",
        "LanceDB 无法打开：检查 06_Index/vector/lancedb/ 是否存在且包含表。",
        "查询无结果：检查数据是否已导入并嵌入。",
        "补充实体找不到：检查文件是否为高置信匹配，而不是 candidate_only 或 file_missing。",
        "Excel 无法解析：安装 openpyxl：pip install openpyxl。",
        "Chat 回答为空：检查 API key 和网络。尝试 evidence-only 模式。",
        "npm build 报错：在 web/ 下运行 npm install 然后 npm run build。",
    ]),
    ("13. 开发扩展指南", [
        "添加新语料：在 04_Corpus/ 下创建目录。构建提取逻辑。",
        "添加新资产类型：添加 schema、builder、chunk type 和 embedder。",
        "添加新 Agent：在 07_Agents/ 下创建工作区。添加 prompt 和 eval 用例。",
        "添加新 API 端点：在 server.py 中添加路由。在 sdk.py 中添加函数。",
        "添加新 Web 页面：在 web/app/ 下创建 page.tsx。更新侧边栏导航。",
        "编写测试：遵循已有测试模式。始终使用真实数据测试。",
        "安全规则：绝不提交 API key、PDF、LanceDB、用户数据。"
        "报告中使用相对路径。绝不要删除用户文件。",
    ]),
    ("14. 数据安全与 Git 管理", [
        "绝不提交：PDF、Excel/CSV/TSV 文件、LanceDB、API key、原始文本、生成数据。",
        "推荐 .gitignore：01_Sources/、02_Parse/、03_Assets/、04_Corpus/、"
        "05_Knowledge/、06_Index/、07_Agents/、08_Projects/、09_Exports/、10_System/、"
        "00_Inbox/、*.pdf、*.xlsx、*.csv、lancedb/。",
        "Config/llm_config.yaml 已加入 .gitignore。提交前确认。",
    ]),
    ("15. 常见问题", [
        "问：需要云端吗？答：不需要。所有数据在本地。",
        "问：能删除 legacy archive 吗？答：确认系统正常后可手动删除。",
        "问：支持哪些 LLM？答：DeepSeek 和 Anthropic Claude。",
        "问：没有 LLM 能用吗？答：能。使用 evidence-only 模式。",
        "问：能后加补充文件吗？答：能。放入 article bundle 文件夹后重新处理。",
        "问：为什么补充文件是 candidate_only？答：文件名或文件夹需要包含 paper_id。",
        "问：怎么命名才能高置信匹配？答：使用 {paper_id}__{label}.ext 格式。",
        "问：支持中文论文吗？答：GROBID 支持多语言。Chat 支持中文提问。",
        "问：能部署到服务器吗？答：API 和 Web 前端都可以部署。",
        "问：数据库能多大？答：LanceDB 支持百万级向量。",
    ]),
    ("16. 未来路线图", [
        "近期（v1.6）：导入仪表盘、资产查看器、手动绑定界面。",
        "中期（v1.7-1.8）：语料构建器、数据集/基因证据扩展、跨研究比较。",
        "远期（v2.0+）：知识图谱、科学记忆、推理引擎、实验设计助手、AI 审稿助手。",
    ]),
]


def write_markdown():
    """Write bilingual markdown manual."""
    lines = [
        f"# Scientra Copilot — User Manual {VERSION}",
        "",
        f"Generated: {today} | Software: {SOFTWARE_VERSION} | Layout: Storage Layout v3",
        "",
        "---",
        "",
        "# Part I. English User Manual",
        "",
    ]
    for title, content in ENGLISH:
        lines.append(f"## {title}")
        lines.append("")
        for para in content:
            lines.append(para)
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("# Part II. 中文使用说明书")
    lines.append("")
    for title, content in CHINESE:
        lines.append(f"## {title}")
        lines.append("")
        for para in content:
            lines.append(para)
            lines.append("")

    path = root / "docs" / "manual" / "Scientra_Copilot_User_Manual_v2_bilingual.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown: {path.relative_to(root)} ({len(lines)} lines)")
    return path


def write_docx():
    """Write bilingual DOCX manual."""
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Title
    title = doc.add_heading("Scientra Copilot — User Manual v2.0", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Bilingual Edition | Software: {SOFTWARE_VERSION} | Layout: Storage Layout v3")
    doc.add_paragraph("")

    # Part I
    doc.add_heading("Part I. English User Manual", level=1)
    for title, content in ENGLISH:
        doc.add_heading(title, level=2)
        for para in content:
            if para.startswith("  "):
                p = doc.add_paragraph(para.strip())
                p.style = doc.styles["Normal"]
                for run in p.runs:
                    run.font.name = "Consolas"
                    run.font.size = Pt(9)
            elif para == "":
                doc.add_paragraph("")
            else:
                doc.add_paragraph(para)

    doc.add_page_break()
    doc.add_heading("Part II. 中文使用说明书", level=1)
    for title, content in CHINESE:
        doc.add_heading(title, level=2)
        for para in content:
            if para.startswith("  "):
                p = doc.add_paragraph(para.strip())
                for run in p.runs:
                    run.font.name = "Consolas"
                    run.font.size = Pt(9)
            elif para == "":
                doc.add_paragraph("")
            else:
                doc.add_paragraph(para)

    path = root / "docs" / "manual" / "Scientra_Copilot_User_Manual_v2_bilingual.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    print(f"DOCX: {path.relative_to(root)} ({path.stat().st_size} bytes)")
    return path


if __name__ == "__main__":
    print("=== Generating Bilingual Manual v2.0 ===\n")
    md = write_markdown()
    docx = write_docx()
    print(f"\nDone. Old manuals NOT overwritten.")
