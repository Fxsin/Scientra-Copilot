# Changelog

All notable changes to Scientra Copilot will be documented in this file.

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
