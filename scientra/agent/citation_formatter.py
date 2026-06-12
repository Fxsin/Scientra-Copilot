"""
Citation Formatter — formats agent responses with inline citations and builds
structured citation metadata for downstream consumers.

Phase 0.7: Supports markdown-formatted answers with linked citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FormattedCitation:
    """A citation rendered for consumption (API response / markdown)."""
    ref_id: str
    paper_title: str
    year: str
    journal: str
    chunk_type: str
    text_snippet: str
    linked_evidence_id: str
    source: str


@dataclass
class FormattedAnswer:
    """Complete formatted answer with citations."""
    question: str
    answer_markdown: str
    answer_plain: str
    citations: list[FormattedCitation] = field(default_factory=list)
    model: str = ""
    papers_cited: int = 0
    elapsed_ms: float = 0.0


def format_agent_response(
    answer: str,
    citations: list[Any],  # list of Citation from literature_agent
    question: str = "",
    model: str = "",
    elapsed_ms: float = 0.0,
) -> FormattedAnswer:
    """Format an agent response for API output."""
    formatted_citations: list[FormattedCitation] = []
    papers_seen: set[str] = set()

    for c in citations:
        year_str = str(c.paper_year) if c.paper_year else "?"
        formatted_citations.append(FormattedCitation(
            ref_id=c.ref_id,
            paper_title=c.paper_title or c.paper_id,
            year=year_str,
            journal=getattr(c, 'paper_journal', ''),
            chunk_type=getattr(c, 'chunk_type', 'unknown'),
            text_snippet=getattr(c, 'text_snippet', '')[:200],
            linked_evidence_id=getattr(c, 'linked_evidence_id', ''),
            source=getattr(c, 'source', ''),
        ))
        papers_seen.add(c.paper_id)

    # Build markdown answer with citation footnotes
    md_lines = [answer, "", "---", "## References"]
    for fc in formatted_citations:
        md_lines.append(
            f"- **[{fc.ref_id}]** {fc.paper_title} ({fc.year}) — "
            f"*{fc.chunk_type}* from {fc.source}"
        )

    return FormattedAnswer(
        question=question,
        answer_markdown="\n".join(md_lines),
        answer_plain=answer,
        citations=formatted_citations,
        model=model,
        papers_cited=len(papers_seen),
        elapsed_ms=elapsed_ms,
    )
