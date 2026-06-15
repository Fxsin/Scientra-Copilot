# API Reference

Base: `http://127.0.0.1:8710`

## Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | API health + LanceDB status |
| `/papers` | GET | Paginated paper list |
| `/papers/registry` | GET | Paper registry summary |
| `/papers/lookup` | GET | Search papers |

## Evidence & Query

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query/assets` | POST | Search PDF asset chunks |
| `/query/evidence` | POST | Search evidence chunks |
| `/query/cross-assets` | POST | Cross-asset search (P5.2) |
| `/query/supplementary-entities` | POST | Search supplementary entities |

## Paper Detail

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/paper/{id}/metadata` | GET | Paper metadata |
| `/paper/{id}/evidence` | GET | Evidence data |
| `/paper/{id}/assets` | GET | Registered assets |
| `/paper/{id}/asset-links` | GET | Asset citation links |
| `/paper/{id}/figures` | GET | Figure intelligence |
| `/paper/{id}/figure-cards` | GET | Figure cards |
| `/paper/{id}/figure/{figure_id}` | GET | Single figure |
| `/paper/{id}/tables` | GET | Table intelligence |
| `/paper/{id}/table-cards` | GET | Table cards |
| `/paper/{id}/table/{table_id}` | GET | Single table |
| `/paper/{id}/supplementaries` | GET | Supplementary intelligence |
| `/paper/{id}/datasets` | GET | Dataset intelligence |
| `/paper/{id}/dataset/{dataset_id}` | GET | Single dataset |

## Knowledge Graph

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/knowledge-network` | GET | Research map network |
| `/knowledge/unified-evidence-graph` | GET | Unified graph nodes/edges |
| `/knowledge/unified-evidence-graph/stats` | GET | Graph statistics |
| `/knowledge/unified-evidence-graph/paper/{paper_id}` | GET | Paper subgraph |
| `/knowledge/unified-evidence-graph/neighborhood/{node_id}` | GET | Node neighborhood |

## Dataset Intelligence

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/datasets` | GET | All dataset cards |
| `/datasets/search` | GET | Search by entity/type |
| `/datasets/entity/{entity_text}` | GET | Entity comparison |
| `/datasets/type/{dataset_type}` | GET | Filter by type |
| `/datasets/status` | GET | Dataset type distribution |

## Research Agent

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/research-agent/ask` | POST | Ask research agent |
| `/v1/research-agent/status` | GET | Agent capabilities |
| `/v1/research-agent/trace/{trace_id}` | GET | Execution trace |

## Validation & Quality

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/validation/e2e/status` | GET | E2E validation status |
| `/quality-dashboard/summary` |GET | Quality dashboard |
| `/quality-dashboard/papers` |GET | Paper quality table |
| `/quality-dashboard/recommendations`|GET | P0-P3 recommendations |

## Demo

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/demo/status` | GET | Demo project status |
| `/demo/queries` | GET | Demo query results |

> Empty states: all endpoints return `{"available": false, "message": "..."}` instead of 500.
