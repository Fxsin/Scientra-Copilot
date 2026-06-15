"""Query Eval Runner — lightweight smoke eval for Cross-Asset Query."""

from __future__ import annotations
from pathlib import Path
from typing import Any

QUERIES = ["MAP2K4 expression", "LC50 bioassay", "Vip3Aa receptor", "western blot evidence", "gene expression"]


class QueryEvalRunner:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)

    def run(self) -> dict[str, Any]:
        results = []
        warnings: list[str] = []

        try:
            from scientra.cross_asset_query import CrossAssetQueryEngine, make_query
            engine = CrossAssetQueryEngine(self.root)
        except Exception as e:
            return {"available": False, "error": str(e), "results": []}

        for q_text in QUERIES:
            r = engine.query(make_query(q_text, top_k=10))
            issues = []

            if "grouped_hits" not in r:
                issues.append("missing grouped_hits")
            hits = r.get("hits", [])
            for h in hits[:3]:
                sp = h.get("source_relative_path", "")
                if not sp:
                    issues.append("missing source_relative_path in hit")
                if ":\\" in sp or sp.startswith("/"):
                    issues.append(f"absolute path in hit: {sp}")
            if not r.get("warnings") and not hits:
                pass  # OK — empty results are valid

            results.append({
                "query": q_text, "total_hits": len(hits),
                "has_grouped": "grouped_hits" in r,
                "issues": issues, "warnings": r.get("warnings", []),
                "passed": len(issues) == 0,
            })

        passed = sum(1 for r in results if r["passed"])
        return {"total_queries": len(results), "passed": passed, "failed": len(results) - passed,
                "results": results, "warnings": warnings}
