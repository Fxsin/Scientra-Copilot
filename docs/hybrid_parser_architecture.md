# Hybrid PDF Parser Architecture

## Why Hybrid, Not Replacement?

GROBID is excellent at metadata extraction (title, authors, affiliations, DOI, references) but has limitations for full-text markdown, layout/bbox data, table extraction, and figure handling.

The Hybrid Parser brings together four complementary tools, each doing what it does best:

| Parser | Primary Role | Output |
|--------|-------------|--------|
| **GROBID** | Metadata, references, citation metadata | TEI XML, metadata JSON |
| **OpenDataLoader PDF** | Markdown, layout/bbox, reading order, tables | `.md`, layout JSON, tables JSON |
| **Marker** | High-quality markdown (backup) | `.md` |
| **PyMuPDF** | Fast scan, raw text, figure extraction | scan report JSON, raw images |

No parser replaces another — they **collaborate**.

## Parser Responsibilities

### GROBID
- Title, authors, affiliations, abstract
- DOI, journal, year
- References and citation metadata
- Keeps existing Docker/GROBID flow intact

### OpenDataLoader PDF
- Markdown with reading order
- Layout JSON (bbox, page blocks)
- Table extraction
- Preferred markdown source

### Marker (Optional)
- High-quality Markdown
- Only enabled if OpenDataLoader quality is insufficient
- Default: **disabled**

### PyMuPDF (fitz)
- PDF quick scan (page count, text layer, images)
- Scanned PDF detection
- Raw text fallback
- Image/figure extraction

## Storage Layout v3 Mapping

All outputs strictly follow Storage Layout v3:

```
02_Parse/
├── markdown/
│   ├── opendataloader/    ← OpenDataLoader markdown
│   ├── marker/             ← Marker markdown (optional)
│   └── final/              ← Merged final markdown
├── layout/
│   └── opendataloader/     ← Layout/bbox JSON
├── tables/
│   └── opendataloader/     ← Table extraction JSON
├── figures/
│   └── raw_images/         ← PyMuPDF extracted images
├── text/
│   ├── pymupdf/            ← PyMuPDF raw text
│   └── grobid/             ← GROBID TEI XML
└── reports/
    ├── pymupdf/            ← PDF scan reports
    ├── grobid/             ← GROBID metadata JSON
    └── hybrid/             ← Hybrid parse manifests
```

## Configuration

In `Config/workflow_config.yaml`:

```yaml
hybrid_parser:
  enabled: false              # DEFAULT: disabled (safe)
  use_grobid: true
  use_opendataloader: true
  use_marker: false
  use_pymupdf: true
  prefer_markdown_source: opendataloader
  fallback_markdown_source: marker
  save_layout_bbox: true
  save_raw_figures: true
  output_root: "02_Parse"
  manifest_dir: "02_Parse/reports/hybrid"
```

## How to Enable

1. Install dependencies:
   ```bash
   pip install pymupdf opendataloader marker-pdf
   ```

2. Edit `Config/workflow_config.yaml`:
   ```yaml
   hybrid_parser:
     enabled: true
   ```

3. Restart the API server.

## How to Disable / Rollback

Set `enabled: false` in `Config/workflow_config.yaml`. The system falls back to the legacy GROBID-only flow immediately. No data loss — the hybrid parse outputs coexist alongside legacy outputs.

## How to Verify OpenDataLoader Is Connected

1. Check `/import/status` — `parser_availability.opendataloader_available` should be `true`.
2. Check a paper's `/paper/{paper_id}/parse-report` — `status` should be `hybrid_parsed`.
3. Look in `02_Parse/markdown/opendataloader/` for `.md` files.

## API Endpoints

### `GET /import/status`
Now includes `parser_availability`:
```json
{
  "parser_availability": {
    "grobid_available": true,
    "opendataloader_available": false,
    "marker_available": false,
    "pymupdf_available": true,
    "hybrid_parser_enabled": false
  }
}
```

### `GET /paper/{paper_id}/parse-report`
Returns hybrid parse manifest if available, or legacy-only status:
```json
{
  "paper_id": "paper_abc123",
  "status": "hybrid_parsed",
  "parser_used": {
    "metadata_source": "grobid",
    "markdown_source": "opendataloader",
    "layout_source": "opendataloader",
    "figures_source": "pymupdf",
    "tables_source": "opendataloader",
    "references_source": "grobid"
  },
  "quality_report": { "overall_score": 0.82 },
  "warnings": [],
  "errors": []
}
```

## PDF Type Routing

| PDF Type | Parsers Run |
|----------|-------------|
| `normal_paper` | GROBID + OpenDataLoader + PyMuPDF |
| `supplementary_pdf` | OpenDataLoader + PyMuPDF |
| `scanned_pdf` | PyMuPDF only (low quality flag) |
| `table_heavy_pdf` | All parsers |
| `image_heavy_pdf` | All parsers |
| `unknown` | All parsers |

## Future Roadmap

1. **Evidence click-to-source** — use layout/bbox data to link evidence claims to PDF positions
2. **Figure/table cards** — structured figure and table assets from hybrid parse
3. **Body-figure-supplementary linking** — cross-reference figures in text with supplementary data
4. **Agent answer bbox citation** — cite exact bounding-box locations in PDF for agent answers
5. **OCR fallback** — Tesseract/other OCR for scanned PDFs

## Graceful Degradation

Every adapter follows the same pattern:
- Dependency missing → `status: "skipped"` (never crashes)
- Parse failure → `status: "failed"` with error details
- Success → `status: "success"` with output paths

The system always produces a manifest, even if all parsers fail.
