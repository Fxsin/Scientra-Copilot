# Simple Table Structure Extraction — Phase 2B

## 1. Phase 2B Objectives

Parse simple text-based table structures from raw text sources.

**This phase:**
- Detects markdown-like, tab-delimited, and whitespace-aligned tables
- Extracts column headers and row data
- Classifies tables as simple/complex/unavailable
- Upgrades `structure_status` from `caption_only` to `simple_structure_extracted`

**This phase does NOT:**
- Use OCR
- Call any LLM
- Parse PDF layouts
- Handle multi-level headers or merged cells
- Process image-based tables
- Force-parse complex tables

## 2. Why Only Simple Tables

In GROBID-extracted raw text:
- Tables lose visual layout — no gridlines, no cell borders
- Column alignment is preserved as whitespace gaps
- Complex tables (merged cells, multi-line cells) become garbled text
- Simple tables (consistent column counts, single-line cells) survive decently

Parsing simple tables gives us structure for ~30-50% of tables without risking data integrity. Complex tables are explicitly marked `complex_structure_skipped` rather than guessed.

## 3. Supported Structure Types

| Type | Detection | Confidence |
|---|---|---|
| Markdown-like pipe tables | `\| col \| col \|` lines | high |
| Tab-delimited tables | `\t` separation | high |
| Whitespace-aligned tables | 2+ space gaps between columns | medium |
| Simple supplementary indices | consistent delimited structure | low/medium |

## 4. Skipped Complex Tables

Marked as `complex_structure_skipped` when:
- Column counts vary wildly (>40% inconsistent)
- Multi-level header patterns detected
- Cell text exceeds 200 characters
- Row count exceeds 100
- Column count exceeds 30
- No viable table body found after caption

## 5. New TableAsset Structure Fields

- `structured_rows: list[dict[str, str]]` — parsed rows as `{column: value}`
- `structured_columns: list[str]` — column header names
- `raw_table_text: str | None` — raw table body block
- `structure_confidence: str` — high / medium / low / none
- `structure_extraction_method: str` — raw_text_delimited / markdown_like / whitespace_aligned / skipped_complex / unavailable
- `structure_notes: list[str]` — extraction notes

## 6. Output Path

```
06_PDF_DataAssets/03_tables/{paper_id}/tables.json  (updated with structure fields)
06_PDF_DataAssets/00_registry/table_extraction_report.md  (updated with structure stats)
```

## 7. Regenerating Table Assets with Structure

```bash
# Single paper
python -m scientra.pdf_data_assets.build_assets --tables --paper-id <paper_id> --force

# All papers
python -m scientra.pdf_data_assets.build_assets --tables --all --force
```

## 8. Re-embedding

```bash
python -m scientra.pdf_data_assets.build_assets --quality-check
python -m scientra.pdf_data_assets.asset_embedding --all --force
```

Enhanced table chunks include: column names, row count, representative rows, structure confidence.

## 9. Querying Table Structure via API

```python
from scientra.sdk import query_assets

# Query structured tables
results = query_assets(
    query="LC50 toxicity bioassay",
    chunk_types=["table"],
    top_k=10
)
# Simple structure tables have rich metadata in LanceDB
```

## 10. Phase 2C / 2D Outlook

- **Phase 2C: Supplementary Table Linking** — link supplementary table references to their external files
- **Phase 2D: Table Data Interpretation** — use LLM to interpret table structure + caption → evidence claims (optional, requires LLM)
