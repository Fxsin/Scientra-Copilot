"""Graph Exporter — export unified graph to JSON, GraphML, Cytoscape.js formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GraphExporter:
    """Export graph in multiple formats."""

    def __init__(self, nodes: list[dict], edges: list[dict], output_dir: str | Path) -> None:
        self.nodes = nodes
        self.edges = edges
        self.output_dir = Path(output_dir)

    def export_all(self, json_f: bool = True, graphml: bool = False, cyjs: bool = False) -> dict[str, str]:
        results: dict[str, str] = {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if json_f:
            p = self.output_dir / "unified_evidence_graph.json"
            self._export_json(p)
            results["json"] = str(p)

        if graphml:
            p = self.output_dir / "unified_evidence_graph.graphml"
            self._export_graphml(p)
            results["graphml"] = str(p)

        if cyjs:
            p = self.output_dir / "unified_evidence_graph.cyjs"
            self._export_cyjs(p)
            results["cyjs"] = str(p)

        return results

    def _export_json(self, path: Path) -> None:
        data = {"nodes": self.nodes, "edges": self.edges}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _export_graphml(self, path: Path) -> None:
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                  '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
                  '<graph id="G" edgedefault="directed">']
        for n in self.nodes:
            title = (n.get("title", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
            ntype = n.get("node_type", "unknown")
            lines.append(f'<node id="{n["node_id"]}"><data key="title">{title}</data><data key="type">{ntype}</data></node>')
        for e in self.edges:
            etype = e.get("edge_type", "unknown")
            lines.append(f'<edge id="{e["edge_id"]}" source="{e["source_node_id"]}" target="{e["target_node_id"]}"><data key="type">{etype}</data></edge>')
        lines.append('</graph></graphml>')
        path.write_text("\n".join(lines), encoding="utf-8")

    def _export_cyjs(self, path: Path) -> None:
        cy_nodes = [{"data": {"id": n["node_id"], "label": n.get("title", "")[:80], "type": n.get("node_type", ""), "paper_id": n.get("paper_id", "")}} for n in self.nodes]
        cy_edges = [{"data": {"id": e["edge_id"], "source": e["source_node_id"], "target": e["target_node_id"], "type": e.get("edge_type", ""), "confidence": e.get("confidence", 0)}} for e in self.edges]
        data = {"elements": {"nodes": cy_nodes, "edges": cy_edges}}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
