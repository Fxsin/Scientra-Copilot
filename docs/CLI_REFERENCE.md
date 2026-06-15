# CLI Reference

## Setup

| Script | Purpose |
|--------|---------|
| `Scripts/setup.py` | Initial project setup |
| `Scripts/dev_restart.py` | Restart development server |

## Import & Assets

| Script | Example |
|--------|---------|
| `Scripts/add_paper_asset.py` | `--paper-id paper_xxx --file Table_S1.xlsx` |
| `Scripts/init_paper_assets.py` | `--paper-id paper_xxx` |

## Asset Intelligence (P4)

| Script | Example |
|--------|---------|
| `Scripts/build_asset_links.py` | `--all --verbose` |
| `Scripts/build_figure_intelligence.py` | `--paper-id paper_xxx --mode rule` |
| `Scripts/build_table_intelligence.py` | `--all --mode rule --max-sample-rows 30` |
| `Scripts/build_supplementary_intelligence.py` | `--paper-id paper_xxx --mode auto` |

## Knowledge Layer (P5)

| Script | Example |
|--------|---------|
| `Scripts/build_unified_evidence_graph.py` | `--verbose --validate --export-graphml` |
| `Scripts/query_cross_assets.py` | `--query "MAP2K4 expression" --json` |
| `Scripts/build_dataset_intelligence.py` | `--all --sample-rows 100 --build-cross-paper-index` |
| `Scripts/query_datasets.py` | `--entity DEMO_GENE_A --json` |
| `Scripts/ask_research_agent.py` | `--query "research plan for receptor mechanism" --mode auto` |

## Quality & Demo (P6)

| Script | Example |
|--------|---------|
| `Scripts/run_e2e_validation.py` | `--all --verbose` |
| `Scripts/export_quality_dashboard.py` | `--markdown --csv` |
| `Scripts/create_demo_project.py` | `--create-only --force` |
| `Scripts/run_demo_queries.py` | `--use-cross-asset --use-dataset` |
| `Scripts/update_docs.py` | `--all --verbose` |
