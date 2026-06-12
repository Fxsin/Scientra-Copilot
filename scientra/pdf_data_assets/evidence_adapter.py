"""
Evidence Adapter — reads 03_Evidence output and converts to asset-compatible records.

This module does NOT modify evidence_extraction.py or its output format.
It wraps existing evidence.json data into structures the asset builders consume.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EvidenceAdapter:
    """Reads and adapts 03_Evidence data for asset builders."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.evidence_dir = self.root / "03_Evidence"

    def list_paper_ids(self) -> list[str]:
        """Return all paper_ids that have an evidence.json."""
        if not self.evidence_dir.exists():
            return []
        return sorted(
            d.name
            for d in self.evidence_dir.iterdir()
            if d.is_dir() and (d / "evidence.json").exists()
        )

    def load_evidence(self, paper_id: str) -> dict[str, Any] | None:
        """Load evidence.json for a given paper_id. Returns None if missing."""
        path = self.evidence_dir / paper_id / "evidence.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def get_methods(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the methods list from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        methods = ev.get("methods", [])
        return methods if isinstance(methods, list) else []

    def get_key_results(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the key_results list from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        results = ev.get("key_results", [])
        return results if isinstance(results, list) else []

    def get_core_findings(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the core_findings list from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        findings = ev.get("core_findings", [])
        return findings if isinstance(findings, list) else []

    def get_discussion_points(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the discussion_points list from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        points = ev.get("discussion_points", [])
        return points if isinstance(points, list) else []

    def get_claims(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the claims list from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        claims = ev.get("claims", [])
        return claims if isinstance(claims, list) else []

    def get_limitations(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the limitations list from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        limits = ev.get("limitations", [])
        return limits if isinstance(limits, list) else []

    def get_open_questions(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the open_questions list from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        questions = ev.get("open_questions", [])
        return questions if isinstance(questions, list) else []

    def get_result_discussion_links(self, paper_id: str) -> list[dict[str, Any]]:
        """Return the result_discussion_links from evidence, or empty list."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return []
        links = ev.get("result_discussion_links", [])
        return links if isinstance(links, list) else []

    def get_evidence_meta(self, paper_id: str) -> dict[str, Any]:
        """Return top-level metadata from evidence.json."""
        ev = self.load_evidence(paper_id)
        if ev is None:
            return {}
        return {
            "paper_id": ev.get("paper_id", paper_id),
            "title": ev.get("title", "unknown"),
            "year": ev.get("year"),
            "journal": ev.get("journal", "unknown"),
            "evidence_version": ev.get("evidence_version", "unknown"),
            "status": ev.get("status", "unknown"),
            "coverage": ev.get("coverage", {}),
        }

    def has_evidence(self, paper_id: str) -> bool:
        """Check if evidence.json exists for the paper."""
        return (self.evidence_dir / paper_id / "evidence.json").exists()
