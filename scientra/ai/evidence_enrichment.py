"""Evidence Enrichment — AI-enhanced evidence chunk analysis (Phase 2.2).

Processes evidence chunks in batches, enriching each with:
- ai_claim / ai_finding
- method_mentioned / entity_mentioned
- supports_claim / evidence_strength
- limitations / confidence / warnings

Output: 03_Assets/ai/evidence_enrichment/{paper_id}.json
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _detect_project_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "Config" / "llm_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
OUTPUT_DIR = PROJECT_ROOT / "03_Assets" / "ai" / "evidence_enrichment"

DEFAULT_BATCH_SIZE = 8
DEFAULT_MAX_CHUNKS = 40
DEFAULT_MIN_CHUNK_LENGTH = 80


def _build_batch_prompt(chunks: list[dict[str, Any]], batch_index: int) -> str:
    """Build a prompt for enriching a batch of evidence chunks."""
    chunks_json = []
    for chunk in chunks:
        chunks_json.append({
            "chunk_id": chunk.get("chunk_id", ""),
            "text": chunk.get("text", ""),
            "chunk_type": chunk.get("chunk_type", ""),
            "source_section": chunk.get("source_section", ""),
            "confidence": chunk.get("confidence", "medium"),
        })

    prompt = f"""You are a research scientist analyzing evidence chunks from an academic paper.

For each chunk below, analyze and enrich with the following fields:
- ai_claim: The scientific claim being made (if any)
- ai_finding: The specific finding or observation
- method_mentioned: List of methods/techniques mentioned
- entity_mentioned: List of key entities (genes, proteins, species, compounds, etc.) mentioned
- supports_claim: true/false/null — does this chunk provide evidence for a claim? null if unclear
- evidence_strength: "strong" | "moderate" | "weak" | "unknown"
- limitations: Any limitations or caveats in this chunk
- confidence: 0.0-1.0 confidence in the enrichment quality
- warnings: Any concerns about this chunk

## Chunks Batch {batch_index}

```json
{json.dumps(chunks_json, ensure_ascii=False, indent=2)}
```

## Output Format

Return ONLY a JSON object with an "enriched_chunks" array:

```json
{{
  "enriched_chunks": [
    {{
      "chunk_id": "original_id",
      "ai_claim": "The claim made",
      "ai_finding": "The finding described",
      "method_mentioned": ["method1", "method2"],
      "entity_mentioned": ["entity1", "entity2"],
      "supports_claim": true,
      "evidence_strength": "moderate",
      "limitations": [],
      "confidence": 0.85,
      "warnings": []
    }}
  ]
}}
```

