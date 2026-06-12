"""
Scientra Literature Agent V1 — Phase 0.7

Dual-source retrieval agent that queries both pdf_asset_chunks (quality-filtered,
provenance-complete) and evidence_chunks (broad coverage), merges context,
and synthesizes cited answers via Claude.

Also re-exports AgentQueryInterface for backward compatibility with scientra/agent.py.

Architecture:
    User Question → Intent Detection → Dual-Source Retrieval
    → Context Merge → Prompt Format → Claude → Cited Answer

Usage:
    from scientra.agent import LiteratureAgent
    agent = LiteratureAgent()
    response = agent.ask("What is the mode of action of Vip3Aa?")
    print(response.answer)
    for citation in response.citations:
        print(f"[{citation.ref_id}] {citation.paper_title}")
"""

from __future__ import annotations

from scientra.agent.literature_agent import LiteratureAgent, AgentResponse, Citation
from scientra.agent.interface import (
    AgentQueryInterface,
    AgentAccessPolicyError,
    normalize_filters,
    coerce_agent_request,
    enforce_agent_policy,
)

__all__ = [
    "LiteratureAgent",
    "AgentResponse",
    "Citation",
    "AgentQueryInterface",
    "AgentAccessPolicyError",
]
