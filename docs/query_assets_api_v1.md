# POST /query/assets API — Phase 0.8

## Purpose

Search the `pdf_asset_chunks` LanceDB table directly. Returns structured,
provenance-complete asset chunks with quality scores and evidence traceability.

## Difference from `/query/evidence`

| Aspect | `/query/evidence` | `/query/assets` |
|---|---|---|
| Source | `evidence_chunks` table | `pdf_asset_chunks` table |
| Quality filter | None | `min_quality_score` (default 0) |
| Chunk types | level-based | section / method / result / claim |
| Provenance | chunk_id → evidence field | chunk → asset → evidence (3-level) |
| Entity enrichment | No | Planned (entities field reserved) |
| Paper filter | Via filters | `paper_id` parameter |
| Citation key | No | `[A:paper_id:chunk_id]` format |

Both endpoints coexist. Neither replaces the other.

## Request

```
POST /query/assets
Content-Type: application/json
```

```json
{
  "query": "protein expression conditions",
  "top_k": 10,
  "chunk_types": ["method", "result"],
  "paper_id": null,
  "min_quality_score": 70,
  "include_metadata": true
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | Yes | — | Search query text (min 1 char) |
| `top_k` | int | No | 10 | Max results (1–50) |
| `chunk_types` | string[] | No | null (all) | Filter: section, method, result, claim |
| `paper_id` | string | No | null | Limit to single paper |
| `min_quality_score` | float | No | 0.0 | Minimum quality_score (0–100) |
| `include_metadata` | bool | No | true | Include paper metadata |

## Response

```json
{
  "query": "protein expression conditions",
  "results": [
    {
      "chunk_id": "paper_id:chunk:0004",
      "paper_id": "paper_id",
      "chunk_type": "method",
      "text": "Method: expression\n...",
      "score": 0.8912,
      "linked_evidence_id": "paper_id:methods:4",
      "linked_evidence_ids": ["paper_id:methods:4"],
      "source_asset_ids": ["paper_id:method:0004"],
      "entities": [],
      "linked_claims": [],
      "linked_methods": [],
      "confidence": "medium",
      "quality_score": 98.0,
      "citation_key": "[A:paper_id:paper_id:chunk:0004]",
      "metadata": {
        "paper_title": "...",
        "paper_year": 2023
      }
    }
  ],
  "count": 10,
  "unique_papers": 5,
  "warnings": [],
  "elapsed_ms": 123.4
}
```

## Citation Key Format

```
[A:{paper_id}:{chunk_id}]
```

The `[A:...]` prefix distinguishes asset citations from evidence citations `[E:...]` and reference citations `[Ref:N]`.

## SDK Usage

```python
from scientra.sdk import query_assets

results = query_assets(
    query="Vip3Aa binding receptor",
    top_k=10,
    chunk_types=["method", "result"],
    min_quality_score=70,
)
for r in results["results"]:
    print(f"[{r['chunk_type']}] {r['text'][:100]}...")
    print(f"  Score: {r['score']}, Quality: {r['quality_score']}")
    print(f"  Evidence: {r['linked_evidence_id']}")
```

## Web Chat Integration (Phase 0.9)

The `/query/assets` endpoint is designed for evidence card display:

1. User asks question → POST /v1/agent/ask with `return_context=true`
2. Each context chunk is an asset with `citation_key`
3. Frontend renders `[A:paper_id:chunk_id]` as clickable evidence cards
4. Clicking a card shows: text, paper title, year, chunk_type, quality_score, linked_evidence_id

## Errors

| Condition | Status | Response |
|---|---|---|
| Empty query | 422 | Validation error |
| Invalid chunk_types | 400 | `"Invalid chunk_types: [...]"` |
| pdf_asset_chunks table missing | 200 | `results: [], warnings: ["pdf_asset_chunks not found"]` |
