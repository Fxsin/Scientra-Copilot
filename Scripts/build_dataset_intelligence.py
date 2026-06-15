#!/usr/bin/env python
"""Build Dataset Intelligence (P5.3). Usage:
    python Scripts/build_dataset_intelligence.py --paper-id paper_xxxxx --verbose
    python Scripts/build_dataset_intelligence.py --all --sample-rows 100
    python Scripts/build_dataset_intelligence.py --all --build-cross-paper-index
"""

from __future__ import annotations

import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve_paper_ids(args) -> list[str]:
    if args.paper_id: return [args.paper_id]
    if args.all:
        from scientra.papers.paper_registry import load_paper_registry
        reg = load_paper_registry(); papers = reg if isinstance(reg, list) else reg.get("papers", {})
        return list(papers.keys()) if isinstance(papers, dict) else [p.get("paper_id", "") for p in papers if p.get("paper_id")]
    print("Error: --paper-id or --all required"); sys.exit(1)


def main() -> int:
    p = argparse.ArgumentParser(description="Build Dataset Intelligence (P5.3)")
    p.add_argument("--paper-id"); p.add_argument("--all", action="store_true")
    p.add_argument("--sample-rows", type=int, default=50); p.add_argument("--embed", action="store_true")
    p.add_argument("--build-cross-paper-index", action="store_true")
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--force", action="store_true"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    paper_ids = _resolve_paper_ids(args)

    if args.dry_run:
        print(f"DRY RUN — {len(paper_ids)} papers, sample_rows={args.sample_rows}, embed={args.embed}, cross-paper={args.build_cross_paper_index}")
        return 0

    from scientra.datasets.intelligence import DatasetIntelligenceRunner, CrossPaperDatasetIndexer
    total, total_ds = 0, 0
    for i, pid in enumerate(paper_ids):
        if args.verbose: print(f"[{i + 1}/{len(paper_ids)}] {pid}")
        runner = DatasetIntelligenceRunner(max_sample=args.sample_rows, embed=args.embed)
        r = runner.run(pid, force=args.force)
        if r.get("success"):
            total += 1; total_ds += r.get("dataset_count", 0)
            if args.verbose: print(f"  Datasets: {r.get('dataset_count', 0)}")
        elif args.verbose: print(f"  {r.get('message', 'Error')}")

    print(f"Papers: {total}  Datasets: {total_ds}")

    if args.build_cross_paper_index:
        print("Building cross-paper indexes...")
        idx = CrossPaperDatasetIndexer()
        result = idx.build_indexes()
        print(f"  Entities: {result['entity_count']}  Types: {result['type_count']}")

    return 0


if __name__ == "__main__": sys.exit(main())
