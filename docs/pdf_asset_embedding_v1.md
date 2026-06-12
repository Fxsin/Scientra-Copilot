# PDF Asset Embedding V1 — Phase 0.6

**Version:** 1.0
**Date:** 2026-06-12
**Status:** Phase 0.6 Implemented

---

## 1. Why `pdf_asset_chunks`?

The existing `evidence_chunks` table in LanceDB contains flat text chunks derived
directly from `03_Evidence/evidence.json`. These chunks are useful for keyword and
semantic search but lack the structured provenance that agents need for
evidence-grounded answers.

`pdf_asset_chunks` is a **higher-quality** vector table where each chunk:

- Has been quality-checked (score >= 70)
- Is marked `vector_ready` after validation
- Carries full provenance: `linked_evidence_id`, `linked_evidence_ids`, `source_asset_ids`
- Is linked to its source section, method, result, or claim
- Includes entity tags and quality notes

This enables **Scientra Literature Agent V1** to retrieve not just "similar text"
but **traceable, evidence-backed knowledge fragments**.

## 2. Difference from `evidence_chunks`

| Aspect | `evidence_chunks` | `pdf_asset_chunks` |
|---|---|---|
| **Source** | Raw evidence.json fields | Quality-checked agent_chunks |
| **Quality filtering** | None | score >= 70, vector_ready=true |
| **Provenance** | chunk_id → evidence field | chunk → asset → evidence (3-level traceability) |
| **Entity enrichment** | No | Yes |
| **Citation readiness** | Not guaranteed | `citation_ready` flag |
| **Claim links** | No | `linked_claims` |
| **Method links** | No | `linked_methods` |
| **Maintained by** | `evidence_embedding.py` | `asset_embedding.py` |

Both tables coexist. Neither replaces the other.

## 3. Data Source

```
03_Evidence/evidence.json
    → (asset builders)
        → 06_PDF_DataAssets/09_agent_chunks/{paper_id}/agent_chunks.jsonl
            → (quality check)
                → agent_chunks.quality.jsonl
                    → (asset_embedding.py)
                        → 04_VectorDB/lancedb → table: pdf_asset_chunks
```

## 4. LanceDB Table Schema

Table: `pdf_asset_chunks`

| Column | Type | Description |
|---|---|---|
| `chunk_id` | string | Unique chunk identifier (PK) |
| `paper_id` | string | Source paper ID |
| `chunk_type` | string | section / method / result / claim |
| `text` | string | Chunk content (embedded) |
| `linked_evidence_id` | string | Primary 03_Evidence cross-reference |
| `confidence` | string | high / medium / low / unknown |
| `vector_ready` | bool | Passed quality validation |
| `vector` | float[1024] | BGE-M3 embedding |
| `metadata_json` | string | JSON with source_asset_ids, linked_evidence_ids, entities, linked_claims, linked_methods, quality_score, quality_notes |
| `embedding_model` | string | `BAAI/bge-m3` |
| `embedding_version` | string | `0.1.0` |
| `indexed_at` | string | ISO 8601 timestamp |

## 5. Usage

```bash
# Check status
python -m scientra.pdf_data_assets.asset_embedding --status

# Embed one paper
python -m scientra.pdf_data_assets.asset_embedding --paper-id "Bacillus_thuringiensis..."

# Embed all papers
python -m scientra.pdf_data_assets.asset_embedding --all

# Force re-embed (overwrite)
python -m scientra.pdf_data_assets.asset_embedding --all --force
```

## 6. Status File

Status is saved to `06_PDF_DataAssets/00_registry/asset_embedding_status.json`:

```json
{
  "last_run_time": "2026-06-12T...",
  "table_name": "pdf_asset_chunks",
  "table_exists": true,
  "embedded_chunk_count": 46,
  "available_papers": 1,
  "available_chunks": 46,
  "vector_ready_chunks": 46,
  "embedding_model": "BAAI/bge-m3",
  "vector_dimension": 1024
}
```

## 7. Agent Integration (Future)

### Reserved API: `POST /query/assets`

**Input:**
```json
{
  "query": "protein expression conditions",
  "chunk_types": ["method", "result", "claim"],
  "top_k": 10,
  "min_quality_score": 70
}
```

**Output:**
```json
{
  "results": [
    {
      "chunk_id": "paper_id:chunk:0004",
      "paper_id": "paper_id",
      "chunk_type": "method",
      "text": "Method: expression\n...",
      "linked_evidence_id": "paper_id:methods:4",
      "source_asset_ids": ["paper_id:method:0004"],
      "score": 0.89
    }
  ],
  "total": 10
}
```

### Agent SDK pattern:
```python
# Future: Scientra Literature Agent V1
from scientra.pdf_data_assets.asset_embedding import AssetEmbeddingEngine

engine = AssetEmbeddingEngine()
# Retrieve context for agent prompt
results = engine.search("Vip3Aa mechanism of action", top_k=5, chunk_types=["method", "result"])
for r in results:
    print(f"[{r.chunk_type}] {r.text[:100]}...")
    print(f"  Evidence: {r.linked_evidence_id}")
```

## 8. Why Not Modify `/query/evidence` Now?

- `GET /query/evidence` serves the existing web UI and Agent SDK
- Adding `pdf_asset_chunks` search requires schema alignment, scoring harmonization, and API versioning
- Phase 0.6 focuses on **writing** the table and verifying data quality
- A separate `POST /query/assets` endpoint (Phase 1+) will provide asset-native search without disrupting existing consumers

## 9. Model Reuse

This module reuses `BgeM3Embedder` from `scientra/embedding.py`:

- Same model: `BAAI/bge-m3`
- Same dimension: 1024
- Same device: auto (from `Config/embedding.yaml`)
- No additional model loading or configuration needed

If the embedder is unavailable, the module raises a clear error:
```
Cannot import BgeM3Embedder from scientra.embedding.
Ensure the project embedding environment is configured.
```
