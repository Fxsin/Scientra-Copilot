"""Graph Validator — check graph quality and integrity."""

from __future__ import annotations

from typing import Any

from scientra.knowledge.unified_graph.graph_schema import NODE_TYPES, EDGE_TYPES


class GraphValidator:
    """Validate unified evidence graph quality."""

    def validate(self, nodes: list[dict], edges: list[dict]) -> dict[str, Any]:
        node_ids = {n["node_id"] for n in nodes}
        issues: list[dict] = []
        warnings: list[str] = []

        # Check orphan nodes
        referenced = set()
        for e in edges:
            referenced.add(e.get("source_node_id", ""))
            referenced.add(e.get("target_node_id", ""))
        for n in nodes:
            nid = n["node_id"]
            if nid not in referenced and n.get("node_type") != "paper":
                warnings.append(f"Orphan node: {nid} ({n.get('node_type')})")
                issues.append({"type": "orphan_node", "node_id": nid})

        # Check duplicate nodes
        seen: dict[str, list[str]] = {}
        for n in nodes:
            key = f"{n.get('node_type')}:{n.get('title', '')[:50]}"
            seen.setdefault(key, []).append(n["node_id"])
        for key, nids in seen.items():
            if len(nids) > 1:
                warnings.append(f"Duplicate node: {key} ({len(nids)} copies)")
                issues.append({"type": "duplicate_node", "key": key, "count": len(nids)})

        # Check invalid edge references
        for e in edges:
            if e.get("source_node_id") not in node_ids:
                issues.append({"type": "invalid_source", "edge_id": e.get("edge_id")})
            if e.get("target_node_id") not in node_ids:
                issues.append({"type": "invalid_target", "edge_id": e.get("edge_id")})

        # Check unsupported types
        for n in nodes:
            if n.get("node_type") not in NODE_TYPES:
                issues.append({"type": "unsupported_node_type", "node_id": n["node_id"], "node_type": n.get("node_type")})
        for e in edges:
            if e.get("edge_type") not in EDGE_TYPES:
                issues.append({"type": "unsupported_edge_type", "edge_id": e.get("edge_id"), "edge_type": e.get("edge_type")})

        # Check missing provenance
        for n in nodes:
            if not n.get("provenance"):
                issues.append({"type": "missing_provenance", "node_id": n["node_id"]})
        for e in edges:
            if not e.get("provenance"):
                issues.append({"type": "missing_provenance", "edge_id": e.get("edge_id")})

        # Check low confidence
        for e in edges:
            if e.get("confidence", 0) < 0.3:
                issues.append({"type": "low_confidence_edge", "edge_id": e.get("edge_id"), "confidence": e.get("confidence")})

        # Check missing paper_id
        for n in nodes:
            if not n.get("paper_id"):
                issues.append({"type": "missing_paper_id", "node_id": n["node_id"]})

        error_count = sum(1 for i in issues if i["type"] in ("invalid_source", "invalid_target", "unsupported_node_type", "unsupported_edge_type"))
        warn_count = len(issues) - error_count

        return {
            "valid": error_count == 0,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "error_count": error_count,
            "warning_count": warn_count,
            "total_issues": len(issues),
            "issues": issues,
            "warnings": warnings,
            "orphan_count": sum(1 for i in issues if i["type"] == "orphan_node"),
        }
