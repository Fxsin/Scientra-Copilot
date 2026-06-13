# Manual Supplementary File Import — Phase 2D

## 1. Phase 2D Objectives

Provide a user-controlled mechanism to import downloaded supplementary data files (xlsx, csv, tsv) from published papers. The system scans `00_Supplementary/inbox/`, matches files to known paper references, extracts lightweight previews, and generates high-quality supplementary_table chunks for the vector database.

## 2. Why Manual Import

Supplementary data files are stored on publisher websites, not in the local project. Rather than building a downloader (which would need authentication, rate limiting, and publisher-specific logic), Phase 2D provides a simple drop-in directory for users to place files they've already downloaded.

## 3. Directory Structure

```
00_Supplementary/
├── README.md
├── inbox/          # Place downloaded files here
├── matched/        # (optional) matched files after import
├── unmatched/      # (optional) unmatched files after import
└── registry/       # Import reports and file index
```

## 4. Supported File Types

| Type | Preview | Notes |
|---|---|---|
| `.xlsx` / `.xls` | First sheet, 20 rows | Requires openpyxl; sheet names captured |
| `.csv` | Full preview, 20 rows | Auto-detected |
| `.tsv` | Full preview, 20 rows | Tab/CSV detection |
| `.txt` | Only if tabular | CSV/TSV detection |

## 5. Recommended Naming

```
{paper_id}__Table_S1.xlsx
{paper_id}__Supplementary_Data_1.csv
{paper_id_short}__Table_S2.xlsx
```

Higher match confidence when both paper_id and supplement label are present.

## 6. Matching Strategies

| Priority | Method | Requires |
|---|---|---|
| 1 | `manual_paper_id_label` | paper_id + supplement label in filename |
| 2 | `manual_paper_id_only` | paper_id in filename |
| 3 | `manual_label_only` | supplement label in filename |
| 4 | `no_local_file` | No matching file |

## 7. Running

```bash
# Step 1: Scan inbox and build import registry
python -m scientra.pdf_data_assets.build_assets --import-supplementary

# Step 2: Match imports to references + regenerate chunks
python -m scientra.pdf_data_assets.build_assets --supplementary --all --force

# Step 3: Quality check + re-embedding
python -m scientra.pdf_data_assets.build_assets --quality-check
python -m scientra.pdf_data_assets.asset_embedding --all --force
```

## 8. Querying

```python
from scientra.sdk import query_assets
results = query_assets("expression data", chunk_types=["supplementary_table"])
```

## 9. Future: Phase 2E

Phase 2E will build on the imported supplementary data to create entity indices and enable gene-level queries (e.g., "which supplementary tables mention gene X?").
