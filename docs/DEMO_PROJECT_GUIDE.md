# Demo Project Guide

> ⚠️ ALL DEMO DATA IS SYNTHETIC — FOR FUNCTIONALITY TESTING ONLY.

## Quick Start

```bash
python Scripts/create_demo_project.py --create-only
python Scripts/run_demo_queries.py --use-cross-asset --use-dataset --verbose
```

## What's Included

The demo creates a synthetic paper: "Demo Plant Stress Response Study" with:
- `main_demo_paper.txt` — Synthetic paper text with Figure/Table citations
- `Table_S1_gene_expression.csv` — Differential expression (10 genes)
- `Table_S2_bioassay.csv` — LC50 bioassay (12 samples)
- `Supplementary_Methods.md` — Methods + dataset descriptions
- `Figure_S1_caption.txt` — Workflow figure caption
- `asset_notes.txt` — Asset titles for matching

## Demo Queries

| Query | What it tests |
|-------|--------------|
| `DEMO_GENE_A expression` | Cross-asset search |
| `gene expression dataset` | Dataset type detection |
| `LC50 bioassay` | Bioassay schema inference |
| `Which tables support the demo findings?` | Evidence chain |
| `Generate a research plan based on demo gaps` | Research agent |

## Expected Results

- Entities: DEMO_GENE_A through DEMO_ENZYME_J
- Dataset types: differential_expression, bioassay
- Asset links: Table S1, Table S2, Figure S1, Supplementary Methods

## Location

- Source: `examples/demo_project/`
- Import staging: `00_Inbox/article_bundles/demo/`
- Query outputs: `09_Exports/demo_project/`
