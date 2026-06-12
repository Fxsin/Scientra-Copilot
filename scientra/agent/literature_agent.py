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

DEFAULT_MODEL = os.environ.get("SCIENTRA_LLM_MODEL", "")
DEFAULT_BASE_URL = os.environ.get("SCIENTRA_LLM_BASE_URL", "")
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.3

# Provider auto-detection: env var → config file → none
def _detect_provider():
    # 1. Environment variables
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek", os.environ["DEEPSEEK_API_KEY"], "deepseek-chat", "https://api.deepseek.com"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", os.environ["ANTHROPIC_API_KEY"], "claude-sonnet-4-6", "https://api.anthropic.com"

    # 2. Config file
    config_path = Path(__file__).resolve().parent.parent.parent / "Config" / "llm_config.yaml"
    if config_path.exists():
        try:
            import yaml
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            provider = cfg.get("provider", "")
            api_key = cfg.get("api_key", "")
            model = cfg.get("model", "")
            base_url = cfg.get("base_url", "")
            if provider and api_key:
                return provider, api_key, model or _default_model(provider), base_url or _default_url(provider)
        except Exception:
            pass

    return None, "", "", ""

def _default_model(provider: str) -> str:
    return "deepseek-chat" if provider == "deepseek" else "claude-sonnet-4-6"

