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
  use_marker: auto            # "auto" | true | false. "auto" triggers when ODL quality < marker_trigger_score
  use_pymupdf: true
  prefer_markdown_source: opendataloader    # "opendataloader" | "marker"
  fallback_markdown_source: marker          # "marker" | "none"
  marker_trigger_score: 0.65  # Auto-trigger Marker when ODL markdown score is below this
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

## Marker Auto-Trigger Logic

When `use_marker: auto`, Marker is conditionally invoked:

1. OpenDataLoader is skipped or failed → run Marker
2. OpenDataLoader `quality_score` < `marker_trigger_score` (default 0.65) → run Marker
3. OpenDataLoader markdown file is missing or < 500 chars → run Marker
4. Otherwise → skip Marker (ODL quality is sufficient)

Set `use_marker: true` to always run Marker alongside OpenDataLoader.
Set `use_marker: false` to never run Marker.

## Workflow Integration

When `hybrid_parser.enabled: true`, the workflow runner (`scientra/workflow.py`) runs
the hybrid parser as a builtin step between `summary` and `evidence`:

```
import_pdf → parse → metadata → tag → summary → hybrid_parse → evidence → embedding → lancedb → index_update
```

The `hybrid_parse` step:
- Is **optional** — failure does not block the workflow
- Scans all PDFs in `01_PDF/` and `01_Sources/papers/`
- Derives `paper_id` from PDF filename stem
- Skips silently when `hybrid_parser.enabled: false`

## P1 Evidence Input Selection

### Overview

P1 allows evidence extraction to preferentially use the hybrid parser's final markdown
(`02_Parse/markdown/final/{paper_id}.md`) instead of legacy GROBID raw text
(`03_Summary/raw_text/{paper_id}.txt`).

Final markdown from the hybrid pipeline has better structure:
- Proper heading hierarchy (Introduction, Methods, Results, Discussion, etc.)
- Reading-order-aware text flow (from OpenDataLoader layout analysis)
- Cleaner text (less encoding artifacts vs raw GROBID TEI recombination)

This means `extract_sections()` can more accurately detect section boundaries,
leading to better key result extraction, method identification, and discussion parsing.

### How It Works

The module `scientra/parsers/hybrid_input_selector.py` provides `select_text_for_evidence()`:

```
select_text_for_evidence(paper_id, legacy_text_path, config, root) → {
    "text": "...",
    "source": "hybrid_final_markdown" | "legacy_raw_text" | "grobid_text" | "missing",
    "source_path": "/path/to/source",
    "quality_score": 0.85,
    "warnings": [...],
    "fallback_reason": null | "Quality below threshold" | ...
}
```

Decision flow:
1. `prefer_hybrid_markdown_for_evidence=false` → immediate legacy fallback
2. Final markdown missing → legacy fallback
3. Final markdown empty → legacy fallback
4. Parse manifest `quality_report.overall_score` < threshold → legacy fallback
5. All checks pass → return hybrid final markdown

### Configuration

```yaml
hybrid_parser:
  prefer_hybrid_markdown_for_evidence: false  # DEFAULT: false (legacy safe)
  min_final_markdown_score_for_evidence: 0.65  # Min quality to use hybrid markdown
```

### How to Enable

```yaml
# Config/workflow_config.yaml
hybrid_parser:
  enabled: true
  prefer_hybrid_markdown_for_evidence: true
```

Then run evidence extraction:
```bash
python -m scientra.evidence_extraction
```

### How to Verify

Check the evidence output:
```json
{
  "paper_id": "paper_001",
  "evidence_input_source": "hybrid_final_markdown",
  "evidence_input_path": "02_Parse/markdown/final/paper_001.md",
  "evidence_input_quality_score": 0.82
}
```

Or if legacy was used:
```json
{
  "evidence_input_source": "legacy_raw_text",
  "fallback_reason": "Final markdown not found at 02_Parse/markdown/final/"
}
```

### Why This Doesn't Change Embedding/LanceDB Schema

The evidence and chunk schemas remain unchanged. Only the *text input source* changes.
Downstream systems (embedding, LanceDB, vector search) operate on the same data structures
regardless of whether the text came from legacy raw_text or hybrid markdown.

The `evidence_input_source` and `evidence_input_path` fields are added to the evidence JSON
for auditability, but are not indexed — they are metadata-only fields.

### Rollback

Set `prefer_hybrid_markdown_for_evidence: false` and re-run evidence extraction.
The system immediately returns to using legacy raw text. No data migration needed.

## P1.5 Evidence Input Validation & Comparison

