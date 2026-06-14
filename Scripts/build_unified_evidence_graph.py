#!/usr/bin/env python
"""Build Unified Evidence Graph (P5.1) — Storage Layout v3.

Usage:
    python Scripts/build_unified_evidence_graph.py --verbose
    python Scripts/build_unified_evidence_graph.py --validate --export-graphml
    python Scripts/build_unified_evidence_graph.py --embed-nodes
    python Scripts/build_unified_evidence_graph.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="Build Unified Evidence Graph (P5.1)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--validate", action="store_true")
    p.add_argument("--export-json", action="store_true", default=True)
    p.add_argument("--export-graphml", action="store_true")
    p.add_argument("--export-cyjs", action="store_true")
    p.add_argument("--embed-nodes", action="store_true")
    args = p.parse_args()

    if args.dry_run:
        print("=" * 60)
        print("  DRY RUN — Unified Evidence Graph P5.1")
        print("=" * 60)
        print(f"  Validate: {args.validate}  Embed: {args.embed_nodes}")
        print(f"  Exports: JSON={args.export_json} GraphML={args.export_graphml} CyJS={args.export_cyjs}")
        print(f"  Output: 05_Knowledge/unified_evidence_graph/")
        print()
        return 0

    from scientra.knowledge.unified_graph import GraphBuilder

    print("=" * 60)
    print("  Unified Evidence Graph — P5.1 (Storage Layout v3)")
    print("=" * 60)
    print(f"  Validate: {args.validate}  Embed: {args.embed_nodes}")

    builder = GraphBuilder(embed=args.embed_nodes)
    result = builder.build(force=args.force, export_graphml=args.export_graphml, export_cyjs=args.export_cyjs)

    if result.get("success"):
        print(f"  Nodes: {result.get('total_nodes', 0)}  Edges: {result.get('total_edges', 0)}")
        print(f"  Papers: {result.get('paper_count', 0)}")
        if args.verbose:
            print(f"  Node types: {result.get('node_types', {})}")
            print(f"  Edge types: {result.get('edge_types', {})}")
        v = result.get("validation", {})
        if v and args.validate:
            print(f"  Validation: errors={v.get('errors', 0)} warnings={v.get('warnings', 0)}")
    else:
        print(f"  Error: {result.get('error', 'Unknown')}")

    for w in builder.warnings[:10]:
        print(f"  ⚠ {w}")
    print(f"\n  Output: 05_Knowledge/unified_evidence_graph/")
    print()
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
