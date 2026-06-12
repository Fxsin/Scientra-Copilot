"""
Figure Interpreter — AI-powered figure interpretation from captions.

Phase 1B: Uses Claude to generate structured interpretations.
No OCR, no image analysis. Text-only interpretation from captions + references.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.pdf_data_assets.figure_interpretation_prompt import (
    SYSTEM_PROMPT, build_user_prompt,
)

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DEFAULT_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")


class FigureInterpreter:
    """Interprets figures from captions using Claude API."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).resolve() if root else Path(__file__).resolve().parent.parent.parent
        self.figures_dir = self.root / "06_PDF_DataAssets" / "02_figures"
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = DEFAULT_MODEL
        self.base_url = DEFAULT_BASE_URL.rstrip("/")

    @property
    def llm_available(self) -> bool:
        return bool(self.api_key)

    def interpret_paper(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        """Interpret all eligible figures for a paper."""
        figs_path = self.figures_dir / paper_id / "figures.json"
        out_path = self.figures_dir / paper_id / "figure_interpretations.json"

        if out_path.exists() and not force:
            try:
                data = json.loads(out_path.read_text(encoding="utf-8"))
                return data
            except Exception:
                pass

        if not figs_path.exists():
            return {"paper_id": paper_id, "status": "no_figures", "interpretations": []}

        figures = json.loads(figs_path.read_text(encoding="utf-8"))
        interpretations: list[dict[str, Any]] = []
        stats = {"total": len(figures), "interpreted": 0, "skipped": 0, "pending": 0}

        for i, fig in enumerate(figures):
            quality = fig.get("caption_quality", "none")

            # Skip none-quality figures (no useful caption)
            if quality == "none":
                interp = self._make_skipped(fig, paper_id, i, "caption_quality_none")
                stats["skipped"] += 1
            elif not self.llm_available:
                interp = self._make_pending(fig, paper_id, i)
                stats["pending"] += 1
            else:
                try:
                    interp = self._interpret_figure(fig, paper_id, i)
                    stats["interpreted"] += 1
                except Exception as e:
                    interp = self._make_pending(fig, paper_id, i, str(e))
                    stats["pending"] += 1

            interpretations.append(interp)

        result = {
            "paper_id": paper_id,
            "status": "success",
            "stats": stats,
            "interpretations": interpretations,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        tmp = out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(out_path)
        return result

    def interpret_all(self, force: bool = False) -> dict[str, Any]:
        """Interpret figures for all papers with figures.json."""
        if not self.figures_dir.exists():
            return {"status": "no_figures_dir", "papers": []}

        papers = [d for d in self.figures_dir.iterdir() if d.is_dir() and (d / "figures.json").exists()]
        results = []
        total_stats = {"total": 0, "interpreted": 0, "skipped": 0, "pending": 0}

        for i, pd in enumerate(papers):
            print(f"  [{i+1}/{len(papers)}] {pd.name[:50]}...")
            r = self.interpret_paper(pd.name, force=force)
            results.append(r)
            for k in total_stats:
                total_stats[k] += r.get("stats", {}).get(k, 0)

        return {"status": "complete", "papers": len(papers), "stats": total_stats, "results": results}

    def _interpret_figure(self, fig: dict, paper_id: str, idx: int) -> dict[str, Any]:
        """Call Claude to interpret a single figure."""
        user_prompt = build_user_prompt(fig)
        raw = self._call_claude(SYSTEM_PROMPT, user_prompt)

        # Parse JSON from response
        parsed = self._parse_json(raw)
        return {
            "asset_id": f"{paper_id}:fig_interp:{idx:04d}",
            "paper_id": paper_id,
            "asset_type": "figure_interpretation",
            "figure_id": fig.get("figure_id", f"{paper_id}_fig_{idx}"),
            "figure_label": fig.get("figure_label", "unknown"),
            "figure_type": fig.get("figure_type", "unknown"),
            "caption": fig.get("caption", ""),
            "caption_quality": fig.get("caption_quality", "unknown"),
            "reference_sentences": fig.get("reference_sentences", []),
            "linked_result_assets": fig.get("linked_result_assets", []),
            "linked_claim_assets": fig.get("linked_claim_assets", []),
            "linked_evidence_ids": fig.get("linked_evidence_ids", []),
            "figure_main_message": parsed.get("figure_main_message", ""),
            "experimental_evidence_type": parsed.get("experimental_evidence_type", "unknown"),
            "supported_claims": parsed.get("supported_claims", []),
            "evidence_strength": parsed.get("evidence_strength", "unclear"),
            "limitations": parsed.get("limitations", []),
            "interpretation_confidence": parsed.get("interpretation_confidence", "low"),
            "interpretation_source": "caption_only" if not fig.get("reference_sentences") else "caption_plus_references",
            "status": "interpreted",
            "model_name": self.model,
            "prompt_version": "0.1.0",
            "source_text": fig.get("source_text", fig.get("caption", "")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _make_skipped(self, fig: dict, paper_id: str, idx: int, reason: str) -> dict[str, Any]:
        return {
            "asset_id": f"{paper_id}:fig_interp:{idx:04d}",
            "paper_id": paper_id,
            "asset_type": "figure_interpretation",
            "figure_id": fig.get("figure_id", ""),
            "figure_label": fig.get("figure_label", "unknown"),
            "figure_type": fig.get("figure_type", "unknown"),
            "caption": fig.get("caption", ""),
            "caption_quality": fig.get("caption_quality", "unknown"),
            "reference_sentences": fig.get("reference_sentences", []),
            "linked_result_assets": fig.get("linked_result_assets", []),
            "linked_claim_assets": fig.get("linked_claim_assets", []),
            "linked_evidence_ids": fig.get("linked_evidence_ids", []),
            "status": "skipped",
            "figure_main_message": "",
            "experimental_evidence_type": "unknown",
            "supported_claims": [],
            "evidence_strength": "unclear",
            "limitations": [f"Skipped: {reason}"],
            "interpretation_confidence": "low",
            "interpretation_source": "reference_only",
            "model_name": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _make_pending(self, fig: dict, paper_id: str, idx: int, error: str = "") -> dict[str, Any]:
        return {
            "asset_id": f"{paper_id}:fig_interp:{idx:04d}",
            "paper_id": paper_id,
            "figure_label": fig.get("figure_label", "unknown"),
            "figure_type": fig.get("figure_type", "unknown"),
            "caption": fig.get("caption", ""),
            "caption_quality": fig.get("caption_quality", "unknown"),
            "reference_sentences": fig.get("reference_sentences", []),
            "linked_result_assets": fig.get("linked_result_assets", []),
            "linked_claim_assets": fig.get("linked_claim_assets", []),
            "linked_evidence_ids": fig.get("linked_evidence_ids", []),
            "status": "pending",
            "figure_main_message": "",
            "experimental_evidence_type": "unknown",
            "supported_claims": [],
            "evidence_strength": "unclear",
            "limitations": [f"Pending: LLM unavailable" + (f" — {error[:100]}" if error else "")],
            "interpretation_confidence": "low",
            "interpretation_source": "reference_only",
            "model_name": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _call_claude(self, system_prompt: str, user_prompt: str) -> str:
        """Call Claude API."""
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = ""
        for block in raw.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
        return text

    def _parse_json(self, text: str) -> dict[str, Any]:
        """Extract JSON from Claude's response."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting from code blocks
        import re
        m = re.search(r'\{[^{}]*"figure_main_message"[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {"figure_main_message": text[:200], "experimental_evidence_type": "unknown"}
