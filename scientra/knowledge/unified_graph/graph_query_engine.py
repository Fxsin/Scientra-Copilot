"""Graph Query Engine — query unified evidence graph nodes and edges."""

from __future__ import annotations

from typing import Any


class GraphQueryEngine:
    """Query the unified evidence graph."""

    def __init__(self, nodes: list[dict], edges: list[dict]) -> None:
        self.nodes = nodes
        self.edges = edges
        self._node_index = {n["node_id"]: n for n in nodes}
        self._adj_out: dict[str, list[dict]] = {}
        self._adj_in: dict[str, list[dict]] = {}
        for e in edges:
            s = e.get("source_node_id", "")
            t = e.get("target_node_id", "")
            self._adj_out.setdefault(s, []).append(e)
            self._adj_in.setdefault(t, []).append(e)

    def get_node(self, node_id: str) -> dict | None:
        return self._node_index.get(node_id)

    def get_neighborhood(self, node_id: str, depth: int = 1) -> dict[str, Any]:
        visited: set[str] = set()
        queue = [(node_id, 0)]
        result_nodes: list[dict] = []
        result_edges: list[dict] = []

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)
            node = self._node_index.get(current)
            if node:
                result_nodes.append(node)

            for e in self._adj_out.get(current, []) + self._adj_in.get(current, []):
                neighbor = e.get("target_node_id") if e.get("source_node_id") == current else e.get("source_node_id")
                if neighbor not in visited:
                    queue.append((neighbor, d + 1))
                if e not in result_edges:
                    result_edges.append(e)

        return {"node_id": node_id, "depth": depth, "nodes": result_nodes, "edges": result_edges}

    def get_paper_subgraph(self, paper_id: str) -> dict[str, Any]:
        p_nodes = [n for n in self.nodes if n.get("paper_id") == paper_id]
        p_ids = {n["node_id"] for n in p_nodes}
        p_edges = [e for e in self.edges if e.get("source_node_id") in p_ids or e.get("target_node_id") in p_ids]
        return {"paper_id": paper_id, "nodes": p_nodes, "edges": p_edges}

    def get_claim_support_chain(self, claim_node_id: str) -> dict[str, Any]:
        result_nodes: list[dict] = []
        result_edges: list[dict] = []
        visited: set[str] = set()

        # Walk backward: claim → supporting evidence → linked assets
        queue = [claim_node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            node = self._node_index.get(current)
            if node:
                result_nodes.append(node)

            for e in self._adj_in.get(current, []):
                if e.get("edge_type", "").startswith("evidence_supports") or e.get("edge_type", "").startswith("figure_supports") or e.get("edge_type", "").startswith("table_supports"):
                    prev = e.get("source_node_id")
                    if prev not in visited:
                        queue.append(prev)
                    result_edges.append(e)

            # Also walk forward to linked assets
            for e in self._adj_out.get(current, []):
                if "linked_to" in e.get("edge_type", ""):
                    nxt = e.get("target_node_id")
                    if nxt not in visited:
                        queue.append(nxt)
                    result_edges.append(e)

        return {"claim_node_id": claim_node_id, "nodes": result_nodes, "edges": result_edges}

    def get_gap_hypothesis_chain(self, gap_node_id: str) -> dict[str, Any]:
        result_nodes: list[dict] = []
        result_edges: list[dict] = []
        visited: set[str] = set()

        queue = [gap_node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            node = self._node_index.get(current)
            if node:
                result_nodes.append(node)

            # Walk to hypotheses addressing this gap
            for e in self._adj_in.get(current, []):
                if e.get("edge_type") == "hypothesis_addresses_gap":
                    hyp = e.get("source_node_id")
                    if hyp not in visited:
                        queue.append(hyp)
                    result_edges.append(e)
            # Walk to evidence supporting hypotheses
            for e in self._adj_out.get(current, []):
                if "supported_by" in e.get("edge_type", ""):
                    ev = e.get("target_node_id")
                    if ev not in visited:
                        queue.append(ev)
                    result_edges.append(e)

        return {"gap_node_id": gap_node_id, "nodes": result_nodes, "edges": result_edges}

    def search(self, keyword: str = "", node_type: str = "", paper_id: str = "", min_confidence: float = 0.0, limit: int = 100) -> list[dict]:
        results = []
        for n in self.nodes:
            if node_type and n.get("node_type") != node_type:
                continue
            if paper_id and n.get("paper_id") != paper_id:
                continue
            if n.get("confidence", 0) < min_confidence:
                continue
            if keyword:
                kw = keyword.lower()
                if kw not in n.get("title", "").lower() and kw not in n.get("text", "").lower():
                    continue
            results.append(n)
        return results[:limit]

    def get_stats(self) -> dict[str, Any]:
        node_types: dict[str, int] = {}
        edge_types: dict[str, int] = {}
        papers: set[str] = set()
        for n in self.nodes:
            node_types[n.get("node_type", "?")] = node_types.get(n.get("node_type", "?"), 0) + 1
            if n.get("paper_id"):
                papers.add(n["paper_id"])
        for e in self.edges:
            edge_types[e.get("edge_type", "?")] = edge_types.get(e.get("edge_type", "?"), 0) + 1
        return {
            "total_nodes": len(self.nodes), "total_edges": len(self.edges),
            "paper_count": len(papers), "node_types": node_types, "edge_types": edge_types,
        }
