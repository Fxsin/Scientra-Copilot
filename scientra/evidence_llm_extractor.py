"""
Section-level LLM Structured Extraction — Optional enhancement for evidence V2.
Requires API key (DEEPSEEK_API_KEY or ANTHROPIC_API_KEY).
Falls back gracefully when unavailable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ENGINE_VERSION = "v2"


def has_api_key() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def extract_section_with_llm(
    section_name: str,
    section_text: str,
    paper_id: str,
) -> dict[str, Any] | None:
    """
    Extract structured fields from a single section using LLM.
    Returns None if LLM is unavailable or fails.
    """
    if not has_api_key():
        return None

    if not section_text or len(section_text.strip()) < 100:
        return None

    try:
        prompt = _build_section_prompt(section_name, section_text)
        result = _call_llm(prompt)
        return _validate_section_result(result, section_name, paper_id)
    except Exception:
        return None


def _build_section_prompt(section_name: str, text: str) -> str:
    text = text[:8000]  # limit input size

    prompts: dict[str, str] = {
        "introduction": f"""Extract from this INTRODUCTION section only explicit statements. Do NOT infer beyond the text. Return valid JSON.

Required JSON structure:
{{
  "research_question": "",
  "study_objective": "",
  "research_gap": "",
  "background_claims": [{{"claim": "", "quote": "", "confidence": "high|medium|low"}}],
  "hypotheses": [{{"hypothesis": "", "quote": "", "confidence": "high|medium|low"}}]
}}

- Return empty string "" if a field is not present.
- Return empty array [] if no items are found.
- Each quote must be <= 240 characters.
- Do NOT include references, citation IDs, JSON, YAML, or markdown artifacts.
- Output valid JSON only.

SECTION TEXT:
{text}""",

        "methods": f"""Extract from this METHODS section only explicit experimental methods. Do NOT infer. Return valid JSON.

Required JSON structure:
{{
  "methods": [{{"name": "", "purpose": "", "evidence_type": "experiment|assay|sequencing|microscopy|structure|modeling|survey|statistical|computational|biochemical|genetic|other", "quote": "", "confidence": "high|medium|low"}}]
}}

- Return [] if no methods are found.
- evidence_type must be one of the listed values.
- Each quote <= 240 characters.
- Output valid JSON only.

SECTION TEXT:
{text}""",

        "results": f"""Extract from this RESULTS section only explicit experimental results. Do NOT infer beyond the text. Return valid JSON.

Required JSON structure:
{{
  "key_results": [{{"result": "", "measured_variable": "", "direction": "increase|decrease|no_change|association|descriptive|unclear", "condition": "", "quote": "", "confidence": "high|medium|low"}}],
  "core_findings": [{{"finding": "", "quote": "", "confidence": "high|medium|low"}}]
}}

- Return [] if no results are found.
- Each quote <= 240 characters.
- Output valid JSON only.

SECTION TEXT:
{text}""",

        "discussion": f"""Extract from this DISCUSSION section only explicit interpretations, limitations, and future directions. Do NOT infer. Return valid JSON.

Required JSON structure:
{{
  "discussion_points": [{{"point": "", "type": "interpretation|mechanism|comparison|limitation|future_direction|implication|uncertainty", "quote": "", "confidence": "high|medium|low"}}],
  "limitations": [{{"limitation": "", "quote": "", "confidence": "high|medium|low"}}],
  "open_questions": [{{"question": "", "source": "author_explicit|inferred_from_limitation", "quote": "", "confidence": "high|medium|low"}}],
  "future_directions": [{{"direction": "", "quote": "", "confidence": "high|medium|low"}}]
}}

- Return [] if no items are found.
- Each quote <= 240 characters.
- Output valid JSON only.

SECTION TEXT:
{text}""",

        "conclusion": f"""Extract from this CONCLUSION section only explicit findings and implications. Return valid JSON.

Required JSON structure:
{{
  "conclusion_findings": [{{"finding": "", "quote": "", "confidence": "high|medium|low"}}],
  "implications": [{{"implication": "", "quote": "", "confidence": "high|medium|low"}}]
}}

- Return [] if no items are found.
- Each quote <= 240 characters.
- Output valid JSON only.