## Rules
- Do NOT invent information not present in the chunk text.
- If a chunk is purely methodological (e.g., "We used TEM"), ai_claim may be empty.
- method_mentioned and entity_mentioned should be specific names, not general terms.
- supports_claim: true if it provides supporting evidence; false if it contradicts; null if purely descriptive.
- evidence_strength: based on specificity, quantification, and directness.
- Return ONLY the JSON. No markdown. No prose."""

    return prompt


def _extract_json_from_response(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response with repair strategies."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break

    return None


def enrich_evidence_chunks(
    paper_id: str,
    chunks_path: str | None = None,
    config: dict[str, Any] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    min_chunk_length: int = DEFAULT_MIN_CHUNK_LENGTH,
) -> dict[str, Any]:
    """Enrich evidence chunks with AI analysis.

    Args:
        paper_id: Paper identifier.
        chunks_path: Path to evidence_chunks.json. Auto-detected if None.
        config: Optional override config dict.
        batch_size: Chunks per LLM call (5-10 recommended).
        max_chunks: Maximum chunks to process per paper.
        min_chunk_length: Skip chunks shorter than this.

    Returns:
        dict with enriched_chunks list and metadata.
    """
    try:
        from scientra.ai import call_llm, get_config
    except ImportError:
        return {
            "paper_id": paper_id,
            "status": "failed",
            "error": "AI module not importable",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    llm_config = get_config()

    # Check task gating
    if not llm_config.is_task_enabled("evidence_enrichment"):
        return {
            "paper_id": paper_id,
            "status": "skipped",
            "reason": "evidence_enrichment task is disabled in llm_config.yaml",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Resolve chunks path
    if chunks_path is None:
        chunks_path = str(
            PROJECT_ROOT / "03_Evidence" / paper_id / "evidence_chunks.json"
        )

    chunks_file = Path(chunks_path)
    if not chunks_file.exists():
        return {
            "paper_id": paper_id,
            "status": "failed",
            "error": f"Chunks file not found: {chunks_path}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Load chunks
    try:
        chunks_data = json.loads(chunks_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "paper_id": paper_id,
            "status": "failed",
            "error": f"Failed to load chunks: {exc}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    all_chunks = chunks_data.get("chunks", [])
    if not isinstance(all_chunks, list):
        all_chunks = []

    # Filter by length and limit
    eligible = [
        c for c in all_chunks
        if isinstance(c, dict) and len(c.get("text", "")) >= min_chunk_length
    ][:max_chunks]

    if not eligible:
        return {
            "paper_id": paper_id,
            "status": "no_eligible_chunks",
            "total_chunks": len(all_chunks),
            "eligible_count": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Process in batches
    enriched_chunks: list[dict[str, Any]] = []
    batch_count = 0
    failed_batches = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0

    for i in range(0, len(eligible), batch_size):
        batch = eligible[i:i + batch_size]
        batch_count += 1

        prompt = _build_batch_prompt(batch, batch_count)
        response = call_llm(
            prompt=prompt,
            task_name="evidence_enrichment",
            temperature=0.15,
            max_tokens=4096,
            paper_id=paper_id,
        )

        if not response.success:
            failed_batches += 1
            # Preserve original chunks with error markers
            for chunk in batch:
                enriched_chunks.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "original_text": chunk.get("text", ""),
                    "section": chunk.get("source_section", ""),
                    "evidence_type": chunk.get("chunk_type", ""),
                    "ai_claim": "",
                    "ai_finding": "",
                    "method_mentioned": [],
                    "entity_mentioned": [],
                    "supports_claim": None,
                    "evidence_strength": "unknown",
                    "limitations": [],
                    "confidence": 0.0,
                    "warnings": [f"Batch failed: {response.error}"],
                })
            continue

        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens
        total_cost += response.cost_estimate

        parsed = _extract_json_from_response(response.text)
        if parsed is None or "enriched_chunks" not in parsed:
            failed_batches += 1
            for chunk in batch:
                enriched_chunks.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "original_text": chunk.get("text", ""),
                    "section": chunk.get("source_section", ""),
                    "evidence_type": chunk.get("chunk_type", ""),
                    "ai_claim": "",
                    "ai_finding": "",
                    "method_mentioned": [],
                    "entity_mentioned": [],
                    "supports_claim": None,
                    "evidence_strength": "unknown",
                    "limitations": [],
                    "confidence": 0.0,
                    "warnings": ["Failed to parse batch response as JSON"],
                })
            continue

        # Merge enriched fields with original chunk data
        for enriched in parsed.get("enriched_chunks", []):
            chunk_id = enriched.get("chunk_id", "")
            # Find original chunk for metadata
            original = next(
                (c for c in batch if c.get("chunk_id") == chunk_id),
                batch[0] if batch else {},
            )
            enriched_chunks.append({
                "chunk_id": chunk_id,
                "original_text": original.get("text", ""),
                "section": original.get("source_section", ""),
                "evidence_type": original.get("chunk_type", ""),
                "ai_claim": enriched.get("ai_claim", ""),
                "ai_finding": enriched.get("ai_finding", ""),
                "method_mentioned": enriched.get("method_mentioned", []),
                "entity_mentioned": enriched.get("entity_mentioned", []),
                "supports_claim": enriched.get("supports_claim"),
                "evidence_strength": enriched.get("evidence_strength", "unknown"),
                "limitations": enriched.get("limitations", []),
                "confidence": enriched.get("confidence", 0.0),
                "warnings": enriched.get("warnings", []),
            })

    # Build output
    result = {
        "paper_id": paper_id,
        "status": "enriched",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": len(all_chunks),
        "eligible_chunks": len(eligible),
        "enriched_chunks": len(enriched_chunks),
        "batch_count": batch_count,
        "failed_batches": failed_batches,
        "model": response.model if batch_count > 0 else "none",
        "provider": response.provider if batch_count > 0 else "none",
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "cost_estimate": round(total_cost, 8),
        },
        "chunks": enriched_chunks,
    }

    # Save
    _save_output(paper_id, result)
    return result


def _save_output(paper_id: str, data: dict[str, Any]) -> None:
    """Save evidence enrichment output to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{paper_id}.json"
    try:
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_evidence_enrichment(paper_id: str) -> dict[str, Any] | None:
    """Load previously generated evidence enrichment."""
    output_path = OUTPUT_DIR / f"{paper_id}.json"
    if not output_path.exists():
        return None
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return None
