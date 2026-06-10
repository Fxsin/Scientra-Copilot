# Scripts

## Purpose

Executable pipeline scripts for each workflow stage.

## Scripts

| Script | Stage | Description |
|--------|-------|-------------|
| `pdf_parser.py` | Parse | PDF → GROBID → metadata JSON + raw text |
| `metadata_extractor.py` | Metadata | Metadata enrichment (DOI, Crossref, PubMed) |
| `retag.py` | Tag | Tag assignment and recalibration |
| `build_embeddings.py` | Embedding | Build vector embeddings |
| `search_test.py` | Retrieval | Retrieval validation testing |
| `system_check.py` | System | Runtime dependency health check |
| `ensure_grobid.py` | Infra | GROBID Docker container management |
| `grobid_client.py` | Client | GROBID API client library |
| `grobid_diagnostic.py` | Diag | GROBID diagnostic report |
| `run_api_server.py` | API | Start Query API server |
| `run_workflow.py` | Workflow | Workflow entry point |

## User Editing

**No** — source code. Modify only during development.
