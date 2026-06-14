"""Hypothesis Generation — AI-powered testable hypothesis formulation (Phase 2.3).

Uses identified gaps, Summary V2 findings, and evidence enrichment to generate
structured, testable hypotheses with suggested experiments.

Output: 03_Assets/ai/hypotheses/{paper_id}.json
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
OUTPUT_DIR = PROJECT_ROOT / "03_Assets" / "ai" / "hypotheses"

DEFAULT_MAX_HYPOTHESES = 8


def _load_prompt_template() -> str:
    path = PROMPT_DIR / "hypothesis_generation.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _extract_json_from_response(text: str) -> dict[str, Any] | None:
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


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _make_slim(data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Extract only specified fields to reduce token usage."""
    return {k: data.get(k) for k in fields if k in data}


def _render_prompt(
    paper_id: str,
    gaps: dict[str, Any] | None,
    summary_v2: dict[str, Any] | None,
    evidence_enrichment: dict[str, Any] | None,
    max_hypotheses: int = DEFAULT_MAX_HYPOTHESES,
) -> str:
    template = _load_prompt_template()

    sv2 = summary_v2 or {}
    g = gaps or {}

    replacements = {
        "{{paper_id}}": paper_id,
        "{{title}}": str(sv2.get("title", "")),
        "{{authors}}": str(sv2.get("authors", "")),
        "{{year}}": str(sv2.get("year", "")),
        "{{max_hypotheses}}": str(max_hypotheses),
        "{{summary_v2_slim}}": json.dumps(
            _make_slim(sv2, ["core_finding", "key_evidence", "main_claims", "limitations"]),
            ensure_ascii=False, indent=2,
        ) if sv2 else "Not available.",
        "{{gaps}}": json.dumps(g.get("gaps", []), ensure_ascii=False, indent=2) if g else "Not available.",
    }
    for key, value in replacements.items():
        template = template.replace(key, value)

    # Evidence enrichment slim block
    ee = evidence_enrichment or {}
    if ee and ee.get("chunks"):
        slim_chunks = []
        for c in ee.get("chunks", [])[:12]:
            slim_chunks.append(_make_slim(c, ["chunk_id", "ai_claim", "ai_finding", "evidence_strength", "entity_mentioned"]))
        ee_json = json.dumps({"chunks": slim_chunks}, ensure_ascii=False, indent=2)
        template = re.sub(
            r'\{% if evidence_enrichment_slim %\}.*?\{% endif %\}',
            f"### Evidence Enrichment (key claims only)\n```json\n{ee_json[:6000]}\n```",
            template, flags=re.DOTALL,
        )
    else:
        template = re.sub(
            r'\{% if evidence_enrichment_slim %\}.*?\{% endif %\}',
            "", template, flags=re.DOTALL,
        )

    return template


def generate_hypotheses(
    paper_id: str,
    gaps_path: str | None = None,
    summary_v2_path: str | None = None,
    evidence_enrichment_path: str | None = None,
    config: dict[str, Any] | None = None,
    max_hypotheses: int = DEFAULT_MAX_HYPOTHESES,
) -> dict[str, Any]:
    """Generate testable hypotheses from identified research gaps.

    Args:
        paper_id: Paper identifier.
        gaps_path: Path to gaps JSON. Auto-detected if None.
        summary_v2_path: Path to summary V2 JSON. Auto-detected if None.
        evidence_enrichment_path: Path to evidence enrichment JSON. Auto-detected if None.
        config: Optional override config.
        max_hypotheses: Maximum hypotheses to generate.

    Returns:
        dict with hypotheses list and metadata.
    """
    try:
        from scientra.ai import call_llm, get_config
    except ImportError:
        return _fallback(paper_id, "AI module not importable")

    llm_config = get_config()

    if not llm_config.is_task_enabled("hypothesis_generation"):
        return {
            "paper_id": paper_id,
            "status": "skipped",
            "reason": "hypothesis_generation task is disabled in llm_config.yaml",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Load inputs
    gaps = _load_json_file(
        PROJECT_ROOT / "03_Assets" / "ai" / "gaps" / f"{paper_id}.json"
    )
    summary_v2 = _load_json_file(
        PROJECT_ROOT / "03_Assets" / "ai" / "summary_v2" / f"{paper_id}.json"
    )
    evidence_enrichment = _load_json_file(
        PROJECT_ROOT / "03_Assets" / "ai" / "evidence_enrichment" / f"{paper_id}.json"
    )

    if not summary_v2:
        return _fallback(paper_id, "Summary V2 not available — run ai_summary_v2 first.")

    if not gaps or not gaps.get("gaps"):
        return {
            "paper_id": paper_id,
            "status": "no_gaps",
            "hypotheses": [],
            "warnings": ["No research gaps available — run ai_gap_extraction first."],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Render prompt
    prompt = _render_prompt(paper_id, gaps, summary_v2, evidence_enrichment, max_hypotheses)

    # Call LLM
    response = call_llm(
        prompt=prompt,
        task_name="hypothesis_generation",
        temperature=0.3,  # Slightly higher for creative hypothesis generation
        max_tokens=4096,
        paper_id=paper_id,
    )

    if not response.success:
        fb = _fallback(paper_id, f"LLM call failed: {response.error}")
        _save_output(paper_id, fb)
        return fb

    parsed = _extract_json_from_response(response.text)
    if parsed is None:
        fb = _fallback(paper_id, "Failed to parse LLM response as JSON")
        _save_output(paper_id, fb)
        return fb

    result = {
        "paper_id": paper_id,
        "status": "generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypotheses": parsed.get("hypotheses", []),
        "warnings": parsed.get("warnings", []),
        "model": response.model,
        "provider": response.provider,
        "usage": {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "cost_estimate": response.cost_estimate,
        },
    }

    _save_output(paper_id, result)
    return result


def _fallback(paper_id: str, error: str) -> dict[str, Any]:
    return {
        "paper_id": paper_id,
        "status": "fallback",
        "hypotheses": [],
        "warnings": [error],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_output(paper_id: str, data: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (OUTPUT_DIR / f"{paper_id}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    except Exception:
        pass


def load_hypotheses(paper_id: str) -> dict[str, Any] | None:
    path = OUTPUT_DIR / f"{paper_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
