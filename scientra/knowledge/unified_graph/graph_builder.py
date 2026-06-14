"""Graph Builder — orchestrator for unified evidence graph construction.

Stages:
  1. Load all data sources
  2. Build nodes per paper
  3. Build edges per paper
  4. Build global edges (cross-paper)
  5. Validate graph
  6. Write outputs to 05_Knowledge/unified_evidence_graph/
  7. Optional: export formats, embed nodes
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.knowledge.unified_graph.graph_input_loader import GraphInputLoader
from scientra.knowledge.unified_graph.node_builder import NodeBuilder
from scientra.knowledge.unified_graph.edge_builder import EdgeBuilder
from scientra.knowledge.unified_graph.graph_validator import GraphValidator
from scientra.knowledge.unified_graph.graph_query_engine import GraphQueryEngine
from scientra.knowledge.unified_graph.graph_exporter import GraphExporter
from scientra.knowledge.unified_graph.graph_summary_builder import build_summary_md

V3_OUTPUT = "05_Knowledge/unified_evidence_graph"
V3_LANCEDB = "06_Index/vector/lancedb"


class GraphBuilder:
    """Orchestrate unified evidence graph construction."""

    def __init__(self, root: str | Path | None = None, embed: bool = False) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.embed = embed
        self.warnings: list[str] = []

    def build(self, force: bool = False, export_json: bool = True,
              export_graphml: bool = False, export_cyjs: bool = False) -> dict[str, Any]:
        """Build the full unified evidence graph."""
        out_dir = self.root / V3_OUTPUT
        nodes_path = out_dir / "graph_nodes.json"
        edges_path = out_dir / "graph_edges.json"

        if not force and nodes_path.exists() and edges_path.exists():
            try:
                nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
                edges = json.loads(edges_path.read_text(encoding="utf-8"))
                engine = GraphQueryEngine(nodes, edges)
                return {"success": True, "cached": True, **engine.get_stats()}
            except Exception:
                pass

        # Stage 1: Load data
        loader = GraphInputLoader(self.root)
        all_data = loader.load_all()
        registry = all_data.get("paper_registry", {})
        papers = registry if isinstance(registry, list) else registry.get("papers", {})
        if not papers:
            return {"success": False, "error": "Paper registry empty.", "warnings": self.warnings}

        # Stage 2-3: Build per-paper nodes + edges
        all_nodes: list[dict] = []
        all_edges: list[dict] = []
        nb = NodeBuilder(self.warnings)
        eb = EdgeBuilder(self.warnings)

        # Process in batches for large libraries
        paper_list = list(papers.keys()) if isinstance(papers, dict) else [p.get("paper_id", "") for p in (papers if isinstance(papers, list) else [])]
        paper_list = [p for p in paper_list if p]

        for pid in paper_list:
            paper_data = loader.load_paper(pid)
            if not paper_data.get("paper_meta"):
                continue
            p_nodes = nb.build_all(paper_data)
            p_edges = eb.build_all(paper_data, p_nodes)
            all_nodes.extend(p_nodes)
            all_edges.extend(p_edges)

            # Write paper subgraph
            sub_dir = out_dir / "paper_subgraphs"
            sub_dir.mkdir(parents=True, exist_ok=True)
            sub_dir.joinpath(f"{pid}.json").write_text(
                json.dumps({"paper_id": pid, "nodes": p_nodes, "edges": p_edges}, ensure_ascii=False, indent=2),
                encoding="utf-8")

        # Stage 4: Global edges
        global_edges = eb.build_global_edges(all_nodes, all_data.get("gap_clusters", []), all_data.get("hypothesis_clusters", []))
        all_edges.extend(global_edges)

        # Deduplicate edges
        seen_eids = set()
        unique_edges = []
        for e in all_edges:
            eid = e.get("edge_id", "")
            if eid not in seen_eids:
                seen_eids.add(eid)
                unique_edges.append(e)
        all_edges = unique_edges

        # Stage 5: Validate
        validator = GraphValidator()
        validation = validator.validate(all_nodes, all_edges)

        # Stage 6: Write outputs
        out_dir.mkdir(parents=True, exist_ok=True)
        self._wj(nodes_path, all_nodes)
        self._wj(edges_path, all_edges)
        self._wj(out_dir / "graph_index.json", {n["node_id"]: n.get("node_type") for n in all_nodes})

        # Stats
        engine = GraphQueryEngine(all_nodes, all_edges)
        stats = engine.get_stats()
        stats["generated_at"] = datetime.now(timezone.utc).isoformat()
        stats["validation"] = {"valid": validation["valid"], "errors": validation["error_count"], "warnings": validation["warning_count"], "orphans": validation["orphan_count"]}
        self._wj(out_dir / "graph_stats.json", stats)

        # Summary
        build_summary_md(all_nodes, all_edges, validation, out_dir / "unified_evidence_graph_summary.md")

        # Stage 7: Exports
        if export_json or export_graphml or export_cyjs:
            exporter = GraphExporter(all_nodes, all_edges, out_dir / "exports")
            exporter.export_all(export_json, export_graphml, export_cyjs)

        # Stage 8: Optional embedding
        if self.embed:
            try:
                self._embed_nodes(all_nodes)
            except Exception:
                self.warnings.append("Node embedding failed — graph built successfully without embeddings.")

        return {"success": True, "cached": False, "warnings": self.warnings, **stats}

    def _embed_nodes(self, nodes: list[dict]) -> None:
        try:
            import lancedb
            db = lancedb.connect(str(self.root / V3_LANCEDB))
            data = [{
                "node_id": n.get("node_id", ""), "node_type": n.get("node_type", ""),
                "paper_id": n.get("paper_id", ""), "title": n.get("title", ""),
                "text": n.get("text", "")[:2000],
                "source_module": n.get("provenance", {}).get("source_module", ""),
                "source_relative_path": ";".join(n.get("source_paths", [])),
                "confidence": n.get("confidence", 0),
                "vector": _compute_vec(n.get("title", "") + " " + n.get("text", "")),
            } for n in nodes if n.get("text") and len(n.get("text", "")) > 50]
            if data:
                try:
                    db.open_table("knowledge_graph_nodes").add(data)
                except Exception:
                    db.create_table("knowledge_graph_nodes", data)
        except Exception:
            raise

    @staticmethod
    def _wj(p: Path, d: Any) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _compute_vec(text: str) -> list[float] | None:
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("BAAI/bge-m3").encode(text[:8192]).tolist()
    except Exception:
        return None
