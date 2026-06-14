"""P5.1 Unified Evidence Graph.

Core modules:
  - graph_schema: Node/edge type definitions and factory functions
  - graph_input_loader: Multi-source data loader with graceful fallback
  - node_builder: Build all node types from available data
  - edge_builder: Build intra-paper and cross-paper edges
  - graph_validator: Quality and integrity checks
  - graph_query_engine: Query API (neighborhood, search, chains)
  - graph_exporter: Export to JSON/GraphML/Cytoscape.js
  - graph_summary_builder: Markdown summary generation
  - graph_builder: Full pipeline orchestrator
"""

from scientra.knowledge.unified_graph.graph_schema import make_node, make_edge, NODE_TYPES, EDGE_TYPES
from scientra.knowledge.unified_graph.graph_input_loader import GraphInputLoader
from scientra.knowledge.unified_graph.node_builder import NodeBuilder
from scientra.knowledge.unified_graph.edge_builder import EdgeBuilder
from scientra.knowledge.unified_graph.graph_validator import GraphValidator
from scientra.knowledge.unified_graph.graph_query_engine import GraphQueryEngine
from scientra.knowledge.unified_graph.graph_exporter import GraphExporter
from scientra.knowledge.unified_graph.graph_builder import GraphBuilder

__all__ = [
    "make_node", "make_edge", "NODE_TYPES", "EDGE_TYPES",
    "GraphInputLoader", "NodeBuilder", "EdgeBuilder",
    "GraphValidator", "GraphQueryEngine", "GraphExporter",
    "GraphBuilder",
]
