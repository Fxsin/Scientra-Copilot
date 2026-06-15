"""Agent Guardrails — check output for risks."""

from __future__ import annotations
from typing import Any

OVERCLAIM = ["prove", "confirm", "establish", "breakthrough", "novel", "first time", "definitively", "undoubtedly"]


class AgentGuardrails:
    def check(self, answer: str, refs: list[dict], tool_results: list[dict]) -> dict[str, Any]:
        warnings: list[str] = []
        issues: list[str] = []

        # Check for unsupported claims
        oc = sum(1 for w in OVERCLAIM if w in answer.lower())
        if oc >= 2 and len(refs) <= 2:
            warnings.append(f"Overclaim risk: {oc} strong terms with only {len(refs)} references.")
            issues.append("overclaim_risk")

        # Check missing references
        if not refs:
            warnings.append("No evidence references provided.")
            issues.append("no_references")

        # Check missing provenance
        for r in refs:
            if "provenance" not in r:
                warnings.append(f"Reference {r.get('ref_id', '?')} missing provenance.")
                issues.append("missing_provenance")
                break

        # Check for hallucinated citations
        for r in refs:
            sp = r.get("source_relative_path", "")
            if not sp:
                warnings.append(f"Reference {r.get('ref_id', '?')} has no source path.")
                issues.append("no_source_path")

        # Check tool failures
        failed = [t for t in tool_results if t.get("status") in ("warning", "failed")]
        for t in failed:
            warnings.append(f"Tool '{t['tool_name']}' had issues.")

        risk = "high" if len(issues) >= 3 else ("medium" if issues else "low")

        return {"warnings": warnings, "issues": issues, "risk_level": risk, "passed": risk == "low"}
