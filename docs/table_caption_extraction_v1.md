# Table Caption + Reference Extraction — Phase 2A

## 1. Phase 2A Objectives

Extract table labels, captions, in-text reference sentences, and table types from scientific papers. Establish preliminary links to result assets, claim assets, and evidence.

**This phase does NOT:**
- Parse complex table row/column structures
- Use OCR
- Call any LLM
- Modify 03_Evidence original data
- Modify original PDFs
- Modify LanceDB table structures

## 2. Why Caption/Reference First (Not Complex Structure)

- Table structure parsing (rows, columns, headers) is highly dependent on PDF layout quality
- Many papers use complex multi-level headers, merged cells, and footnotes
- Caption and reference extraction is robust, rule-based, and works on plain text
- Even without full structure data, captions + reference links provide valuable context for evidence retrieval
- Phase 2B will add simple structure extraction for well-formatted tables

## 3. TableAsset Schema

See `scientra/pdf_data_assets/schemas.py` for the full `TableAsset` model.

Key fields:
- `asset_id`: Unique identifier (`{paper_id}:table:{index}`)
- `table_label`: e.g. "Table 1", "Supplementary Table S1"
- `table_number`: e.g. "1", "S1"
- `caption`: Full table caption text
- `source_text`: Caption or reference source (for traceability)
- `table_type`: Rule-based classification (see Section 6)
- `reference_sentences`: Sentences in the paper that reference this table
- `linked_result_assets`: Related result asset IDs
- `linked_claim_assets`: Related claim asset IDs
- `linked_evidence_ids`: Related evidence item IDs
- `caption_quality`: high / medium / low / none
- `caption_source`: plain_text_caption / reference_only
- `structure_status`: caption_only (Phase 2A default)
- `confidence`: high / medium / low

## 4. Extraction Sources

### Primary Source
`03_Summary/raw_text/*.txt` — plain text extracted from PDFs via GROBID or similar tools.

### Fallback Source
`03_Evidence/{paper_id}/evidence.json` — structured evidence fields (methods, key_results, core_findings, discussion_points).

## 5. Linking Logic

The `TableLinker` module scans evidence fields for in-text table references:
- "Table 1 shows..."
- "...as shown in Table 2"
- "Tables 1 and 2 demonstrate..."
- "Supplementary Table S1 lists..."

Each reference is linked to:
1. The table label (by matching table_number)
2. The source section (results, discussion, methods)
3. Evidence item ID (`{paper_id}:{field_name}:{index}`)

## 6. Table Type Classification Rules

Rule-based classification using caption + reference sentence text:

| table_type | Keywords |
|---|---|
| toxicity_or_bioassay | LC50, LD50, mortality, toxicity, bioassay, feeding assay, survival |
| expression_or_production | expression, purification, yield, production, recombinant, soluble |
| binding_or_affinity | binding, affinity, Kd, competition, SPR, BBMV, dissociation constant |
| omics_data | RNA-seq, transcriptome, proteome, DEG, differentially expressed, GO term |
| gene_or_protein_list | gene list, protein list, accession, locus tag, ORF |
| primer_or_plasmid | primer, plasmid, vector, oligonucleotide, construct |
| strain_or_sample | strain, isolate, sample, specimen, collection site |
| statistics_or_model | p-value, regression, ANOVA, model, correlation, coefficient |
| phenotype_summary | phenotype, morphology, growth rate, symptom, efficacy, potency |
| sequence_or_domain | sequence, domain, identity, alignment, conserved, motif |
| supplementary_index | supplementary table, supplementary information, additional file |
| unknown | (no keywords matched) |

## 7. Output Path

```
06_PDF_DataAssets/03_tables/{paper_id}/tables.json
06_PDF_DataAssets/00_registry/table_extraction_report.md
```

## 8. Regenerating Table Chunks

```bash
# Single paper
python -m scientra.pdf_data_assets.build_assets --tables --paper-id <paper_id>

# All papers
python -m scientra.pdf_data_assets.build_assets --tables --all --force
```

This automatically:
1. Extracts table captions
2. Links table references
3. Regenerates agent chunks (includes "table" chunks)
4. Updates asset registry

## 9. Re-embedding Table Chunks

```bash
python -m scientra.pdf_data_assets.build_assets --quality-check
python -m scientra.pdf_data_assets.asset_embedding --all --force
```

Table chunks are embedded into the `pdf_asset_chunks` LanceDB table alongside other chunk types.

## 10. Querying Tables via API

```python
from scientra.sdk import query_assets

# Query for table chunks
results = query_assets(
    query="LC50 toxicity",
    chunk_types=["table"],
    top_k=10
)

# Query with table type filter
results = query_assets(
    query="expression yield",
    chunk_types=["table", "figure"],
    top_k=10
)
```

The `/query/assets` API endpoint accepts `chunk_types: ["table"]`.

## 11. Future: Phase 2B — Simple Table Structure Extraction

Phase 2B will add:
- Simple table row/column structure extraction for well-formatted tables
- Header row detection
- Basic cell content extraction
- `structure_status` transitions from `caption_only` to `simple_structure_extracted`
- Still no OCR, no LLM, no complex multi-level header parsing

Complex tables (merged cells, multi-level headers, footnotes in body) will be marked `complex_structure_skipped`.