SECTION TEXT:
{text}""",
    }

    return prompts.get(section_name, "")


def _call_llm(prompt: str) -> str | None:
    """Call DeepSeek or Anthropic API. Returns response text or None."""
    if not prompt:
        return None

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import urllib.request

        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
        model = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro")

        body = json.dumps({
            "model": model,
            "max_tokens": 2000,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            content = data.get("content", [{}])[0].get("text", "")
            return content.strip()

    except Exception:
        return None


def _validate_section_result(result: str | None, section_name: str, paper_id: str) -> dict[str, Any] | None:
    """Validate and clean LLM output."""
    if not result:
        return None
    try:
        # Try to extract JSON from response
        start = result.find("{")
        end = result.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(result[start:end + 1])
            # Basic validation: all values should be lists, strings, or dicts
            for key in list(parsed.keys()):
                val = parsed[key]
                if isinstance(val, list):
                    parsed[key] = [item for item in val if isinstance(item, dict) and any(v for v in item.values() if isinstance(v, str) and len(v) > 5)]
                elif val is None or val == "null" or val == "undefined":
                    parsed[key] = "" if key.endswith("_question") or key.endswith("_objective") or key.endswith("_gap") else []
            return parsed
    except Exception:
        pass
    return None


def run_llm_extraction(root: str | Path, force: bool = False) -> dict[str, Any]:
    """Run section-level LLM extraction for all papers."""
    root = Path(root).resolve()
    evidence_dir = root / "03_Evidence"

    report: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "llm_available": has_api_key(),
        "total": 0, "success": 0, "partial": 0, "failed": 0, "skipped": 0, "llm_skipped_no_key": 0,
        "sections_extracted": 0, "errors": [],
    }

    if not has_api_key():
        report["llm_skipped_no_key"] = 1
        _safe_write_json(evidence_dir / "evidence_llm_report.json", report)
        return report

    for paper_dir in sorted(evidence_dir.iterdir()):
        if not paper_dir.is_dir():
            continue
        sections_path = paper_dir / "sections.json"
        if not sections_path.exists():
            continue
        report["total"] += 1

        evidence_path = paper_dir / "evidence.json"
        if evidence_path.exists():
            try:
                ev = json.loads(evidence_path.read_text(encoding="utf-8"))
                if ev.get("evidence_version") == "v2" and not force:
                    report["skipped"] += 1
                    continue
            except Exception:
                pass

        try:
            sections = json.loads(sections_path.read_text(encoding="utf-8"))
            sec_map = sections.get("sections", {})
            enhanced: dict[str, Any] = {}
            success_count = 0

            for sec_name in ["introduction", "methods", "results", "discussion", "conclusion"]:
                text = sec_map.get(sec_name, "")
                if not text or len(text) < 100:
                    continue
                result = extract_section_with_llm(sec_name, text, paper_dir.name)
                if result:
                    enhanced[sec_name] = result
                    success_count += 1
                    report["sections_extracted"] += 1

            if success_count > 0:
                existing = {}
                if evidence_path.exists():
                    try:
                        existing = json.loads(evidence_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                existing["evidence_version"] = "v2"
                existing["extraction_mode"] = "section_llm"
                existing["llm_used"] = True
                # Merge enhanced sections
                for sec_name, sec_data in enhanced.items():
                    for key, value in sec_data.items():
                        if isinstance(value, list) and value:
                            existing_list = existing.get(key, [])
                            if isinstance(existing_list, list):
                                existing[key] = existing_list + value
                            else:
                                existing[key] = value
                        elif isinstance(value, str) and value:
                            if not existing.get(key):
                                existing[key] = value

                _safe_write_json(evidence_path, existing)
                report["success" if success_count >= 3 else "partial"] += 1
            else:
                report["partial"] += 1
        except Exception as exc:
            report["failed"] += 1
            report["errors"].append(f"{paper_dir.name}: {type(exc).__name__}: {exc}")

    _safe_write_json(evidence_dir / "evidence_llm_report.json", report)
    return report


def _safe_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    import time
    for _ in range(3):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.3)
    tmp.replace(path)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Evidence LLM Extractor V2")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not has_api_key():
        print("No API key found — LLM extraction skipped. Set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY.")
        return 0
    report = run_llm_extraction(args.root, force=args.force)
    print(f"Total: {report['total']}  Success: {report['success']}  Partial: {report['partial']}  Failed: {report['failed']}  Sections: {report['sections_extracted']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
