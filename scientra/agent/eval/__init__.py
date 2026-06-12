"""
Scientra Literature Agent Evaluation Framework — Phase 0.7B

Evaluation dimensions:
    - Retrieval quality (context coverage, source balance, latency)
    - Citation validity (Ref mapping, paper existence, no phantom refs)
    - Answer grounding (evidence-based vs inference vs insufficient)
    - Hallucination control (fake entity, fake claim, fake DOI, out-of-scope)
    - Regression testing (25+ cases across 7 categories)

Usage:
    python -m scientra.agent.eval.regression_runner --use-llm false --case-type all
    python -m scientra.agent.eval.regression_runner --use-llm true --limit 10
"""

from __future__ import annotations
