"""Agent Answer Builder — generate answers (evidence_only or llm_synthesis)."""

from __future__ import annotations
from typing import Any

from scientra.agents.research_agent.agent_schema import make_evidence_ref


class AgentAnswerBuilder:
    def build(self, query: str, intent: str, mode: str,
              tool_results: list[dict], chains: list[dict]) -> dict[str, Any]:
        if mode == "llm_synthesis" and self._llm_available():
            return self._build_llm(query, intent, tool_results, chains)

        return self._build_evidence_only(query, intent, tool_results, chains)

    def _build_evidence_only(self, query: str, intent: str,
                              tool_results: list[dict], chains: list[dict]) -> dict:
        refs = self._collect_refs(tool_results)
        all_hits = []
        for tr in tool_results:
            d = tr.get("data", [])
            if isinstance(d, list):
                all_hits.extend(d)

        n_results = len(all_hits)
        n_tools = len([t for t in tool_results if t.get("status") == "success"])
        n_papers = len({h.get("paper_id", "") for h in all_hits if h.get("paper_id")})
        n_chains = len(chains)

        answer = (f"Found {n_results} result(s) using {n_tools} tool(s) across {n_papers} paper(s). "
                  f"Identified {n_chains} evidence chain(s).")
        if refs:
            top = refs[0]
            answer += f" Top result: {top.get('title', '')[:120]}."

        warnings = []
        if n_results == 0:
            warnings.append("No results found — try broadening the query.")
        failed = [t for t in tool_results if t.get("status") in ("warning", "failed")]
        for t in failed:
            warnings.append(f"Tool '{t['tool_name']}' had issues: {t.get('output_summary', '')}")

        return {
            "answer": answer, "evidence_references": refs[:15],
            "evidence_chains": chains, "warnings": warnings,
            "confidence": min(0.3 + 0.1 * n_tools + 0.05 * n_results, 0.85),
        }

    def _build_llm(self, query: str, intent: str,
                    tool_results: list[dict], chains: list[dict]) -> dict:
        try:
            from scientra.ai import call_llm
            ctx = self._build_context(tool_results, chains)
            prompt = f"Answer based on evidence:\n\nQuery: {query}\n\nEvidence:\n{ctx}\n\nReturn concise answer grounded in the evidence. Do not invent facts."
            resp = call_llm(prompt=prompt, task_name="research_agent", temperature=0.2, max_tokens=1024,
                            system_prompt="You are a research agent. Answer ONLY from provided evidence.")
            if resp.success and resp.text:
                refs = self._collect_refs(tool_results)
                return {"answer": resp.text, "evidence_references": refs[:15],
                        "evidence_chains": chains, "warnings": [], "confidence": 0.7}
        except Exception:
            pass
        return self._build_evidence_only(query, intent, tool_results, chains)

    @staticmethod
    def _collect_refs(tool_results: list[dict]) -> list[dict]:
        refs = []
        for tr in tool_results:
            data = tr.get("data", [])
            items = data if isinstance(data, list) else []
            for i, h in enumerate(items[:10]):
                refs.append(make_evidence_ref(
                    f"ref_{tr['tool_name']}_{i}", h.get("asset_type", "unknown"),
                    h.get("paper_id", ""), h.get("title", ""), h.get("text", ""),
                    h.get("source_relative_path", ""), h.get("confidence", 0.5),
                ))
        return refs

    @staticmethod
    def _build_context(tool_results: list[dict], chains: list[dict]) -> str:
        parts = []
        for tr in tool_results:
            data = tr.get("data", [])
            items = data if isinstance(data, list) else []
            for h in items[:5]:
                parts.append(f"[{h.get('asset_type', '?')}] {h.get('title', '')} — {h.get('text', '')[:200]}")
        for c in chains:
            parts.append(f"Chain: {c.get('summary', '')}")
        return "\n".join(parts)[:4000]

    @staticmethod
    def _llm_available() -> bool:
        try:
            from scientra.ai import get_config
            c = get_config()
            return c is not None and c.enabled and bool(c.api_key)
        except Exception:
            return False
