# Contributing to Scientra Copilot

Thanks for your interest in contributing! Scientra Copilot is an open-source literature knowledge OS for researchers.

## Development Setup

```bash
# Clone & install
git clone https://github.com/your-org/scientra-copilot.git
cd scientra-copilot
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Architecture Principles

Before contributing, please understand these core principles:

1. **One-Way Gate**: Data flows PDF → Parse → Metadata → Tag → Summary → Embedding → LanceDB → API → Agent. No step can mutate upstream data.
2. **Single Entry Point**: All agents must call `literature_query()`. Direct access to PDFs, SQLite, or LanceDB is forbidden.
3. **Policy Enforcement**: The Agent SDK enforces access boundaries at runtime.
4. **Source Anchoring**: Every result must have a traceable citation back to its source.

## Code Style

- Python 3.11+ with type hints
- Follow PEP 8
- Use `ruff` for linting: `ruff check .`
- Run tests before submitting: `pytest Tests/ -v`

## Pull Request Process

1. Fork the repo and create a feature branch
2. Add tests for new functionality
3. Update docs if you change public APIs
4. Ensure `python Scripts/system_check.py` passes
5. Submit a PR with a clear description

## Project Structure

See [README.md](README.md#-project-structure) for the full directory layout.

## Questions?

Open a [GitHub Discussion](https://github.com/your-org/scientra-copilot/discussions) or check the [docs](docs/).
