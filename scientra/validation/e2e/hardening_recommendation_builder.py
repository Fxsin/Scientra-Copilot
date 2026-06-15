"""Hardening Recommendation Builder — generate P0/P1/P2/P3 recommendations."""

from __future__ import annotations
from typing import Any


class HardeningRecommendationBuilder:
    def build(self, inventory: dict, paper_status: list[dict], storage: dict,
              module_health: dict, query_eval: dict, agent_eval: dict) -> dict[str, list[dict]]:
        recs: dict[str, list[dict]] = {"P0": [], "P1": [], "P2": [], "P3": []}

        # P0: Blocking issues
        if not module_health.get("all_modules_ok"):
            for mod, status in module_health.get("modules", {}).items():
                if status != "ok":
                    recs["P0"].append({"title": f"Module import failed: {mod}", "detail": status, "fix": "Check dependencies and import paths"})
        if storage.get("issues"):
            for issue in storage["issues"]:
                recs["P0"].append({"title": "Storage issue", "detail": issue, "fix": "Create missing directory or fix permissions"})

        # P1: Important
        if not storage.get("db_v2_clean"):
            for hit in storage.get("db_v2_hits", [])[:5]:
                recs["P1"].append({"title": "DB/DB_v2 reference found", "detail": f"In file: {hit}", "fix": "Replace with Storage Layout v3 path"})
        if query_eval.get("failed", 0) > 0:
            recs["P1"].append({"title": "Query eval failures", "detail": f"{query_eval['failed']} queries failed", "fix": "Check CrossAssetQueryEngine output"})
        if agent_eval.get("failed", 0) > 0:
            recs["P1"].append({"title": "Agent eval failures", "detail": f"{agent_eval['failed']} agent queries failed", "fix": "Check ResearchAgentRunner output"})
        low_completion = [p for p in paper_status if p.get("completion_score", 0) < 0.3]
        if low_completion:
            recs["P1"].append({"title": f"{len(low_completion)} papers with low completion", "detail": "Run P4/P5 pipelines for these papers", "fix": "Scripts/build_*.py --all"})

        # P2: Polish
        missing_scripts = [s for s, v in module_health.get("scripts", {}).items() if v != "exists"]
        if missing_scripts:
            recs["P2"].append({"title": f"Missing scripts: {len(missing_scripts)}", "detail": ", ".join(missing_scripts[:5]), "fix": "Re-create missing CLI scripts"})
        if paper_status:
            avg = sum(p.get("completion_score", 0) for p in paper_status) / len(paper_status)
            if avg < 0.5:
                recs["P2"].append({"title": "Low average completion", "detail": f"Average: {avg:.2f}", "fix": "Run figure/table/supplementary intelligence pipelines"})

        # P3: Future
        recs["P3"].append({"title": "Performance benchmarking", "detail": "No performance tests run", "fix": "Add query/agent latency benchmarks in P6.5"})
        recs["P3"].append({"title": "CI/CD integration", "detail": "No CI/CD configured", "fix": "Add GitHub Actions for auto-validation"})
        recs["P3"].append({"title": "API documentation", "detail": "No OpenAPI docs generated", "fix": "Enable FastAPI auto-docs or add manual docs"})

        return recs
