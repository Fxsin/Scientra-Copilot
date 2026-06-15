# Research Agent Guide

The Graph-Augmented Research Agent (P5.4) answers questions using the full P4/P5 pipeline.

## Modes

| Mode | API Key | Behavior |
|------|---------|----------|
| `evidence_only` | Not required | Deterministic answers from evidence |
| `llm_synthesis` | Required | LLM-synthesized answers grounded in evidence |
| `auto` | Optional | Tries LLM, falls back to evidence_only |

## Tools Used

The agent can call 8 tools:
- `cross_asset_query` — Search across evidence, figures, tables, supplementary
- `unified_graph_query` — Query the evidence graph
- `dataset_query` — Search datasets by type or entity
- `dataset_entity_compare` — Compare entities across papers
- `evidence_search` — Search evidence chunks
- `gap_search` — Search research gaps
- `hypothesis_search` — Search hypotheses
- `opportunity_search` — Search research opportunities

## Example Queries

```bash
python Scripts/ask_research_agent.py --query "MAP2K4 expression" --mode evidence_only
python Scripts/ask_research_agent.py --query "Which claims are weakly supported?" --mode evidence_only
python Scripts/ask_research_agent.py --query "Generate a research plan for receptor mechanism" --mode auto
```

## Response Structure

- `answer` — The agent's answer
- `evidence_references` — Cited sources with paper_id and relative paths
- `evidence_chains` — Claim→Evidence→Asset chains
- `used_tools` — Which tools were called and their status
- `warnings` — Any issues or limitations
- `confidence` — Overall confidence score (0-1)

## Guardrails

- No unsupported claims — all answers grounded in evidence
- No API key in traces — safe to share trace logs
- No absolute paths — all source paths are relative
- Overclaim detection — strong language without evidence triggers warnings

## Limitations

- Evidence_only mode provides factual summaries, not creative analysis
- LLM mode requires API key and `figure_interpretation: true` in config
- Agent does not have multi-turn conversation memory
- Research plans are template-based in evidence_only mode
