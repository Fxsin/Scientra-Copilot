# Changelog

All notable changes to Scientra Copilot will be documented in this file.

## [0.2.1] — 2026-06-10

### Fixed
- **Web 前端无法启动**：补齐 Next.js App Router 路由层（`web/app/`），包含 9 个页面路由以及 `layout.tsx` 和 `globals.css`。
- **组件接口不匹配**：修复 `ResearchMapView` 未传入 `data` prop 导致 `Cannot read properties of undefined` 运行时错误；修复 `NetworkGraph`/`NetworkToolbar`/`NetworkNodeDetail` props 签名不匹配问题。
- **前端 API 端口错误**：`web/lib/api.ts` 默认端口 8765 → 8710，与 `run_api_server.py` 默认端口一致。此前首次用户启动后所有 API 请求静默失败。
- **环境变量名引用旧项目名**：`NEXT_PUBLIC_LITERATURE_API_URL` → `NEXT_PUBLIC_SCIENTRA_API_URL`；`LITERATURE_OS_API_KEY` → `SCIENTRA_API_KEY`。前端错误消息中 "Literature_OS" → "Scientra Copilot"。
- **`start_all.py` 启动 Web 前不安装 npm 依赖**：`node_modules/` 不存在时 `npm run dev` 直接崩溃。现已增加自动检测和 `npm install`。
- **`start_all.py` 误导日志**：`package.json` 存在时不再打印 "not yet implemented"。
- **文档缺失 `pip install -e .` 步骤**：`workflow.py` 需导入 `scientra` package，但安装指引中未提及此必需步骤。已在手册和系统要求文档中补全。
- **`system_check.py` 引用不存在的目录**：`sys.path` 中引用了已删除的 `06_API/` 和 `08_Agent_Interface/`。
- **文档 SDK 导入路径错误**：`from agent_sdk import ...` → `from scientra.sdk import ...`（`agent_sdk.py` 不存在，代码在 `scientra/sdk.py`）。
- **侧边栏品牌名称不一致**："Research OS" → "Scientra Copilot"。
- **文档硬编码开发者本地路径**：删除 `docs/System_Requirements.md` 中的 `G:\AI_agent\Scientra Copilot`。

### Added
- **`.gitignore`**：忽略 `node_modules/`、`.next/`、`__pycache__/`、`.venv/`、`*.log` 等构建产物与环境文件。
- **`web/app/report/` 研究报告页**：综合研究智能报告，支持打印和导出 TXT。

### Changed
- **侧边栏品牌文案**：`Research OS` → `Scientra Copilot`（含主标题和版本号）。
- **版本号同步**：`pyproject.toml`、`scientra/version.py` → 0.2.1。
- **`start_all.py` 启动流程**：增加 `npm install` 自动检测，首次用户无需手动安装前端依赖。

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
