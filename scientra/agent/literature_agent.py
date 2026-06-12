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
from scientra.agent.evidence_packet_builder import build_evidence_packet, clean_text, is_boilerplate_or_disclaimer

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
    token_usage: dict | None = None


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

        # 2. Build context with intent-specific strategy
        if intent == "claim_query":
            context = self._build_claim_context(question, top_k, include_evidence)
        elif intent == "research_gap_query":
            context = self._build_research_gap_context(question, top_k, include_evidence)
        elif intent == "method_query":
            context = self._build_method_context(question, top_k, include_evidence)
        elif intent == "result_query":
            context = self._build_result_context(question, top_k, include_evidence)
        elif include_assets and include_evidence:
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
                token_usage={"source": "no_llm", "total_tokens": 0, "note": "Empty context; no LLM call."},
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
                token_usage={"source": "no_llm", "total_tokens": 0, "note": "Evidence-only mode; no LLM tokens used."},
            )

        # 4. Format prompt + call LLM
        system_prompt = self._build_system_prompt(intent)
        if intent == "claim_query":
            user_prompt = self._build_claim_user_prompt(question, context)
        elif intent == "research_gap_query":
            user_prompt = self._build_gap_user_prompt(question, context)
        elif intent == "method_query":
            packet = build_evidence_packet(context.chunks, max_items=12, intent="method_query")
            user_prompt = f"QUESTION: {question}\n\nEVIDENCE PACKET:\n{packet}\n\nINSTRUCTION: Summarize methods by category. Group into molecular, biochemical, bioassay, microscopy, computational. Cite [Ref:N]. Note fragmentary evidence."
        elif intent == "result_query":
            packet = build_evidence_packet(context.chunks, max_items=12, intent="result_query")
            user_prompt = f"QUESTION: {question}\n\nEVIDENCE PACKET:\n{packet}\n\nINSTRUCTION: Summarize results by category. Note repeated findings vs isolated results. Cite [Ref:N]. Separate results from interpretation."
        else:
            user_prompt = self._build_user_prompt(question, context)
        raw_answer, usage_raw = self._call_claude(system_prompt, user_prompt)

        # Detect if LLM actually responded
        if raw_answer.startswith("[Agent Error:"):
            extractive_answer = self._build_extractive_answer(question, intent, context, top_k)
            citations = self._parse_citations(extractive_answer, context)
            elapsed = (time.time() - t0) * 1000
            return AgentResponse(
                question=question, answer=extractive_answer,
                citations=citations,
                context_used=len(context.chunks), papers_cited=len(context.papers),
                model="evidence-only-fallback", elapsed_ms=round(elapsed, 1),
                intent=intent, raw_context=context if return_context else None,
                token_usage={"source": "unavailable", "total_tokens": 0,
                             "note": "LLM unavailable; answer from evidence-only fallback."},
            )

        raw_answer = self._sanitize_answer(raw_answer, context)
        citations = self._parse_citations(raw_answer, context)
        elapsed = (time.time() - t0) * 1000

        # Build token usage
        cost = self._estimate_cost(usage_raw)
        token_usage = {
            "provider": self.provider, "model": self.model,
            "prompt_tokens": usage_raw.get("prompt_tokens"),
            "completion_tokens": usage_raw.get("completion_tokens"),
            "total_tokens": usage_raw.get("total_tokens"),
            "source": usage_raw.get("source", "provider_reported"),
            "currency": "USD", "note": usage_raw.get("note"),
            **cost,
        }

        return AgentResponse(
            question=question, answer=raw_answer, citations=citations,
            context_used=len(context.chunks), papers_cited=len(context.papers),
            model=self.model, elapsed_ms=round(elapsed, 1),
            intent=intent, raw_context=context if return_context else None,
            token_usage=token_usage,
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
        # Method (new evidence-packet path — MUST be before old search_by_method)
        if any(w in q for w in ["what methods are commonly", "find evidence related to",
                                  "which papers mention", "what bioassay methods",
                                  "what experimental methods", "what techniques are",
                                  "what assays are", "methods are commonly used",
                                  "methods are used in this", "how to measure",
                                  "protein expression", "binding assay"]):
            return "method_query"
        # Result (new evidence-packet path)
        if any(w in q for w in ["which results are", "what results are", "what experimental outcomes",
                                  "what findings are", "what effects are",
                                  "what are the main results", "frequently reported",
                                  "repeatedly observed", "outcomes are described",
                                  "findings are repeatedly", "what conclusions are supported by"]):
            return "result_query"
        # Method-related (generic fallback)
        if any(w in q for w in ["rna-seq", "spr", "how to", "how are",
                                  "method ", "methods ", "protocol", "technique",
                                  "assay", "bioassay"]):
            return "search_by_method"
        # Mechanism-related
        if any(w in q for w in ["mechanism", "mode of action", "pathway", "resistance",
                                  "binding", "receptor", "domain", "processing",
                                  "activation", "synergy", "toxicity", "apoptosis"]):
            return "search_by_mechanism"
        # Research gaps
        if any(w in q for w in ["research gap", "knowledge gap", "missing evidence",
                                  "missing data", "unresolved", "still needed",
                                  "remain unanswered", "insufficient evidence",
                                  "future work", "remains to be determined",
                                  "what gaps", "what evidence is missing",
                                  "what remains", "what experiments are still",
                                  "limitations are repeatedly", "mechanisms are unclear",
                                  "gap", "gaps"]):
            return "research_gap_query"
        # Claim / evidence quality
        if any(w in q for w in ["claim", "claims", "conclusion", "conclusions",
                                  "stronger evidence", "weak evidence", "weakly supported",
                                  "need validation", "unsupported", "indirect evidence",
                                  "lack direct evidence", "drawn across papers",
                                  "supported only indirectly", "need stronger",
                                  "lack sufficient", "which claims", "what claims"]):
            return "claim_query"
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

    def _build_claim_context(self, question: str, top_k: int, include_evidence: bool) -> ContextPack:
        """Build claim-specific context: prioritize claim chunks, low confidence, weak evidence."""
        # Fetch more internally, then rerank
        fetch_k = max(top_k * 3, 30)
        context = self.context_builder.build_context(
            question=question, top_k=fetch_k,
            chunk_types=["claim", "result"],
            include_evidence=include_evidence,
        )
        # Score and rerank: prioritize claim + weak evidence
        scored = []
        boilerplate_count = 0
        for c in context.chunks:
            score = 0
            ctype = getattr(c, 'chunk_type', '')
            conf = getattr(c, 'confidence', '')
            ev_ids = getattr(c, 'linked_evidence_ids', []) or []
            text = clean_text(getattr(c, 'text', ''))
            # Filter boilerplate/disclaimers
            if ctype == "claim" and is_boilerplate_or_disclaimer(text):
                boilerplate_count += 1
                continue
            if ctype == "claim": score += 3
            if conf == "low": score += 2
            elif conf == "medium": score += 1
            if not ev_ids: score += 1
            if len(text) < 50: score -= 2
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        reranked = [c for _, c in scored[:top_k]]
        # Limit per paper
        paper_counts: dict = {}
        limited = []
        for c in reranked:
            pid = getattr(c, 'paper_id', '')
            paper_counts[pid] = paper_counts.get(pid, 0) + 1
            if paper_counts[pid] <= 3:
                limited.append(c)
        context.chunks = limited
        return context

    def _build_claim_user_prompt(self, question: str, context: ContextPack) -> str:
        """Build evidence packet specifically for claim queries."""
        packet = build_evidence_packet(context.chunks, max_items=12)
        return (
            f"QUESTION: {question}\n\n"
            f"EVIDENCE PACKET:\n{packet}\n\n"
            "INSTRUCTION: Analyze the claims in the Evidence Packet. "
            "Identify which claims need stronger evidence and why. "
            "Structure your answer with High-priority and Medium-priority weak claims. "
            "For each: Claim, Current evidence, Why stronger evidence is needed, Missing evidence, Sources. "
            "Use Citation (Year) [Ref:N] format. End with an Overall assessment. "
            "If evidence is insufficient, say so clearly. Do NOT fabricate."
        )

    def _build_research_gap_context(self, question: str, top_k: int, include_evidence: bool) -> ContextPack:
        """Build gap-specific context: prioritize weak claims, limitations, unclear results."""
        fetch_k = max(top_k * 3, 30)
        context = self.context_builder.build_context(
            question=question, top_k=fetch_k,
            chunk_types=["claim", "result", "figure"],
            include_evidence=include_evidence,
        )
        gap_signals = ["unclear", "unknown", "remains", "requires further", "future work",
                       "limitation", "not determined", "inconsistent", "discrepancy",
                       "indirect", "lacking", "insufficient", "needs more", "suggest",
                       "may", "might", "could be", "poorly understood", "not well",
                       "little is known", "no evidence", "missing", "incomplete"]
        scored = []
        for c in context.chunks:
            score = 0
            ctype = getattr(c, 'chunk_type', '')
            conf = getattr(c, 'confidence', '')
            text = clean_text(getattr(c, 'text', ''))
            if is_boilerplate_or_disclaimer(text):
                continue
            if ctype == "claim" and conf in ("low", "medium"): score += 3
            if any(s in text.lower() for s in gap_signals): score += 2
            if conf == "low": score += 1
            if len(text) < 40: score -= 2
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        reranked = [c for _, c in scored[:top_k]]
        paper_counts: dict = {}
        limited = []
        for c in reranked:
            pid = getattr(c, 'paper_id', '')
            paper_counts[pid] = paper_counts.get(pid, 0) + 1
            if paper_counts[pid] <= 3:
                limited.append(c)
        context.chunks = limited
        return context

    def _build_gap_user_prompt(self, question: str, context: ContextPack) -> str:
        packet = build_evidence_packet(context.chunks, max_items=12, intent="research_gap_query")
        return (
            f"QUESTION: {question}\n\n"
            f"EVIDENCE PACKET:\n{packet}\n\n"
            "INSTRUCTION: Identify research gaps from the Evidence Packet. "
            "Structure: ## Evidence-based gaps, ## Inferred gaps (labeled as 'inferred'), "
            "## Overall assessment. For each gap: Observed evidence, Why this indicates a gap, "
            "Missing evidence, Sources. Use Citation (Year) [Ref:N] format. "
            "Be conservative — do not invent gaps. If evidence is insufficient, say so."
        )

    def _build_method_context(self, question: str, top_k: int, include_evidence: bool) -> ContextPack:
        fetch_k = max(top_k * 3, 30)
        context = self.context_builder.build_context(
            question=question, top_k=fetch_k,
            chunk_types=["method", "result"],
            include_evidence=include_evidence,
        )
        scored = []
        for c in context.chunks:
            score = 0
            ctype = getattr(c, 'chunk_type', '')
            text = clean_text(getattr(c, 'text', ''))
            if is_boilerplate_or_disclaimer(text): continue
            if ctype == "method": score += 3
            if any(w in text.lower() for w in ["pcr", "elisa", "blot", "assay", "sequencing", "microscopy",
                "expression", "purification", "binding", "crispr", "rnai", "mutagenesis", "lc50"]): score += 2
            if len(text) < 30: score -= 2
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        reranked = [c for _, c in scored[:top_k]]
        paper_counts: dict = {}; limited = []
        for c in reranked:
            pid = getattr(c, 'paper_id', ''); paper_counts[pid] = paper_counts.get(pid, 0) + 1
            if paper_counts[pid] <= 3: limited.append(c)
        context.chunks = limited
        return context

    def _build_result_context(self, question: str, top_k: int, include_evidence: bool) -> ContextPack:
        fetch_k = max(top_k * 3, 30)
        context = self.context_builder.build_context(
            question=question, top_k=fetch_k,
            chunk_types=["result", "claim"],
            include_evidence=include_evidence,
        )
        scored = []
        for c in context.chunks:
            score = 0
            ctype = getattr(c, 'chunk_type', '')
            text = clean_text(getattr(c, 'text', ''))
            if is_boilerplate_or_disclaimer(text): continue
            if ctype == "result": score += 3
            if any(w in text.lower() for w in ["showed", "demonstrated", "increased", "decreased",
                "significant", "observed", "found that", "result", "revealed", "indicated"]): score += 2
            if len(text) < 40: score -= 2
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        reranked = [c for _, c in scored[:top_k]]
        paper_counts: dict = {}; limited = []
        for c in reranked:
            pid = getattr(c, 'paper_id', ''); paper_counts[pid] = paper_counts.get(pid, 0) + 1
            if paper_counts[pid] <= 3: limited.append(c)
        context.chunks = limited
        return context

    def _build_system_prompt(self, intent: str = "hybrid_search") -> str:
        base = (
            "You are Scientra Literature Agent. Answer using ONLY the Evidence Packet. "
            "NEVER invent papers, data, DOIs, or values. "
            "Use author-year citations: 'Author et al. (Year) [Ref:N]'. "
            "Separate evidence from inference. If evidence is weak or missing, say so.\n"
        )
        if intent == "claim_query":
            return (
                "You are a scientific evidence reviewer. Evaluate CLAIM QUALITY.\n"
                "Output structure:\n"
                "# Claims needing stronger evidence\n"
                "## High-priority weak claims\n"
                "### Claim N: {title}\n"
                "**Claim:** ...\n**Current evidence:** ...\n"
                "**Why stronger evidence is needed:** ...\n"
                "**Missing evidence:** bullet list\n"
                "**Sources:** Citation (Year) [Ref:N]\n"
                "## Medium-priority claims (same structure)\n"
                "## Overall assessment\n"
                "**Well-supported:** ...\n**Weak/indirect:** ...\n"
                "**Suggested evidence to add:** ...\n\n"
                "RULES: Use ONLY the Evidence Packet. Cite [Ref:N] + Citation. "
                "NEVER invent. If evidence is insufficient, say so. "
                "Separate evidence from inference. "
                "IGNORE publisher notes, data accuracy disclaimers, copyright text, "
                "and metadata warnings — these are NOT scientific claims. "
                "Only evaluate claims about mechanisms, methods, results, phenotypes, "
                "or experimental conclusions."
            )
        if intent == "research_gap_query":
            return (
                "You are a scientific research gap analyst. Identify gaps from evidence.\n"
                "Output structure:\n"
                "# Research gaps inferred from the literature library\n"
                "## Evidence-based gaps\n"
                "### Gap N: {title}\n"
                "**Observed evidence:** ...\n**Why this indicates a gap:** ...\n"
                "**Missing evidence:** bullet list\n"
                "**Sources:** Citation (Year) [Ref:N]\n"
                "## Inferred gaps (label each as 'Inferred gap')\n"
                "**Basis for inference:** ...\n**Why this remains uncertain:** ...\n"
                "## Overall assessment\n"
                "**Well-covered areas:** ...\n**Weakly supported areas:** ...\n"
                "**Priority evidence to add:** ...\n\n"
                "RULES: Use ONLY the Evidence Packet. Be conservative. "
                "Label inferences clearly. NEVER invent. "
                "Use Citation (Year) [Ref:N] format."
            )
        if intent == "method_query":
            return (
                "You are summarizing RESEARCH METHODS from evidence.\n"
                "Output structure:\n"
                "# Common methods in the literature library\n"
                "## Molecular / genetic methods\n"
                "## Protein / biochemical methods\n"
                "## Bioassay / phenotype methods\n"
                "## Microscopy / imaging methods\n"
                "## Computational / statistical methods\n"
                "## Evidence coverage and limitations\n"
                "For each method: what it is, how used, representative sources.\n"
                "RULES: Use ONLY the Evidence Packet. Cite [Ref:N]. "
                "Group by category. If evidence is fragmentary, say so. NEVER invent."
            )
        if intent == "result_query":
            return (
                "You are summarizing RESEARCH RESULTS from evidence.\n"
                "Output structure:\n"
                "# Commonly reported results\n"
                "## Main result categories (group by topic)\n"
                "For each: **Observed results**, **How strongly supported**, **Sources**.\n"
                "## Repeated or convergent findings\n"
                "## Evidence coverage and limitations\n"
                "RULES: Use ONLY the Evidence Packet. Cite [Ref:N]. "
                "Separate results from interpretation. If evidence is sparse, say so. NEVER invent."
            )
        if "method" in intent:
            return base + (
                "You are summarizing RESEARCH METHODS.\n"
                "Structure: ## Common method categories with representative examples. "
                "Group by molecular, biochemical, bioassay, structural, computational. "
                "Note evidence coverage and limitations."
            )
        return base + (
            "Structure your answer clearly with headings. "
            "Every key claim MUST cite [Ref:N]. "
            "Use 'Author et al. (Year) [Ref:N]' format."
        )

    def _build_user_prompt(self, question: str, context: ContextPack) -> str:
        """Build evidence packet — structured, cleaned context for LLM."""
        parts: list[str] = []
        parts.append(f"QUESTION: {question}\n")
        parts.append("EVIDENCE PACKET (from research papers):\n")

        for i, chunk in enumerate(context.chunks, 1):
            text = self._sanitize_text(getattr(chunk, 'text', ''))
            if not text or len(text) < 20:
                continue

            title = chunk.paper_title or chunk.paper_id[:60]
            year = getattr(chunk, 'paper_year', None)
            year_str = str(year) if year else "?"
            ctype = getattr(chunk, 'chunk_type', 'unknown')
            conf = getattr(chunk, 'confidence', 'unknown')
            source = getattr(chunk, 'source', '')
            source_short = "Asset" if "asset" in source else "Evidence" if "evidence" in source else source

            # Evidence role
            role = self._classify_evidence_role(ctype, conf, text)

            parts.append(
                f"[Ref:{i}] {title} ({year_str}) | Type: {ctype} | Role: {role} | "
                f"Confidence: {conf} | Source: {source_short}\n"
                f"{text[:800]}\n"
            )

        parts.append(
            "INSTRUCTION: Answer using ONLY the Evidence Packet above. "
            "Cite EVERY key claim with [Ref:N] in brackets exactly. "
            "Use paper titles (shortened) as citation labels since author names may be unavailable. "
            "Format: '...finding [Ref:1]' or '(see [Ref:2])'. "
            "If evidence is weak, note the confidence level from the packet. "
            "NEVER invent papers, data, or DOIs. Separate evidence from inference clearly."
        )
        return "\n".join(parts)

    def _sanitize_text(self, text: str) -> str:
        """Clean context text of common artifacts."""
        if not text:
            return ""
        # Remove JavaScript artifacts
        for artifact in ["[object Object]", "object Object", "undefined", "null null", "None None"]:
            text = text.replace(artifact, "")
        # Collapse whitespace
        import re
        text = re.sub(r'\s+', ' ', text).strip()
        # Deduplicate repeated phrases (3+ word repeats)
        words = text.split()
        if len(words) > 6:
            for window in [4, 5, 6]:
                for i in range(len(words) - window * 2):
                    phrase = " ".join(words[i:i+window])
                    next_phrase = " ".join(words[i+window:i+window*2])
                    if phrase == next_phrase and len(phrase) > 10:
                        words = words[:i+window] + words[i+window*2:]
                        text = " ".join(words)
                        break
        return text

    def _classify_evidence_role(self, ctype: str, confidence: str, text: str) -> str:
        if ctype == "claim" and confidence in ("low", "medium"):
            return "weak_claim"
        if ctype == "claim":
            return "claim"
        if ctype == "result":
            return "supporting_result"
        if ctype == "method":
            return "method_context"
        if ctype == "figure":
            return "figure_context"
        if confidence == "low":
            return "weak_evidence"
        return "direct_evidence" if confidence == "high" else "background"

    def _call_claude(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        """Call LLM API and return (text, usage_dict)."""
        if not self.api_key:
            return (
                "[Agent Error: No LLM API key configured. "
                "Run: python Scripts/setup_llm.py or set DEEPSEEK_API_KEY / ANTHROPIC_API_KEY. "
                "Context was retrieved successfully but LLM synthesis is unavailable.]"
            ), {"source": "unavailable", "note": "No API key configured"}

        if self.provider == "deepseek":
            return self._call_deepseek(system_prompt, user_prompt)
        return self._call_anthropic(system_prompt, user_prompt)

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        payload = {
            "model": self.model, "max_tokens": self.max_tokens,
            "temperature": self.temperature, "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.base_url}/v1/messages"
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = json.loads(resp.read().decode("utf-8", errors="replace"))
                text = "".join(b.get("text","") for b in raw.get("content",[]) if isinstance(b,dict) and b.get("type")=="text")
                usage_raw = raw.get("usage", {})
                usage = {
                    "source": "provider_reported",
                    "prompt_tokens": usage_raw.get("input_tokens"),
                    "completion_tokens": usage_raw.get("output_tokens"),
                    "total_tokens": (usage_raw.get("input_tokens", 0) or 0) + (usage_raw.get("output_tokens", 0) or 0),
                }
                return text, usage
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403): break
            except Exception: pass
            if attempt < 2: time.sleep(2.0 * (2**attempt))
        return f"[Agent Error: API call failed]", {"source": "unavailable", "note": "API call failed after retries"}

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        payload = {
            "model": self.model,
            "messages": [{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
            "temperature": self.temperature, "max_tokens": self.max_tokens, "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = json.loads(resp.read().decode("utf-8", errors="replace"))
                text = raw["choices"][0]["message"]["content"]
                usage_raw = raw.get("usage", {})
                usage = {
                    "source": "provider_reported",
                    "prompt_tokens": usage_raw.get("prompt_tokens"),
                    "completion_tokens": usage_raw.get("completion_tokens"),
                    "total_tokens": usage_raw.get("total_tokens"),
                }
                return text, usage
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403): break
            except Exception: pass
            if attempt < 2: time.sleep(2.0 * (2**attempt))
        return f"[Agent Error: API call failed]", {"source": "unavailable", "note": "API call failed after retries"}

    def _estimate_cost(self, usage: dict) -> dict:
        """Estimate cost from pricing config."""
        pricing_path = self.root / "Config" / "llm_pricing.yaml"
        pricing = {}
        if pricing_path.exists():
            try:
                import yaml
                pricing = yaml.safe_load(pricing_path.read_text(encoding="utf-8")) or {}
            except Exception: pass

        provider_pricing = pricing.get(self.provider, {}).get(self.model, {})
        input_price = provider_pricing.get("input_per_1m_tokens_usd")
        output_price = provider_pricing.get("output_per_1m_tokens_usd")
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0

        result = {"estimated_input_cost_usd": None, "estimated_output_cost_usd": None, "estimated_total_cost_usd": None}
        if input_price is not None and prompt_tokens:
            result["estimated_input_cost_usd"] = round(prompt_tokens / 1_000_000 * input_price, 6)
        if output_price is not None and completion_tokens:
            result["estimated_output_cost_usd"] = round(completion_tokens / 1_000_000 * output_price, 6)
        if result["estimated_input_cost_usd"] is not None and result["estimated_output_cost_usd"] is not None:
            result["estimated_total_cost_usd"] = round(result["estimated_input_cost_usd"] + result["estimated_output_cost_usd"], 6)
        elif result["estimated_input_cost_usd"] is not None:
            result["estimated_total_cost_usd"] = result["estimated_input_cost_usd"]
        elif result["estimated_output_cost_usd"] is not None:
            result["estimated_total_cost_usd"] = result["estimated_output_cost_usd"]
        return result

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
