"""
Hybrid PDF Parser — Evidence Input Selector (P1).

Provides select_text_for_evidence() which decides whether to use
hybrid final markdown or legacy raw text as input for evidence extraction.

This is the ONLY touchpoint for P1 — evidence/chunk/embedding pipelines
are NOT modified. Only the text source selection changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _resolve_root() -> Path:
    """Resolve project root from this file's location."""
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parents[2]


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    """Load a YAML file safely, returning empty dict on any failure."""
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _read_text_safe(path: Path) -> str | None:
    """Read a text file, returning None on any failure."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def _load_json_safe(path: Path) -> dict[str, Any] | None:
    """Load a JSON file, returning None on any failure."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def select_text_for_evidence(
    paper_id: str,
    legacy_text_path: str | Path | None = None,
    config: dict[str, Any] | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Select the best available text for evidence extraction.

    Decision logic:
    1. If hybrid_parser is disabled or prefer_hybrid_markdown_for_evidence is
       false → return legacy text immediately (safe default).
    2. If hybrid final markdown exists AND quality >= threshold AND not empty
       → return hybrid_final_markdown.
    3. Otherwise → fall back to legacy text with a reason.

    Args:
        paper_id: The paper identifier.
        legacy_text_path: Path to the legacy raw text file (03_Summary/raw_text/{paper_id}.txt).
        config: Optional hybrid_parser config dict. Loaded from workflow_config.yaml if None.
        root: Project root directory. Auto-detected if None.

    Returns:
        A dict with keys:
        - text: The selected text content (str, may be empty)
        - source: "hybrid_final_markdown" | "legacy_raw_text" | "grobid_text" | "missing"
        - source_path: Absolute path to the source file (str, may be empty)
        - quality_score: Float 0.0–1.0 from the hybrid parse manifest, or 0.0
        - warnings: List of warning strings
        - fallback_reason: str or None — why we fell back (if applicable)
    """
    project_root = Path(root) if root else _resolve_root()

    # ── Load config ──
    if config is None:
        wf_path = project_root / "Config" / "workflow_config.yaml"
        if wf_path.exists():
            full_config = _load_yaml_safe(wf_path)
            config = full_config.get("hybrid_parser", {})
        else:
            config = {}

    hybrid_enabled = config.get("enabled", False)
    prefer_hybrid = config.get("prefer_hybrid_markdown_for_evidence", False)
    min_score = config.get("min_final_markdown_score_for_evidence", 0.65)

    # ── Gate 1: Fast path — hybrid not enabled or not preferred ──
    if not hybrid_enabled or not prefer_hybrid:
        return _load_legacy_text(paper_id, legacy_text_path, project_root,
                                 reason="Hybrid parser disabled or prefer_hybrid_markdown_for_evidence=false")

    # ── Gate 2: Try hybrid final markdown ──
    final_md_path = project_root / "02_Parse" / "markdown" / "final" / f"{paper_id}.md"
    manifest_path = project_root / "02_Parse" / "reports" / "hybrid" / f"{paper_id}_parse_manifest.json"

    if not final_md_path.exists():
        return _load_legacy_text(paper_id, legacy_text_path, project_root,
                                 reason="Final markdown not found at 02_Parse/markdown/final/")

    # Read markdown
    md_text = _read_text_safe(final_md_path)
    if not md_text or not md_text.strip():
        return _load_legacy_text(paper_id, legacy_text_path, project_root,
                                 reason="Final markdown is empty")

    # Check quality from manifest
    quality_score = 0.0
    if manifest_path.exists():
        manifest = _load_json_safe(manifest_path)
        if manifest:
            qr = manifest.get("quality_report") or {}
            quality_score = qr.get("overall_score", qr.get("markdown_score", 0.0))

    if quality_score < min_score:
        return _load_legacy_text(
            paper_id, legacy_text_path, project_root,
            reason=f"Final markdown quality score {quality_score:.2f} below threshold {min_score}",
        )

    # ── Success: return hybrid final markdown ──
    return {
        "text": md_text,
        "source": "hybrid_final_markdown",
        "source_path": str(final_md_path),
        "quality_score": quality_score,
        "warnings": [],
        "fallback_reason": None,
    }


def _load_legacy_text(
    paper_id: str,
    legacy_text_path: str | Path | None,
    root: Path,
    reason: str | None = None,
) -> dict[str, Any]:
    """Load legacy raw text with fallback chain."""
    warnings: list[str] = []
    if reason:
        warnings.append(f"Falling back to legacy text: {reason}")

    # Try explicit path first
    if legacy_text_path:
        lp = Path(legacy_text_path)
        text = _read_text_safe(lp)
        if text:
            return {
                "text": text,
                "source": "legacy_raw_text",
                "source_path": str(lp),
                "quality_score": 0.0,
                "warnings": warnings,
                "fallback_reason": reason,
            }

    # Try standard locations
    candidates = [
        root / "03_Summary" / "raw_text" / f"{paper_id}.txt",
        root / "02_Parse" / "text" / "pymupdf" / f"{paper_id}.txt",
        root / "02_Parse" / "text" / "grobid" / f"{paper_id}.tei.xml",
    ]

    for cand in candidates:
        text = _read_text_safe(cand)
        if text and text.strip():
            source_type = "legacy_raw_text"
            if "grobid" in str(cand):
                source_type = "grobid_text"
            return {
                "text": text,
                "source": source_type,
                "source_path": str(cand),
                "quality_score": 0.0,
                "warnings": warnings,
                "fallback_reason": reason,
            }

    # Nothing found
    return {
        "text": "",
        "source": "missing",
        "source_path": "",
        "quality_score": 0.0,
        "warnings": warnings + [f"No text found for paper_id={paper_id} in any known location."],
        "fallback_reason": reason,
    }
