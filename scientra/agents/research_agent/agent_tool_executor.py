"""Agent Tool Executor — execute tool calls, catching failures gracefully."""

from __future__ import annotations
import time
from pathlib import Path
from typing import Any


class AgentToolExecutor:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.warnings: list[str] = []

    def execute(self, tool_name: str, input_data: dict, top_k: int = 20) -> dict[str, Any]:
        t0 = time.time()
        result: dict = {"tool_call_id": f"tc_{tool_name}", "tool_name": tool_name,
                        "input": input_data, "status": "success",
                        "output_summary": "", "warnings": [], "duration_ms": 0,
                        "data": []}

        try:
            if tool_name == "cross_asset_query":
                result["data"] = self._cross_asset(input_data, top_k)
                result["output_summary"] = f"Found {len(result['data'])} cross-asset results"
            elif tool_name == "unified_graph_query":
                result["data"] = self._graph_query(input_data, top_k)
                result["output_summary"] = f"Found {len(result['data'])} graph results"
            elif tool_name == "dataset_query":
                result["data"] = self._dataset_query(input_data)
                result["output_summary"] = f"Found {len(result['data'])} dataset results"
            elif tool_name == "dataset_entity_compare":
                result["data"] = self._entity_compare(input_data)
                result["output_summary"] = f"Entity found in {result['data'].get('found_in_papers', 0) if isinstance(result['data'], dict) else 0} papers"
            elif tool_name == "evidence_search":
                result["data"] = self._evidence_search(input_data, top_k)
                result["output_summary"] = f"Found {len(result['data'])} evidence results"
            elif tool_name == "gap_search":
                result["data"] = self._gap_search(input_data, top_k)
                result["output_summary"] = f"Found {len(result['data'])} gaps"
            elif tool_name == "hypothesis_search":
                result["data"] = self._hypothesis_search(input_data, top_k)
                result["output_summary"] = f"Found {len(result['data'])} hypotheses"
            elif tool_name == "opportunity_search":
                result["data"] = self._opportunity_search(input_data, top_k)
                result["output_summary"] = f"Found {len(result['data'])} opportunities"
            else:
                result["status"] = "skipped"
                result["output_summary"] = f"Unknown tool: {tool_name}"
        except Exception as e:
            result["status"] = "warning"
            result["warnings"].append(str(e))
            result["output_summary"] = f"Tool error: {e}"

        result["duration_ms"] = int((time.time() - t0) * 1000)
        return result

    def _cross_asset(self, inp: dict, top_k: int) -> list:
        try:
            from scientra.cross_asset_query import CrossAssetQueryEngine, make_query
            q = make_query(query=inp.get("query", ""), top_k=min(top_k, 20), use_graph=inp.get("use_graph", True))
            r = CrossAssetQueryEngine(self.root).query(q)
            return r.get("hits", [])[:top_k]
        except Exception:
            return []

    def _graph_query(self, inp: dict, top_k: int) -> list:
        try:
            from scientra.knowledge.unified_graph.graph_query_engine import GraphQueryEngine
            import json
            np = self.root / "05_Knowledge/unified_evidence_graph/graph_nodes.json"
            ep = self.root / "05_Knowledge/unified_evidence_graph/graph_edges.json"
            nodes = json.loads(np.read_text(encoding="utf-8")) if np.exists() else []
            edges = json.loads(ep.read_text(encoding="utf-8")) if ep.exists() else []
            engine = GraphQueryEngine(nodes, edges)
            return engine.search(keyword=inp.get("query", ""), node_type=inp.get("node_type", ""), limit=top_k)
        except Exception:
            return []

    def _dataset_query(self, inp: dict) -> list:
        try:
            from scientra.datasets.intelligence import CrossPaperDatasetIndexer
            idx = CrossPaperDatasetIndexer(self.root)
            if inp.get("entity"):
                return idx.query_entity(inp["entity"])
            if inp.get("dataset_type"):
                return idx.query_type(inp["dataset_type"])
            return []
        except Exception:
            return []

    def _entity_compare(self, inp: dict) -> dict:
        try:
            from scientra.datasets.intelligence import DatasetComparisonEngine
            return DatasetComparisonEngine(self.root).compare_entity(inp.get("entity_text", ""))
        except Exception:
            return {}

    def _evidence_search(self, inp: dict, top_k: int) -> list:
        try:
            from scientra.cross_asset_query import CrossAssetQueryEngine, make_query
            q = make_query(query=inp.get("query", ""), paper_id=inp.get("paper_id", ""), top_k=top_k,
                           asset_types=["evidence"], use_vector=False, use_graph=False)
            return CrossAssetQueryEngine(self.root).query(q).get("hits", [])[:top_k]
        except Exception:
            return []

    def _gap_search(self, inp: dict, top_k: int) -> list:
        try:
            from scientra.cross_asset_query.cross_asset_input_loader import CrossAssetInputLoader
            loader = CrossAssetInputLoader(self.root)
            data = loader.load_all()
            gaps = data.get("gap", [])
            q = inp.get("query", "").lower()
            return [g for g in gaps if q in g.get("title", "").lower() or q in g.get("text", "").lower()][:top_k]
        except Exception:
            return []

    def _hypothesis_search(self, inp: dict, top_k: int) -> list:
        try:
            from scientra.cross_asset_query.cross_asset_input_loader import CrossAssetInputLoader
            loader = CrossAssetInputLoader(self.root)
            data = loader.load_all()
            hyps = data.get("hypothesis", [])
            q = inp.get("query", "").lower()
            return [h for h in hyps if q in h.get("title", "").lower() or q in h.get("text", "").lower()][:top_k]
        except Exception:
            return []

    def _opportunity_search(self, inp: dict, top_k: int) -> list:
        try:
            import json
            p = self.root / "05_Knowledge/research_opportunities/opportunity_ranking.json"
            if not p.exists():
                return []
            ops = json.loads(p.read_text(encoding="utf-8"))
            items = ops if isinstance(ops, list) else ops.get("opportunities", [])
            q = inp.get("query", "").lower()
            return [o for o in items if isinstance(o, dict) and (q in str(o).lower())][:top_k]
        except Exception:
            return []
