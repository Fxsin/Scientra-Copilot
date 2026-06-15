"""Agent Eval Runner — lightweight smoke eval for Research Agent."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

QUERIES = ["MAP2K4 expression", "which evidence supports Vip3Aa receptor mechanism", "generate research plan for Bt toxin resistance"]


class AgentEvalRunner:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def run(self) -> dict[str, Any]:
        results = []
        warnings: list[str] = []

        try:
            from scientra.agents.research_agent import ResearchAgentRunner, make_request
            runner = ResearchAgentRunner(self.root)
        except Exception as e:
            return {"available": False, "error": str(e), "results": []}

        for q_text in QUERIES:
            r = runner.ask(make_request(q_text, mode="evidence_only", top_k=5, return_trace=True))
            issues = []

            if not r.get("answer"):
                issues.append("missing answer")
            if r["mode"] != "evidence_only":
                issues.append("not in evidence_only mode")
            refs = r.get("evidence_references", [])
            for ref in refs[:3]:
                sp = ref.get("source_relative_path", "")
                if ":\\" in sp or sp.startswith("/"):
                    issues.append(f"absolute path in reference: {sp}")

            # Check no API key in trace
            if r.get("trace_id"):
                trace_path = self.root / "07_Agents/research_agent/traces" / f"{r['trace_id']}.json"
                if trace_path.exists():
                    trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
                    trace_str = json.dumps(trace_data)
                    if "api_key" in trace_str.lower() or "sk-" in trace_str:
                        issues.append("potential API key in trace")

            results.append({
                "query": q_text, "has_answer": bool(r.get("answer")),
                "ref_count": len(r.get("evidence_references", [])),
                "chain_count": len(r.get("evidence_chains", [])),
                "mode": r["mode"], "issues": issues,
                "passed": len(issues) == 0,
            })

        passed = sum(1 for r in results if r["passed"])
        return {"total_queries": len(results), "passed": passed, "failed": len(results) - passed,
                "results": results, "warnings": warnings}