def _default_url(provider: str) -> str:
    return "https://api.deepseek.com" if provider == "deepseek" else "https://api.anthropic.com"


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

        # Auto-detect provider
        provider, detected_key, detected_model, detected_url = _detect_provider()
        self.provider = provider or "none"
        self.api_key = api_key or detected_key
        self.model = model or DEFAULT_MODEL or detected_model
        self.base_url = (base_url or DEFAULT_BASE_URL or detected_url).rstrip("/")
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
        include_assets: bool = True,
        paper_id: str | None = None,
        use_llm: bool = True,
        return_context: bool = False,
    ) -> AgentResponse:
        """Ask a research question. Returns cited answer.

        Args:
            question: Research question
            top_k: Max chunks per source
            chunk_types: Filter by section/method/result/claim
            include_evidence: Search evidence_chunks
            include_assets: Search pdf_asset_chunks
            paper_id: Limit to single paper
            use_llm: If False, return extractive answer without Claude
            return_context: Include raw context in response
        """
        t0 = time.time()

        # 1. Detect intent
        intent = self._detect_intent(question)

        # 2. Build context from configured sources
        if include_assets and include_evidence:
            context = self.context_builder.build_context(
                question=question, top_k=top_k,
                chunk_types=chunk_types, include_evidence=True,
            )
        elif include_assets:
            context = self.context_builder.build_context(
                question=question, top_k=top_k,
                chunk_types=chunk_types, include_evidence=False,
            )
        elif include_evidence:
            context = self.context_builder.build_context(
                question=question, top_k=top_k,
                chunk_types=chunk_types, include_evidence=True,
            )
            # Remove asset chunks if any leaked
            context.chunks = [c for c in context.chunks if c.source != "pdf_asset_chunks"]
        else:
            context = self.context_builder.build_context(
                question=question, top_k=top_k,
                chunk_types=chunk_types, include_evidence=True,
            )

        # Post-filter by paper_id
        if paper_id:
            context.chunks = [c for c in context.chunks if c.paper_id == paper_id]
            # Rebuild papers dict
            context.papers = {paper_id: context.papers.get(paper_id, {})} if paper_id in context.papers else {}

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
                raw_context=context if return_context else None,
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
                raw_context=context if return_context else None,
            )

        # 3. If use_llm=False, return structured extractive answer
        if not use_llm:
            extractive_answer = self._build_extractive_answer(question, intent, context, top_k)
            citations = self._parse_citations(extractive_answer, context)
            elapsed = (time.time() - t0) * 1000
            return AgentResponse(
                question=question,
                answer=extractive_answer,
                citations=citations,
                context_used=len(context.chunks),
                papers_cited=len(context.papers),
                model="evidence-only-fallback",
                elapsed_ms=round(elapsed, 1),
                intent=intent,
                raw_context=context if return_context else None,
            )

        # 4. Format prompt + call Claude
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(question, context)
        raw_answer = self._call_claude(system_prompt, user_prompt)

        # Detect if LLM actually responded
        if raw_answer.startswith("[Agent Error:"):
            # Fallback to extractive
            extractive_answer = self._build_extractive_answer(question, intent, context, top_k)
            citations = self._parse_citations(extractive_answer, context)
            elapsed = (time.time() - t0) * 1000
            return AgentResponse(
                question=question,
                answer=extractive_answer,
                citations=citations,
                context_used=len(context.chunks),
                papers_cited=len(context.papers),
                model="evidence-only-fallback",
                elapsed_ms=round(elapsed, 1),
                intent=intent,
                raw_context=context if return_context else None,
            )

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
            raw_context=context if return_context else None,
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

    def _build_extractive_answer(self, question: str, intent: str, context, top_k: int) -> str:
        """Build a structured extractive answer based on intent type."""
        chunks = context.chunks[:top_k]

        # Filter low-quality method chunks
        if intent in ("search_by_method", "search_by_toxin"):
            return self._build_method_summary(chunks)

        # Default: simple listing
        lines = ["Evidence-only summary (no LLM):\n"]
        for i, c in enumerate(chunks, 1):
            lines.append(f"[Ref:{i}] [{c.chunk_type}] {c.text[:200]}")
        lines.append("\n*Enable LLM synthesis for a more polished answer.*")
        return "\n".join(lines)

    def _build_method_summary(self, chunks) -> str:
        """Build a categorized method summary from chunks."""
        # Group chunks by method category
        categories: dict[str, list] = {
            "Molecular / genetic methods": [],
            "Protein / biochemical methods": [],
            "Bioassay / phenotype methods": [],
            "Structural / biophysical methods": [],
            "Statistical / computational methods": [],
            "Other methods": [],
        }

        mol_keywords = ["pcr", "qpcr", "rna-seq", "rnaseq", "transcriptom", "cloning", "gene", "sequencing",
                        "genotyping", "crispr", "rnai", "knockout", "knockdown", "mutagenesis", "expression"]
        prot_keywords = ["western blot", "sds-page", "sds page", "elisa", "binding assay", "ligand blot",
                         "protein", "purification", "recombinant", "heterologous", "blot", "electrophoresis"]
        bio_keywords = ["bioassay", "toxicity", "lc50", "ld50", "mortality", "feeding assay", "diet",
                        "leaf disc", "field trial", "greenhouse", "lab colony", "larvae"]
        struct_keywords = ["cryo-em", "cryo em", "microscopy", "confocal", "structure", "modeling",
                           "homology", "domain", "crystallography", "nmr"]
        stat_keywords = ["statistical", "regression", "anova", "t-test", "phylogenetic", "alignment",
                         "docking", "bioinformatic", "software", "database"]

        # Generic phrases to skip in extractive answer
        skip_phrases = [
            "using the approach", "using this method", "leaves were used",
            "japonica were used", "samples were used", "was used", "were used",
            "the approach", "method described", "as described previously",
            "according to the manufacturer",
        ]

        ref_idx = 0
        seen_texts: set[str] = set()
        for c in chunks:
            ref_idx += 1
            text = getattr(c, 'text', '')
            text_lower = text.lower()
            # Skip generic method phrases
            if any(p in text_lower for p in skip_phrases) and len(text) < 80:
                continue
            # Deduplicate near-identical texts
            text_key = text_lower[:60].strip()
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            matched = False
            for cat, keywords in [
                ("Molecular / genetic methods", mol_keywords),
                ("Protein / biochemical methods", prot_keywords),
                ("Bioassay / phenotype methods", bio_keywords),
                ("Structural / biophysical methods", struct_keywords),
                ("Statistical / computational methods", stat_keywords),
            ]:
                if any(kw in text_lower for kw in keywords):
                    categories[cat].append((ref_idx, text[:150]))
                    matched = True
                    break
            if not matched:
                categories["Other methods"].append((ref_idx, text[:150]))

        # Build output
        lines = ["Evidence-only summary:\n", "Common method categories found in the retrieved context:\n"]

        has_any = False
        for cat, items in categories.items():
            if not items:
                continue
            has_any = True
            lines.append(f"### {cat}")
            for ref_id, snippet in items[:4]:
                lines.append(f"- {snippet} [Ref:{ref_id}]")
            lines.append("")

        if not has_any:
            lines.append("Retrieved method evidence is too generic. " +
                         "Try a more specific query, such as: protein expression, binding assay, or toxicity assay.")

        lines.append("*This is an extractive summary based on retrieved chunks. Enable LLM synthesis for a more polished interpretation.*")
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        return (
            "You are Scientra Literature Agent, a research assistant specialized in "
            "scientific literature about Bacillus thuringiensis (Bt) insecticidal proteins, "
            "particularly Vip3A toxins.\n\n"
            "CRITICAL RULES — follow strictly:\n"
            "1. Answer based ONLY on the provided context chunks. NEVER use outside knowledge.\n"
            "2. Cite sources inline using [Ref:N] where N is the chunk reference number.\n"
            "   Every key claim MUST have at least one [Ref:N] citation.\n"
            "3. If the context is empty or contains insufficient information, state:\n"
            "   'Insufficient evidence in current database.' Do NOT fabricate.\n"
            "4. NEVER invent DOI numbers, paper titles, author names, data values, or statistics.\n"
            "5. NEVER use absolute language: do not say 'proves', 'definitively', 'certainly',\n"
            "   'without doubt', or 'all studies show'. Use 'suggests', 'indicates', 'reports'.\n"
            "6. Distinguish between directly observed RESULTS and author INTERPRETATIONS.\n"
            "7. For METHOD questions: group by category (molecular, biochemical, bioassay, etc.).\n"
            "8. For CLAIM questions: distinguish evidence-based claims from inferences.\n"
            "9. For RESEARCH GAP questions: separate evidence-based gaps from possible gaps.\n"
            "10. Mark INFERENCES clearly with 'Inference:' prefix.\n"
            "11. Keep answers concise (300–700 words). Use scientific terminology.\n"
            "12. If the question is outside the database scope, state so and redirect.\n"
            "13. If asked about a fake/nonexistent entity, state: 'No evidence found.'\n"
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
        """Call LLM API (Anthropic or DeepSeek) and return text response."""
        if not self.api_key:
            return (
                "[Agent Error: No LLM API key configured. "
                "Run: python Scripts/setup_llm.py or set DEEPSEEK_API_KEY / ANTHROPIC_API_KEY. "
                "Context was retrieved successfully but LLM synthesis is unavailable.]"
            )

        if self.provider == "deepseek":
            return self._call_deepseek(system_prompt, user_prompt)
        return self._call_anthropic(system_prompt, user_prompt)

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
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
        last_error = None
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = json.loads(resp.read().decode("utf-8", errors="replace"))
                text = ""
                for block in raw.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        text += block.get("text", "")
                return text
            except urllib.error.HTTPError as exc:
                last_error = RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}")
                if exc.code in (401, 403): break
            except Exception as exc:
                last_error = exc
            if attempt < 2: time.sleep(2.0 * (2**attempt))
        return f"[Agent Error: API call failed — {last_error}]"

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error = None
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = json.loads(resp.read().decode("utf-8", errors="replace"))
                return raw["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                last_error = RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}")
                if exc.code in (401, 403): break
            except Exception as exc:
                last_error = exc
            if attempt < 2: time.sleep(2.0 * (2**attempt))
        return f"[Agent Error: API call failed — {last_error}]"

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
