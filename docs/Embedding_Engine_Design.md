# Embedding Engine Design

## Purpose

Embedding Engine is the P6 retrieval-layer builder for scientra. It converts validated literature knowledge layers into three embedding input layers:

1. Metadata
2. Summary
3. Raw-text chunks

PDFs are not embedded directly. PDFs remain data sources. The engine consumes parsed metadata, calibrated tags, generated summaries, and GROBID raw text.

## Safety Boundary

P6 dry-run is a no-write validation stage.

- Does not call DeepSeek.
- Does not regenerate summaries.
- Does not reparse PDFs.
- Does not rerun Tag Engine.
- Does not load BGE-M3.
- Does not generate vectors.
- Does not create LanceDB.
- Does not write LanceDB.
- Does not enter Query API.

## Configuration

Config path: `Config/embedding.yaml`

```yaml
embedding_model: "BAAI/bge-m3"
embedding_dimension: 1024
device: "auto"

chunking:
  chunk_size: 800
  chunk_overlap: 150
  min_chunk_size: 200

lancedb:
  path: "04_VectorDB/lancedb"
  tables:
    metadata: "metadata_embeddings"
    summary: "summary_embeddings"
    chunks: "chunk_embeddings"

tags:
  use_assigned_tags_only: true
  include_candidate_tags: false
```

## Input Contract

For each paper, the dry-run expects:

- `02_Metadata/<paper_key>/metadata.yaml`
- `02_Metadata/<paper_key>/tags.yaml`
- `03_Summary/<paper_key>/summary.md`
- `03_Summary/raw_text/<paper_key>_*.txt`

Only `assigned_tags` enter formal filter metadata. `candidate_tags` are retained in reports for review but excluded from filter fields and real-run payload planning.

## Three-Layer Records

Metadata layer:

- title
- DOI
- year
- journal
- authors
- abstract
- assigned tags

Summary layer:

- complete `summary.md`
- requires `# Citation Anchors`
- must contain source anchors such as `S001`

Chunk layer:

- generated from GROBID raw text
- chunk size and overlap controlled by `Config/embedding.yaml`
- chunk IDs are deterministic:
  - `paper_id`
  - source name
  - chunk index
  - text hash prefix

## Dry-Run Checks

Each paper is checked for:

- metadata existence
- tags existence
- summary existence
- raw text existence
- assigned tags existence
- candidate tags excluded from formal filters
- Citation Anchors in summary
- raw text chunkability
- stable chunk IDs
- metadata embedding text readiness
- summary embedding text readiness

## LanceDB Plan

Dry-run creates only a write plan. It does not connect to LanceDB.

Planned tables:

- `metadata_embeddings`
- `summary_embeddings`
- `chunk_embeddings`

## CLI

```bash
python Scripts/build_embeddings.py --dry-run --batch batch_5
```

Report:

```text
05_Index/embedding_dry_run_report.md
```

## Real-Run Gate

P6 real-run is allowed only when:

- all dry-run papers pass
- assigned tags are accepted as formal filters
- candidate tags remain excluded
- summary citation anchors pass
- chunk IDs are stable
- no input layer is missing

In real-run, BGE-M3 may be loaded and LanceDB may be written only after the dry-run report is accepted.
