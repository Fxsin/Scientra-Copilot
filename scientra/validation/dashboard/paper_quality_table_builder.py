"""Paper Quality Table Builder — sortable/filterable paper status table."""

from __future__ import annotations
from typing import Any


class PaperQualityTableBuilder:
    def build(self, papers: list[dict], sort_by: str = "completion_score",
              sort_desc: bool = True, filter_warnings: bool = False,
              filter_stage: str = "", search: str = "", limit: int = 100) -> list[dict]:
        result = list(papers)

        if filter_warnings:
            result = [p for p in result if p.get("warnings") and len(p.get("warnings", [])) > 0]
        if filter_stage:
            result = [p for p in result if not p.get(filter_stage)]
        if search:
            s = search.lower()
            result = [p for p in result if s in p.get("paper_id", "").lower()]

        reverse = sort_desc
        if sort_by == "completion_score":
            result.sort(key=lambda p: p.get("completion_score", 0), reverse=reverse)
        elif sort_by == "warnings":
            result.sort(key=lambda p: len(p.get("warnings", [])), reverse=reverse)
        elif sort_by == "paper_id":
            result.sort(key=lambda p: p.get("paper_id", ""))

        return result[:limit]
