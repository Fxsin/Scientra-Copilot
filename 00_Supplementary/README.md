# Manual Supplementary File Import — 00_Supplementary

## Purpose

Place downloaded supplementary data files (xlsx, csv, tsv) from published papers here for automatic matching and preview extraction.

## Directory Structure

```
00_Supplementary/
├── README.md       # This file
├── inbox/          # Place your downloaded supplementary files here
├── matched/        # Optional: matched files after import
├── unmatched/      # Optional: unmatched files after import
└── registry/       # Import reports and file index
```

## Supported File Types

- `.xlsx` / `.xls` — Excel workbooks (sheets previewed separately)
- `.csv` — Comma-separated values
- `.tsv` — Tab-separated values
- `.txt` — Tabular text files (if delimited)

## Recommended Naming

To maximize match confidence, use one of these naming patterns:

```
{paper_id}__Table_S1.xlsx
{paper_id}__Supplementary_Data_1.xlsx
{paper_id}__Table_S2.csv
{paper_id_short}__Supplementary_Table_S3.xlsx
{title_keyword}__Table_1.xlsx
```

Examples:
```
Bacillus_thuringiensis_toxins_an_overview_be8f9a28904d__Table_S1.xlsx
Spodoptera_frugiperda__Supplementary_Data_1.csv
```

## Important Notes

- **Do NOT** place raw PDFs here — use 01_PDF/
- **Do NOT** place API keys or credentials
- **Do NOT** place raw_text sources — use 03_Summary/
- Large files will only have the first 20 rows previewed
- Full file contents are NEVER read into memory
- File paths are stored as relative paths only (no absolute paths)

## Running the Import

```bash
# Scan inbox and generate import registry
python -m scientra.pdf_data_assets.build_assets --import-supplementary

# Full pipeline: import + match + regenerate chunks
python -m scientra.pdf_data_assets.build_assets --import-supplementary --supplementary --all --force

# Quality check and re-embedding after import
python -m scientra.pdf_data_assets.build_assets --quality-check
python -m scientra.pdf_data_assets.asset_embedding --all --force
```

## Querying Imported Supplementary Data

```python
from scientra.sdk import query_assets
results = query_assets("expression data", chunk_types=["supplementary_table"])
```
