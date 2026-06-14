"""Summary V2 — Enhanced structured summary using LLM Gateway (Phase 2.2).

Generates a JSON-structured summary with evidence-driven claims,
method analysis, and confidence scoring.

Output: 03_Assets/ai/summary_v2/{paper_id}.json
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
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
OUTPUT_DIR = PROJECT_ROOT / "03_Assets" / "ai" / "summary_v2"


def _load_prompt_template() -> str:
    """Load the summary_v2.md prompt template."""
    prompt_path = PROMPT_DIR / "summary_v2.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


def _render_prompt(
    paper_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    evidence_chunks: list[dict[str, Any]] | None = None,
) -> str:
    """Render the prompt template with paper data."""
    template = _load_prompt_template()
    meta = metadata or {}

    # Simple Jinja-style variable substitution
    replacements = {
        "{{paper_id}}": paper_id,
        "{{title}}": str(meta.get("title", "")),
        "{{authors}}": str(meta.get("authors", meta.get("author", ""))),
        "{{year}}": str(meta.get("year", "")),
        "{{doi}}": str(meta.get("doi", "")),
        "{{paper_text}}": text[:24000],  # Truncate long text for token limits
    }
    for key, value in replacements.items():
        template = template.replace(key, value)

    # Handle evidence chunks section
    if evidence_chunks and len(evidence_chunks) > 0:
        chunks_text = ""
        for i, chunk in enumerate(evidence_chunks[:40]):  # Max 40 chunks
            chunks_text += (
                f"[{chunk.get('chunk_id', f'C{i}')}] "
                f"({chunk.get('chunk_type', 'unknown')}, "
                f"confidence: {chunk.get('confidence', 'medium')})\n"
                f"{chunk.get('text', '')}\n\n"
            )
        # Replace the Jinja block
        template = re.sub(
            r'\{% if evidence_chunks %\}.*?\{% endif %\}',
            f"## Available Evidence Chunks\n\n{chunks_text}",
            template,
            flags=re.DOTALL,
        )
    else:
        template = re.sub(
            r'\{% if evidence_chunks %\}.*?\{% endif %\}',
            "",
            template,
            flags=re.DOTALL,
        )

    return template


def _extract_json_from_response(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response text, with multiple repair strategies."""
    # Strategy 1: Direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find outermost JSON object
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


def _build_fallback_summary_v2(
    paper_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal fallback summary when LLM parsing fails."""
    meta = metadata or {}
    return {
        "paper_id": paper_id,
        "title": meta.get("title", ""),
        "research_question": "",
        "core_finding": meta.get("abstract", "")[:500] if meta.get("abstract") else "",
        "method_summary": [],
        "key_evidence": [],
        "main_claims": [],
        "limitations": [],
        "future_directions": [],
        "important_entities": [],
        "confidence": 0.0,
        "warnings": ["Summary V2 generation failed — fallback to metadata only."],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "fallback",
    }


def generate_summary_v2(
    paper_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    evidence_chunks: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate an enhanced V2 summary for a paper.

    Args:
        paper_id: Paper identifier.
        text: Full paper text (or hybrid markdown).
        metadata: Optional metadata dict (title, authors, year, doi).
        evidence_chunks: Optional list of evidence chunk dicts.
        config: Optional override config dict.

    Returns:
        dict with structured summary fields. On failure, returns fallback.
    """
    try:
        from scientra.ai import call_llm, get_config
    except ImportError:
        return _build_fallback_summary_v2(paper_id, metadata)

    # Check if task is enabled
    llm_config = get_config()
    if not llm_config.is_task_enabled("summary"):
        return {
            "paper_id": paper_id,
            "status": "skipped",
            "reason": "Summary task is disabled in llm_config.yaml",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Render prompt
    prompt = _render_prompt(
        paper_id=paper_id,
        text=text,
        metadata=metadata,
        evidence_chunks=evidence_chunks,
    )

    # Call LLM
    response = call_llm(
        prompt=prompt,
        task_name="summary",
        temperature=0.2,
        max_tokens=4096,
        paper_id=paper_id,
    )

    if not response.success:
        fallback = _build_fallback_summary_v2(paper_id, metadata)
        fallback["warnings"].append(f"LLM call failed: {response.error}")
        _save_output(paper_id, fallback)
        return fallback

    # Parse response
    parsed = _extract_json_from_response(response.text)

    if parsed is None:
        fallback = _build_fallback_summary_v2(paper_id, metadata)
        fallback["warnings"].append("Failed to parse LLM response as JSON")
        fallback["raw_response_snippet"] = response.text[:500]
        _save_output(paper_id, fallback)
        return fallback

    # Enrich with metadata
    result = {
        **parsed,
        "paper_id": paper_id,
        "title": (metadata or {}).get("title", parsed.get("title", "")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "generated",
        "model": response.model,
        "provider": response.provider,
        "usage": {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "cost_estimate": response.cost_estimate,
        },
    }

    # Save output
    _save_output(paper_id, result)
    return result


def _save_output(paper_id: str, data: dict[str, Any]) -> None:
    """Save summary V2 output to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{paper_id}.json"
    try:
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_summary_v2(paper_id: str) -> dict[str, Any] | None:
    """Load a previously generated summary V2."""
    output_path = OUTPUT_DIR / f"{paper_id}.json"
    if not output_path.exists():
        return None
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return None