### Overview

P1.5 adds a validation layer that compares evidence extraction results between
legacy raw text and hybrid final markdown **without modifying the main pipeline**.

This allows you to make a data-driven decision about whether to enable
`prefer_hybrid_markdown_for_evidence` for your specific paper collection.

### How It Works

The module `scientra/parsers/evidence_input_comparison.py` provides
`compare_evidence_inputs()` which:

1. Locates both text sources (legacy and hybrid)
2. Runs `extract_sections()` + `extract_evidence()` on each independently
3. Computes comparison metrics (text length, headings, evidence counts, malformed ratio)
4. Generates a recommendation based on 5 quality checks
5. Saves results to `02_Parse/reports/hybrid_validation/`

**Critical: Zero pollution guarantee:**
- Does NOT write to `03_Evidence/`
- Does NOT trigger embedding
- Does NOT touch LanceDB
- All outputs go exclusively to `02_Parse/reports/hybrid_validation/`

### CLI Usage

```bash
# Single paper comparison
python Scripts/compare_evidence_inputs.py --paper-id paper_001

# Batch comparison
python Scripts/compare_evidence_inputs.py --all --limit 20

# With quality filter
python Scripts/compare_evidence_inputs.py --all --min-quality 0.70

# Machine-readable output
python Scripts/compare_evidence_inputs.py --paper-id paper_001 --json
```

### Comparison Report

Per-paper report at `02_Parse/reports/hybrid_validation/{paper_id}_evidence_input_comparison.json`:

```json
{
  "paper_id": "paper_001",
  "recommendation": "use_hybrid_markdown",
  "sources": {
    "legacy_raw_text_available": true,
    "hybrid_final_markdown_available": true,
    "hybrid_parse_quality_score": 0.85
  },
  "comparison": {
    "text_length_delta": 200,
    "text_length_ratio": 1.04,
    "heading_count_delta": 3,
    "malformed_text_ratio_delta": -0.001,
    "evidence_count_delta": 2,
    "evidence_count_ratio": 1.12
  }
}
```

Batch summary at `02_Parse/reports/hybrid_validation/summary.json`.

### Recommendation Logic

The system evaluates 5 checks:

| Check | Criterion |
|-------|-----------|
| Text length | hybrid >= 80% of legacy |
| Heading count | hybrid >= legacy |
| Malformed ratio | hybrid not significantly worse (≤ 1.5× legacy) |
| Evidence count | hybrid >= 70% of legacy |
| Section coverage | methods AND results detected in hybrid |

Results:
- **5/5 or 4/5 passed** → `use_hybrid_markdown`
- **3/5 passed** → `manual_review`
- **≤ 2/5 passed** → `use_legacy_raw_text`
- **No data available** → `insufficient_data`

### Recommended Enablement Criteria

Before setting `prefer_hybrid_markdown_for_evidence: true`, run a batch comparison
on at least 20 papers from diverse journals:

```bash
python Scripts/compare_evidence_inputs.py --all --limit 20
```

Enable when:
- `hybrid_recommended_pct` >= 70%
- `manual_review_pct` <= 20%
- `average_hybrid_evidence_count` >= `average_legacy_evidence_count` × 0.7
- No large-scale evidence count drops observed

## Future Roadmap

1. **Bbox citation for agent answers** — use `02_Parse/layout/opendataloader/{paper_id}.json`
   to map evidence claims back to exact PDF bounding boxes. This enables:
   - "Click to see source in PDF" in the web UI
   - Agent answers with page+bbox citations
   - Implementation: load layout JSON, match evidence text spans to bbox entries

3. **Figure/table cards** — structured assets from hybrid parse outputs:
   - Figures: `02_Parse/figures/raw_images/{paper_id}/` → image cards with captions
   - Tables: `02_Parse/tables/opendataloader/{paper_id}.json` → rendered table cards
   - These feed into `scientra/pdf_data_assets/` for the asset pipeline

4. **Body-figure-supplementary linking** — cross-reference:
   - Figure mentions in markdown → figure image files
   - Table references in text → structured table data
   - Supplementary file citations → supplementary assets

5. **OCR fallback** — Tesseract/Surya OCR for scanned PDFs detected by PyMuPDF scan
   (`suspected_scanned_pdf: true`). Currently scanned PDFs are flagged but not OCR'd.

## Graceful Degradation

Every adapter follows the same pattern:
- Dependency missing → `status: "skipped"` (never crashes)
- Parse failure → `status: "failed"` with error details
- Success → `status: "success"` with output paths

The system always produces a manifest, even if all parsers fail.
