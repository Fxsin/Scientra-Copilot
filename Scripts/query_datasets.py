#!/usr/bin/env python
"""Query Datasets (P5.3). Usage:
    python Scripts/query_datasets.py --entity MAP2K4
    python Scripts/query_datasets.py --dataset-type differential_expression --json
"""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    p = argparse.ArgumentParser(description="Query Datasets (P5.3)")
    p.add_argument("--entity"); p.add_argument("--dataset-type")
    p.add_argument("--paper-id"); p.add_argument("--top-k", type=int, default=20); p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.entity:
        from scientra.datasets.intelligence import DatasetComparisonEngine
        engine = DatasetComparisonEngine()
        result = engine.compare_entity(args.entity)
        if args.json: print(json.dumps(result, ensure_ascii=False, indent=2))
        else: print(f"Entity '{args.entity}' found in {result['found_in_papers']} paper(s).")
    elif args.dataset_type:
        from scientra.datasets.intelligence import CrossPaperDatasetIndexer
        idx = CrossPaperDatasetIndexer()
        results = idx.query_type(args.dataset_type)
        if args.json: print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for r in results[:args.top_k]: print(f"  {r.get('paper_id', '')}: {r.get('n_rows', 0)}×{r.get('n_columns', 0)}")
    elif args.paper_id:
        from scientra.datasets.intelligence import DatasetIntelligenceRunner
        runner = DatasetIntelligenceRunner()
        result = runner.get_cards(args.paper_id)
        if args.json: print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for c in result.get("datasets", []): print(f"  {c.get('dataset_type', '?')}: {c.get('n_rows', 0)}×{c.get('n_columns', 0)}")
    else:
        print("Use --entity, --dataset-type, or --paper-id"); return 1
    return 0


if __name__ == "__main__": sys.exit(main())
