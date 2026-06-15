"""P5.4 Research Agent Schema — type definitions."""

from __future__ import annotations
from typing import Any


def make_request(query: str, paper_id: str = "", mode: str = "evidence_only",
                 use_graph: bool = True, use_cross_asset: bool = True,
                 use_dataset: bool = True, top_k: int = 20, return_trace: bool = False) -> dict:
    return {"query": query, "paper_id": paper_id, "project_id": None,
            "mode": mode, "use_graph": use_graph, "use_cross_asset": use_cross_asset,
            "use_dataset": use_dataset, "top_k": top_k, "return_trace": return_trace}


def make_tool_call(name: str, input_data: dict | None = None) -> dict:
    return {"tool_call_id": f"tc_{name}", "tool_name": name, "input": input_data or {},
            "status": "pending", "output_summary": "", "warnings": [], "duration_ms": 0}


def make_evidence_ref(ref_id: str, source_type: str, paper_id: str, title: str = "",
                      text: str = "", source_path: str = "", confidence: float = 0.5) -> dict:
    return {"ref_id": ref_id, "source_type": source_type, "paper_id": paper_id,
            "asset_id": None, "source_id": ref_id, "title": title, "text": text[:500],
            "source_relative_path": source_path, "confidence": confidence, "provenance": {}}


def make_response(query: str, intent: str = "", mode: str = "evidence_only",
                  answer: str = "", refs: list | None = None, chains: list | None = None,
                  tools: list | None = None, warnings: list | None = None,
                  confidence: float = 0.5, trace_id: str | None = None) -> dict:
    return {"query": query, "resolved_intent": intent, "mode": mode, "answer": answer,
            "evidence_references": refs or [], "evidence_chains": chains or [],
            "research_plan": None, "used_tools": tools or [],
            "warnings": warnings or [], "confidence": confidence, "trace_id": trace_id}
