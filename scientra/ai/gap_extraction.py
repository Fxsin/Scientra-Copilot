"""Gap Extraction — AI-powered research gap identification (Phase 2.3).

Analyzes Summary V2 and Evidence Enrichment outputs to identify
structured knowledge gaps across 7 gap types.

Output: 03_Assets/ai/gaps/{paper_id}.json
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
OUTPUT_DIR = PROJECT_ROOT / "03_Assets" / "ai" / "gaps"

DEFAULT_MAX_GAPS = 8


def _load_prompt_template() -> str:
    path = PROMPT_DIR / "gap_extraction.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


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


def _load_summary_v2(paper_id: str) -> dict[str, Any] | None:
    """Load Summary V2 output if available."""
    path = PROJECT_ROOT / "03_Assets" / "ai" / "summary_v2" / f"{paper_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_evidence_enrichment(paper_id: str) -> dict[str, Any] | None:
    """Load evidence enrichment output if available."""
    path = PROJECT_ROOT / "03_Assets" / "ai" / "evidence_enrichment" / f"{paper_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _render_prompt(
    paper_id: str,
    summary_v2: dict[str, Any] | None,
    evidence_enrichment: dict[str, Any] | None,
    max_gaps: int = DEFAULT_MAX_GAPS,
) -> str:
    """Render the gap extraction prompt."""
    template = _load_prompt_template()

    sv2 = summary_v2 or {}
    ee = evidence_enrichment or {}

    replacements = {
        "{{paper_id}}": paper_id,
        "{{title}}": str(sv2.get("title", "")),
        "{{authors}}": str(sv2.get("authors", "")),
        "{{year}}": str(sv2.get("year", "")),
        "{{max_gaps}}": str(max_gaps),
        "{{summary_v2}}": json.dumps(sv2, ensure_ascii=False, indent=2) if sv2 else "Not available.",
    }
    for key, value in replacements.items():
        template = template.replace(key, value)

    # Evidence enrichment block
    if ee:
        ee_json = json.dumps(ee, ensure_ascii=False, indent=2)
        template = re.sub(
            r'\{% if evidence_enrichment %\}.*?\{% endif %\}',
            f"### Evidence Enrichment\n```json\n{ee_json[:8000]}\n```",
            template, flags=re.DOTALL,
        )
    else:
        template = re.sub(
            r'\{% if evidence_enrichment %\}.*?\{% endif %\}',
            "", template, flags=re.DOTALL,
        )

    return template


def extract_research_gaps(
    paper_id: str,
    summary_v2_path: str | None = None,
    evidence_enrichment_path: str | None = None,
    config: dict[str, Any] | None = None,
    max_gaps: int = DEFAULT_MAX_GAPS,
) -> dict[str, Any]:
    """Extract structured research gaps from paper analysis.

    Args:
        paper_id: Paper identifier.
        summary_v2_path: Path to summary V2 JSON. Auto-detected if None.
        evidence_enrichment_path: Path to evidence enrichment JSON. Auto-detected if None.
        config: Optional override config.
        max_gaps: Maximum number of gaps to extract.

    Returns:
        dict with gaps list and metadata. On failure, returns fallback.
    """
    try:
        from scientra.ai import call_llm, get_config
    except ImportError:
        return _fallback(paper_id, "AI module not importable")

    llm_config = get_config()

    # Task gate
    if not llm_config.is_task_enabled("gap_extraction"):
        return {
            "paper_id": paper_id,
            "status": "skipped",
            "reason": "gap_extraction task is disabled in llm_config.yaml",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Load inputs
    summary_v2 = _load_summary_v2(paper_id)
    evidence_enrichment = _load_evidence_enrichment(paper_id)

    if not summary_v2:
        return _fallback(paper_id, "Summary V2 not available — run ai_summary_v2 first.")

    # Render prompt
    prompt = _render_prompt(paper_id, summary_v2, evidence_enrichment, max_gaps)

    # Call LLM
    response = call_llm(
        prompt=prompt,
        task_name="gap_extraction",
        temperature=0.2,
        max_tokens=4096,
        paper_id=paper_id,
    )

    if not response.success:
        fb = _fallback(paper_id, f"LLM call failed: {response.error}")
        _save_output(paper_id, fb)
        return fb

    # Parse response
    parsed = _extract_json_from_response(response.text)
    if parsed is None:
        fb = _fallback(paper_id, "Failed to parse LLM response as JSON")
        _save_output(paper_id, fb)
        return fb

    result = {
        "paper_id": paper_id,
        "status": "generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gaps": parsed.get("gaps", []),
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
        "gaps": [],
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


def load_gaps(paper_id: str) -> dict[str, Any] | None:
    path = OUTPUT_DIR / f"{paper_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
