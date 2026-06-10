# Changelog

All notable changes to Scientra Copilot will be documented in this file.

## [0.2.1] — 2026-06-10

### Fixed
- **Web 前端无法启动**：补齐 Next.js App Router 路由层（`web/app/`），包含 9 个页面路由（Research Map、Hotspots、Research Gaps、Topic Explorer、Knowledge Network、Library、Settings、Report）以及 `layout.tsx` 和 `globals.css`。此前仅有组件和数据层，缺少页面入口导致 `next dev` 无内容可渲染。
- **组件接口不匹配**：修复 `ResearchMapView` 未传入 `data` prop 导致 `Cannot read properties of undefined` 运行时错误；修复 `NetworkGraph`/`NetworkToolbar`/`NetworkNodeDetail` props 签名不匹配问题，补充 search、activeTypes、edgeDensity、labelMode 等必需参数。
- **Source Control 显示构建产物**：项目中无 `.gitignore`，导致 `web/node_modules/` 和 `web/.next/` 出现在 git status 中。
- **侧边栏品牌名称不一致**：左上角显示 "Research OS"，与软件名 "Scientra Copilot" 不符，已统一修正。

### Added
- **`.gitignore`**：忽略 `node_modules/`、`.next/`、`__pycache__/`、`.venv/`、`*.log` 等构建产物与环境文件。
- **`web/app/report/` 研究报告页**：综合研究智能报告，包含 Executive Summary、知识覆盖度、核心主题、研究热点、研究缺口、主要研究问题、关键文献等模块，支持打印和导出 TXT。

### Changed
- **侧边栏品牌文案**：`Research OS` → `Scientra Copilot`（含主标题和版本号）。

## [0.2.0] — 2026-06-10

### Changed
- **Renamed project** from "Literature_OS" to "Scientra Copilot"
- Python package namespace: `literature_os` → `scientra`
- URI scheme: `literature_os://` → `scientra://`
- API routes: `/v1/literature/` → `/v1/scientra/`
- Docker container: `literature_os_grobid` → `scientra_grobid`
- Logger namespace: `literature_os.*` → `scientra.*`
- SQLite database: `literature_os.db` → `scientra.db`

### Added
- MIT LICENSE
- .gitignore for Python project
- pyproject.toml with dependency specification
- requirements.txt
- CONTRIBUTING.md
- CODE_OF_CONDUCT.md
- GitHub issue templates
- Project slogan: "Your Literature, Structured"

## [0.1.0] — 2026-06-08

### Added
- Initial release as Literature_OS
- 8-step PDF processing pipeline (import → parse → metadata → tag → summary → embedding → lancedb → index)
- GROBID integration for PDF structure parsing
- Rule-based Tag Engine with ontology YAML configuration
- Dual-mode Summary Agent (LLM API + prompt-only fallback)
- BGE-M3 three-level embedding (metadata / summary / chunks)
- LanceDB vector store with hybrid search
- FastAPI query server with `/v1/query` endpoint
- Agent SDK with policy enforcement
- SHA256 incremental processing with workflow state-machine resume
- CLI via Typer
- Comprehensive docs (architecture, manual, API design, SDK design)
