# Supplementary Table Linking — Phase 2C

## 1. Phase 2C Objectives

Identify supplementary table/data references in paper text and establish links to available files.

**This phase does NOT:**
- Use OCR
- Call any LLM
- Parse complex Excel/PDF contents
- Download supplementary files from publisher websites
- Modify 03_Evidence or original PDFs

## 2. Why Supplementary Tables Matter

Supplementary tables often contain the most valuable structured data:
- Full gene expression tables
- Complete bioassay results
- Primer/plasmid sequences
- Statistical model parameters
- Raw omics data

These are more valuable for evidence than PDF-embedded tables because they are already machine-readable (xlsx/csv).

## 3. Supplementary Reference Identification

Supported patterns:

| Pattern | Example |
|---|---|
| `Supplementary Table S1` | "see Supplementary Table S1" |
| `Table S1` | "as shown in Table S1" |
| `Tables S1-S3` | "Tables S1-S3 list..." |
| `Supplementary Data 1` | "available as Supplementary Data 1" |
| `Additional file 1` | "provided in Additional file 1" |
| `Supporting Information Table S1` | "see Supporting Information Table S1" |
| `Supplementary Excel` | "Supplementary Excel file" |

## 4. File Matching Strategies

| Strategy | Method | Confidence |
|---|---|---|
| Exact label in filename | `exact_label_filename` | high |
| Paper ID in file path | `paper_id_filename` | low |
| Title keyword in filename | `title_keyword_filename` | low |
| Generic supplementary index | `supplementary_index` | low |
| Manual review needed | `manual_needed` | none |

## 5. Preview Support

| File Type | Preview | Status |
|---|---|---|
| csv | Full (columns + 20 rows) | `simple_preview_extracted` |
| tsv | Full (columns + 20 rows) | `simple_preview_extracted` |
| xlsx | First sheet, first 20 rows | `simple_preview_extracted` (requires openpyxl) |
| txt | Delimited detection | `simple_preview_extracted` |
| pdf | No preview | `complex_file_skipped` |
| docx | No preview | `complex_file_skipped` |
| zip | No preview | `complex_file_skipped` |

## 6. Content Status Values

| Status | Meaning |
|---|---|
| `link_only` | Reference found, no file checking attempted |
| `file_found` | Local file matched |
| `file_missing` | Reference found but no local file |
| `file_unreadable` | File found but unreadable |
| `simple_preview_extracted` | Lightweight preview extracted |
| `complex_file_skipped` | File type not supported for preview |

## 7. Output Paths

```
06_PDF_DataAssets/08_supplementary_links/{paper_id}/supplementary_links.json
06_PDF_DataAssets/00_registry/supplementary_file_inventory.md
06_PDF_DataAssets/00_registry/supplementary_table_linking_report.md
```

## 8. Running

```bash
# Single paper
python -m scientra.pdf_data_assets.build_assets --supplementary --paper-id <paper_id>

# All papers
python -m scientra.pdf_data_assets.build_assets --supplementary --all --force

# Quality check + re-embedding
python -m scientra.pdf_data_assets.build_assets --quality-check
python -m scientra.pdf_data_assets.asset_embedding --all --force
```

## 9. Current Status

- No paper-specific supplementary files (xlsx, csv) are stored locally
- All references are identified from raw text
- Most links have `content_status: file_missing`
- Supplementary files remain on publisher websites
- To enable preview, download supplementary files to project directory

## 10. Phase 2D Outlook

Phase 2D will optionally use LLM to interpret supplementary table data combined with captions to generate evidence claims.
