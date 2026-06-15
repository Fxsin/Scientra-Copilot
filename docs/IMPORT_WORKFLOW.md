# Import Workflow

## Article Bundle Structure

Place article bundles in `00_Inbox/article_bundles/`:

```
00_Inbox/article_bundles/
└── Your_Paper_Name/
    ├── main_paper.pdf          # Main article PDF
    ├── Table_S1.xlsx           # Supplementary table
    ├── Table_S2.csv            # Supplementary data
    ├── Figure_S1.png           # Supplementary figure
    ├── Supplementary_Methods.pdf
    └── asset_notes.txt         # Asset titles (recommended)
```

## asset_notes.txt Format

```
## Title: Table S1 — Gene expression results
## Title: Table S2 — Bioassay LC50 data
## Title: Figure S1 — Experimental workflow
## Title: Supplementary Methods — Detailed protocols
```

## Single Paper Import

Use the web Import page at `/import` or:

```bash
# Place PDF + supplementary files in 01_Sources/
python Scripts/add_paper_asset.py --file "Table_S1.xlsx" --doi "10.xxxx/xxxx"
```

## Loose Supplementary Files

Place in `00_Inbox/loose_supplementary/` for review before binding to papers.

## File Naming Tips

- Use descriptive names: `Table_S1_gene_expression.csv`
- Avoid special characters: use `_` not spaces
- Group supplementary files with the main paper
- Include `asset_notes.txt` for better matching
