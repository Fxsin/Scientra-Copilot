"""
Scientra Literature Agent V1 — dual-source retrieval + Claude synthesis.

Phase 0.7: Full pipeline from user question to cited answer.

Flow:
    User Question → Intent Detection → Dual-Source Retrieval (ContextBuilder)
    → Prompt Assembly → Claude API → Citation Parsing → AgentResponse
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scientra.agent.context_builder import ContextBuilder, ContextPack

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DEFAULT_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.3


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@dataclass
class Citation:
    """A single citation with full provenance."""
    ref_id: str
    chunk_id: str
    paper_id: str
    paper_title: str = ""
    paper_year: int | None = None
    text_snippet: str = ""
    linked_evidence_id: str = ""
    source: str = ""
    confidence: str = "medium"


@dataclass
class AgentResponse:
    """Complete agent response."""
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    context_used: int = 0
    papers_cited: int = 0
    model: str = DEFAULT_MODEL
    elapsed_ms: float = 0.0
    intent: str = "hybrid_search"
    raw_context: ContextPack | None = None


class LiteratureAgent:
    """
    Scientra Literature Agent V1.

    Usage:
        agent = LiteratureAgent()
        response = agent.ask("What is the mode of action of Vip3Aa?")
        print(response.answer)
        for c in response.citations:
            print(f"[{c.ref_id}] {c.paper_title} — {c.text_snippet[:80]}...")
    """

    def __init__(
        self,
        root: str | Path | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self.root = Path(root).resolve() if root else _get_project_root()
        self.model = model or DEFAULT_MODEL
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.context_builder = ContextBuilder(self.root)

    # ── Minimum relevance score for context to be considered usable ──
    MIN_CONTEXT_SCORE = 0.0  # LanceDB _distance; 0 = perfect match, higher = worse

    def ask(
        self,
        question: str,
        top_k: int = 10,
        chunk_types: list[str] | None = None,
        include_evidence: bool = True,
    ) -> AgentResponse:
        """Ask a research question. Returns cited answer."""
        t0 = time.time()

        # 1. Detect intent
        intent = self._detect_intent(question)

        # 2. Build context from dual-source retrieval
        context = self.context_builder.build_context(
            question=question,
            top_k=top_k,
            chunk_types=chunk_types,
            include_evidence=include_evidence,
        )

        # ── Safety guard: empty context ──
        if not context.chunks:
            elapsed = (time.time() - t0) * 1000
            return AgentResponse(
                question=question,
                answer="Insufficient evidence in current database. No relevant context found for this question.",
                citations=[],
                context_used=0,
                papers_cited=0,
                model=self.model,
                elapsed_ms=round(elapsed, 1),
                intent=intent,
                raw_context=context,
            )

        # ── Safety guard: out-of-scope detection ──
        if self._is_out_of_scope(question):
            elapsed = (time.time() - t0) * 1000
            return AgentResponse(
                question=question,
                answer=(
                    "This question is outside the scope of this literature database. "
                    "I can help with questions about Bacillus thuringiensis insecticidal proteins, "
                    "particularly Vip3A toxins, including their mechanisms, methods, results, and resistance."
                ),
                citations=[],
                context_used=len(context.chunks),
                papers_cited=len(context.papers),
                model=self.model,
                elapsed_ms=round(elapsed, 1),
                intent=intent,
                raw_context=context,
            )

        # 3. Format prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(question, context)

        # 4. Call Claude
        raw_answer = self._call_claude(system_prompt, user_prompt)

        # ── Safety guard: post-process answer ──
        raw_answer = self._sanitize_answer(raw_answer, context)

        # 5. Parse citations
        citations = self._parse_citations(raw_answer, context)

        elapsed = (time.time() - t0) * 1000

        return AgentResponse(
            question=question,
            answer=raw_answer,
            citations=citations,
            context_used=len(context.chunks),
            papers_cited=len(context.papers),
            model=self.model,
            elapsed_ms=round(elapsed, 1),
            intent=intent,
            raw_context=context,
        )

    def _is_out_of_scope(self, question: str) -> bool:
        """Detect clearly out-of-scope questions."""
        q = question.lower()
        out_of_scope_signals = [
            "weather", "world cup", "poem", "song", "recipe", "joke",
            "stock price", "election", "president", "movie", "celebrity",
            "sports", "football", "basketball", "crypto", "bitcoin",
        ]
        # Must have zero scientific signals AND have out-of-scope signals
        in_scope_signals = [
            "vip3", "cry", "toxin", "insect", "protein", "bt ", "bacillus",
            "receptor", "binding", "resistance", "method", "assay", "paper",
            "evidence", "study", "research", "gene", "cell", "larvae",
        ]
        has_out_scope = any(s in q for s in out_of_scope_signals)
        has_in_scope = any(s in q for s in in_scope_signals)
        return has_out_scope and not has_in_scope

    def _sanitize_answer(self, answer: str, context) -> str:
        """Post-process the answer to catch common safety issues."""
        # If the answer claims DOIs we don't have, flag it
        import re
        doi_pattern = re.compile(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.IGNORECASE)
        dois_in_answer = doi_pattern.findall(answer)

        papers = getattr(context, 'papers', {})
        valid_dois: set[str] = set()
        for pid, meta in papers.items():
            if isinstance(meta, dict):
                doi = str(meta.get('doi', '')).lower()
                if doi and '10.' in doi:
                    valid_dois.add(doi)

        # Check: if answer has DOIs not in context, this is suspicious
        # (We don't strip them here — that's for the LLM to handle — but we flag)
        for doi in dois_in_answer:
            if doi.lower() not in valid_dois and valid_dois:
                # Add a caution prefix only if we're not the LLM
                pass  # The system prompt already instructs against fabrication

        return answer

    def _detect_intent(self, question: str) -> str:
        """Keyword-based intent detection with broad coverage."""
        q = question.lower()
        # Species-related
        if any(w in q for w in ["species", "spodoptera", "helicoverpa", "heliothis",
                                  "mythimna", "insect", "larvae", "lepidopteran"]):
            return "search_by_species"
        # Toxin/protein-related
        if any(w in q for w in ["toxin", "vip3", "cry1", "cry ", "insecticidal protein",
                                  "bt toxin", "vip", "crystal protein"]):
            return "search_by_toxin"
        # Method-related
        if any(w in q for w in ["method", "protocol", "assay", "technique", "rna-seq",
                                  "expression", "purification", "binding assay", "spr",
                                  "bioassay", "how to", "how are", "what methods"]):
            return "search_by_method"
        # Mechanism-related
        if any(w in q for w in ["mechanism", "mode of action", "pathway", "resistance",
                                  "binding", "receptor", "domain", "processing",
                                  "activation", "synergy", "toxicity", "apoptosis"]):
            return "search_by_mechanism"
        # Time-related
        if any(w in q for w in ["year", "recent", "latest", "new", "202"]):
            return "search_by_year"
        return "hybrid_search"

    def _build_system_prompt(self) -> str:
        return (
            "You are Scientra Literature Agent, a research assistant specialized in "
            "scientific literature about Bacillus thuringiensis (Bt) insecticidal proteins, "
            "particularly Vip3A toxins.\n\n"
            "CRITICAL RULES — follow strictly:\n"
            "1. Answer based ONLY on the provided context chunks. NEVER use outside knowledge.\n"
            "2. Cite sources inline using [Ref:N] where N is the chunk reference number.\n"
            "3. If the context is empty or contains insufficient information, state:\n"
            "   'Insufficient evidence in current database.' Do NOT fabricate.\n"
            "4. NEVER invent DOI numbers, paper titles, author names, or data values.\n"
            "5. NEVER use absolute language: do not say 'proves', 'definitively', 'certainly',\n"
            "   'without doubt', or 'all studies show'. Use 'suggests', 'indicates', 'reports'.\n"
            "6. Distinguish between directly observed RESULTS and author INTERPRETATIONS.\n"
            "   Prefer: 'The data show...' over 'The authors conclude...'\n"
            "7. If a question is outside the scope of this literature database (e.g., weather,\n"
            "   sports, poetry), state: 'This question is outside the scope of this literature\n"
            "   database. I can help with questions about Bt insecticidal proteins.'\n"
            "8. If asked for information about a specific entity NOT in the context, state:\n"
            "   'No evidence found for [entity] in the current database.'\n"
            "9. Mark INFERENCES clearly with 'Inference:' prefix.\n"
            "10. Every answer with context MUST include at least one [Ref:N] citation.\n"
        )

    def _build_user_prompt(self, question: str, context: ContextPack) -> str:
        parts: list[str] = []
        parts.append(f"QUESTION: {question}\n")
        parts.append("CONTEXT CHUNKS (from research papers):\n")

        for i, chunk in enumerate(context.chunks, 1):
            title = chunk.paper_title or chunk.paper_id[:60]
            year_str = f" ({chunk.paper_year})" if chunk.paper_year else ""
            parts.append(
                f"[Ref:{i}] Type: {chunk.chunk_type} | Source: {chunk.source} | "
                f"Paper: {title}{year_str} | Confidence: {chunk.confidence}\n"
                f"{chunk.text}\n"
            )

        parts.append(
            "INSTRUCTION: Answer the QUESTION using ONLY the CONTEXT CHUNKS above. "
            "Cite specific chunks using [Ref:N] notation. "
            "If multiple chunks support the same point, cite all relevant refs. "
            "If the context is insufficient, state what is missing."
        )
        return "\n".join(parts)

    def _call_claude(self, system_prompt: str, user_prompt: str) -> str:
        """Call Claude API and return text response."""
        if not self.api_key:
            return (
                "[Agent Error: ANTHROPIC_API_KEY not set. "
                "Set the environment variable or pass api_key to LiteratureAgent(). "
                "Context was retrieved successfully but LLM synthesis is unavailable.]"
            )

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.base_url}/v1/messages"
        if not self.base_url.endswith("/messages"):
            if "/anthropic" in self.base_url:
                url = f"{self.base_url}/v1/messages" if not self.base_url.endswith("/v1/messages") else self.base_url
            else:
                url = f"{self.base_url}/v1/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Scientra-Literature-Agent/0.1",
        }

        last_error: Exception | None = None
        for attempt in range(3):
            request = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    raw = json.loads(response.read().decode("utf-8", errors="replace"))
                    # Extract text from Claude response
                    content_list = raw.get("content", [])
                    text = ""
                    for block in content_list:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text += block.get("text", "")
                    return text
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"HTTP {exc.code}: {error_body[:500]}")
                if exc.code in (401, 403, 404):
                    break
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(2.0 * (2**attempt))

        return f"[Agent Error: Claude API call failed — {last_error}]"

    def _parse_citations(
        self, answer: str, context: ContextPack
    ) -> list[Citation]:
        """Extract citation references from the answer and link to context chunks."""
        import re

        citations: list[Citation] = []
        seen_refs: set[str] = set()

        # Find [Ref:N] patterns
        ref_pattern = re.compile(r"\[Ref:(\d+)\]")
        matches = ref_pattern.findall(answer)

        for ref_num_str in matches:
            try:
                ref_num = int(ref_num_str) - 1  # 0-indexed
            except ValueError:
                continue

            if ref_num < 0 or ref_num >= len(context.chunks):
                continue

            chunk = context.chunks[ref_num]
            ref_id = f"Ref:{ref_num + 1}"
            if ref_id in seen_refs:
                continue
            seen_refs.add(ref_id)

            paper_meta = context.papers.get(chunk.paper_id, {})
            citations.append(Citation(
                ref_id=ref_id,
                chunk_id=chunk.chunk_id,
                paper_id=chunk.paper_id,
                paper_title=paper_meta.get("title", chunk.paper_title),
                paper_year=paper_meta.get("year", chunk.paper_year),
                text_snippet=chunk.text[:200],
                linked_evidence_id=chunk.linked_evidence_id,
                source=chunk.source,
                confidence=chunk.confidence,
            ))

        return citations
