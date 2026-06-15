"""Demo Query Runner — run fixed demo queries against P4/P5 modules."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

DEMO_QUERIES = ["DEMO_GENE_A expression", "gene expression dataset", "LC50 bioassay", "Which tables support the demo findings?", "Generate a research plan based on demo gaps"]


class DemoQueryRunner:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)

    def run(self, use_cross_asset: bool = True, use_dataset: bool = True, use_agent: bool = False) -> dict[str, Any]:
        results = []
        warnings: list[str] = []

        for q_text in DEMO_QUERIES[:4]:
            r = {"query": q_text, "hits": 0, "error": None}
            try:
                if use_cross_asset:
                    from scientra.cross_asset_query import CrossAssetQueryEngine, make_query
                    engine = CrossAssetQueryEngine(self.root)
                    resp = engine.query(make_query(q_text, top_k=10))
                    r["hits"] = len(resp.get("hits", []))
            except Exception as e:
                r["error"] = str(e)
                warnings.append(f"Cross-asset query failed for '{q_text}': {e}")
            results.append(r)

        if use_agent:
            try:
                from scientra.agents.research_agent import ResearchAgentRunner, make_request
                runner = ResearchAgentRunner(self.root)
                agent_r = runner.ask(make_request(DEMO_QUERIES[4], mode="evidence_only", top_k=10))
                results.append({"query": DEMO_QUERIES[4], "agent_answer": agent_r.get("answer", "")[:200], "refs": len(agent_r.get("evidence_references", [])), "mode": agent_r["mode"]})
            except Exception as e:
                warnings.append(f"Agent query failed: {e}")

        output_dir = self.root / "09_Exports/demo_project"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "demo_query_results.json").write_text(json.dumps({"results": results, "warnings": warnings}, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "demo_query_results.md").write_text(self._md(results, warnings), encoding="utf-8")

        return {"results": results, "warnings": warnings, "output_dir": str(output_dir.relative_to(self.root))}

    @staticmethod
    def _md(results: list[dict], warnings: list[str]) -> str:
        lines = ["# Demo Query Results", "", "⚠️ All data is synthetic.", ""]
        for r in results:
            lines.append(f"- **{r.get('query', '')}**: hits={r.get('hits', 'N/A')}")
        if warnings:
            lines.append("\n## Warnings")
            for w in warnings: lines.append(f"- {w}")
        return "\n".join(lines)
