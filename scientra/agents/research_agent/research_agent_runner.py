"""Research Agent Runner — P5.4 orchestrator."""

from __future__ import annotations
from pathlib import Path
from typing import Any

from scientra.agents.research_agent.agent_intent_classifier import classify
from scientra.agents.research_agent.agent_planner import plan
from scientra.agents.research_agent.agent_tool_executor import AgentToolExecutor
from scientra.agents.research_agent.evidence_chain_assembler import EvidenceChainAssembler
from scientra.agents.research_agent.agent_answer_builder import AgentAnswerBuilder
from scientra.agents.research_agent.research_plan_builder import ResearchPlanBuilder
from scientra.agents.research_agent.agent_guardrails import AgentGuardrails
from scientra.agents.research_agent.agent_trace_logger import AgentTraceLogger
from scientra.agents.research_agent.agent_schema import make_response


class ResearchAgentRunner:
    """Orchestrate graph-augmented research agent."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def ask(self, request: dict) -> dict[str, Any]:
        query = request.get("query", "")
        mode = request.get("mode", "evidence_only")
        top_k = request.get("top_k", 20)
        return_trace = request.get("return_trace", False)
        warnings: list[str] = []

        # Resolve mode
        if mode == "auto" or mode == "llm_synthesis":
            if not self._llm_available():
                mode = "evidence_only"
                warnings.append("LLM not available — using evidence_only mode.")

        # Stage 1: Intent
        intent = classify(query)

        # Stage 2: Plan
        tools = plan(intent["primary_intent"])
        if not request.get("use_graph", True):
            tools = [t for t in tools if t != "unified_graph_query"]
        if not request.get("use_dataset", True):
            tools = [t for t in tools if t not in ("dataset_query", "dataset_entity_compare")]
        if not request.get("use_cross_asset", True):
            tools = [t for t in tools if t != "cross_asset_query"]

        # Stage 3: Execute tools
        executor = AgentToolExecutor(self.root)
        tool_results = [executor.execute(t, {"query": query}, top_k) for t in tools]
        warnings.extend(executor.warnings)

        # Stage 4: Assemble chains
        assembler = EvidenceChainAssembler()
        chains = assembler.assemble(tool_results)

        # Stage 5: Build answer
        answer_builder = AgentAnswerBuilder()
        answer_data = answer_builder.build(query, intent["primary_intent"], mode, tool_results, chains)

        # Stage 6: Research plan (if relevant)
        research_plan = None
        if intent["primary_intent"] == "research_plan_generation":
            rp = ResearchPlanBuilder()
            research_plan = rp.build(query, tool_results)

        # Stage 7: Guardrails
        guard = AgentGuardrails()
        guard_result = guard.check(answer_data.get("answer", ""), answer_data.get("evidence_references", []), tool_results)
        warnings.extend(guard_result.get("warnings", []))

        # Assemble response
        response = make_response(
            query=query, intent=intent["primary_intent"], mode=mode,
            answer=answer_data.get("answer", ""),
            refs=answer_data.get("evidence_references", []),
            chains=answer_data.get("evidence_chains", []),
            tools=[{"name": t["tool_name"], "status": t["status"], "summary": t.get("output_summary", "")} for t in tool_results],
            warnings=warnings,
            confidence=answer_data.get("confidence", 0.5),
        )
        response["research_plan"] = research_plan
        response["guardrail_risk"] = guard_result["risk_level"]

        # Stage 8: Trace logging
        if return_trace:
            logger = AgentTraceLogger(self.root)
            response["trace_id"] = logger.log(request, response, tool_results)

        return response

    @staticmethod
    def _llm_available() -> bool:
        try:
            from scientra.ai import get_config
            c = get_config()
            return c is not None and c.enabled and bool(c.api_key)
        except Exception:
            return False
