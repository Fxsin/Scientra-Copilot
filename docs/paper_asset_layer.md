# Paper Asset Layer (Phase 4.0)

## Why Paper Asset Layer?

Research papers come with more than just the main PDF. Over time, users accumulate:

- Supplementary PDFs (appendix, supporting information)
- Table files (Excel, CSV datasets)
- Figure images (PNG, TIFF)
- Archive files (ZIP bundles of raw data)

The Paper Asset Layer provides a unified way to manage all these files alongside the main paper, without requiring re-import or re-processing of the primary content.

## User Scenario

1. User imports a main PDF → summary, evidence, gaps, hypotheses are generated.
2. Weeks later, user finds a supplementary PDF and a table spreadsheet.
3. User visits Paper Detail → Add Asset → uploads the files.
4. Files are automatically classified, stored, and linked to the paper.
5. The main PDF pipeline is NOT re-triggered.
6. Future phases (Figure Intelligence, Table Intelligence) will process these assets independently.

## File Layout

```
01_Sources/papers/{paper_id}/
├── main.pdf                 # Reference only — actual file stays in 01_PDF/
├── paper_assets.json         # Asset registry
├── assets/
│   ├── supplementary/        # Supplementary PDFs
│   ├── figures/             # Figure images
│   ├── tables/              # Excel/CSV table files
│   ├── datasets/            # CSV/TSV data files
│   ├── images/              # General images
│   ├── archives/            # ZIP/RAR archives
│   └── attachments/         # Other files
├── links/
│   ├── asset_links.json      # Reserved for future use
│   └── body_asset_links.json # Reserved for future use
```

**Important rules:**
- Existing main PDF files in `01_PDF/` are NOT moved.
- Asset upload does NOT trigger summary/evidence/gap/hypothesis pipelines.
- Only `paper_assets.json` and the `assets/` directory are created.

## Asset Types

| Type | Extensions | Directory |
|------|-----------|-----------|
| `main_pdf` | .pdf (first PDF) | tracked in registry only |
| `supplementary_pdf` | .pdf (matching keywords) | assets/supplementary/ |
| `supplementary_table` | .xlsx, .xls | assets/tables/ |
| `dataset` | .csv, .tsv | assets/datasets/ |
| `figure_image` | .png, .jpg, .tif | assets/images/ |
| `table_image` | .png, .jpg (table in name) | assets/images/ |
| `archive` | .zip, .rar, .7z | assets/archives/ |
| `attachment` | .doc, .txt, other | assets/attachments/ |
| `unknown` | anything else | assets/attachments/ |

## Asset Registry Fields

Each asset in `paper_assets.json`:

| Field | Description |
|-------|------------|
| `asset_id` | Unique ID (e.g., `asset_d0cf4389_0001`) |
| `paper_id` | Parent paper ID |
| `asset_type` | One of the types above |
| `filename` | Safe filename on disk |
| `original_filename` | Original uploaded filename |
| `relative_path` | Path relative to paper directory |
| `sha256` | SHA-256 hash for deduplication |
| `size_bytes` | File size |
| `status` | `registered`, `pending`, `processing`, `processed`, `failed`, `skipped` |
| `source` | `initial_import`, `manual_upload`, `web_upload`, `folder_scan` |
| `warnings` | Classification/processing warnings |
| `errors` | Error messages |

## CLI Usage

### Initialize all papers

```bash
python Scripts/init_paper_assets.py
python Scripts/init_paper_assets.py --dry-run
```

### Add a file to a paper

```bash
python Scripts/add_paper_asset.py --paper-id paper_d0cf4389f4ef6e06 --file "supplementary.pdf"
python Scripts/add_paper_asset.py --paper-id paper_d0cf4389f4ef6e06 --file "Table_S1.xlsx" --asset-type supplementary_table
python Scripts/add_paper_asset.py --paper-id paper_d0cf4389f4ef6e06 --dir "supplementary_files/"
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/paper/{id}/assets` | List all assets |
| POST | `/paper/{id}/assets/register` | Register a single file |
| POST | `/paper/{id}/assets/scan` | Scan and register unregistered files |
| DELETE | `/paper/{id}/assets/{asset_id}` | Logical delete (file preserved) |

## Web Upload

Visit the Paper Detail page → Assets section → Add Asset button → drag & drop files.

## Relationship to Main PDF Pipeline

```
Main PDF Pipeline:
  PDF → Summary → Evidence → Gaps → Hypotheses → Opportunities

Asset Pipeline (independent):
  Supplementary/Figure/Table/Dataset → Asset Registry → Pending Processing
```

The two pipelines are independent. Adding assets never triggers main PDF reprocessing.

## Future Phases

- **P4.1 Figure Intelligence**: Process `figure_image` assets for AI interpretation
- **P4.2 Table Intelligence**: Process `supplementary_table` and `dataset` assets
- **P4.3 Supplementary AI**: Process `supplementary_pdf` assets for content extraction
