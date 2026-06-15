"""Agent Trace Logger — record agent execution traces (no API keys, no absolute paths)."""

from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AgentTraceLogger:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def log(self, request: dict, response: dict, tool_results: list[dict]) -> str:
        trace_id = f"trace_{uuid.uuid4().hex[:10]}"
        trace = {
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": request.get("query", ""),
            "mode": request.get("mode", ""),
            "intent": response.get("resolved_intent", ""),
            "answer_preview": (response.get("answer", "") or "")[:200],
            "tool_count": len(tool_results),
            "tools_used": [t.get("tool_name") for t in tool_results if t.get("status") == "success"],
            "tool_failures": [t.get("tool_name") for t in tool_results if t.get("status") in ("warning", "failed")],
            "ref_count": len(response.get("evidence_references", [])),
            "chain_count": len(response.get("evidence_chains", [])),
            "warnings": response.get("warnings", []),
            "confidence": response.get("confidence", 0),
            "guardrail_risk": response.get("guardrail_risk", "unknown"),
        }

        trace_dir = self.root / "07_Agents/research_agent/traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{trace_id}.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

        tool_dir = self.root / "07_Agents/research_agent/tool_calls"
        tool_dir.mkdir(parents=True, exist_ok=True)
        (tool_dir / f"{trace_id}.json").write_text(json.dumps(tool_results, ensure_ascii=False, indent=2), encoding="utf-8")

        return trace_id
