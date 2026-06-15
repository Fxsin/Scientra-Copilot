#!/usr/bin/env python
"""P6.1 Export Dashboard. Usage:
    python Scripts/export_quality_dashboard.py --markdown --csv
    python Scripts/export_quality_dashboard.py --json --output-dir 09_Exports/quality_dashboard
"""

from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> int:
    p = argparse.ArgumentParser(description="Export Quality Dashboard (P6.1)")
    p.add_argument("--json", action="store_true"); p.add_argument("--markdown", action="store_true"); p.add_argument("--csv", action="store_true")
    p.add_argument("--output-dir", default="09_Exports/quality_dashboard"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    from scientra.validation.dashboard import DashboardDataLoader, DashboardAggregator, PaperQualityTableBuilder, RecommendationViewBuilder, DashboardExporter
    loader = DashboardDataLoader()
    if not loader.is_available():
        print("No P6.0 validation data. Run: python Scripts/run_e2e_validation.py --all --verbose"); return 1

    data = loader.load_all()
    agg = DashboardAggregator()
    result = agg.aggregate(data)
    papers = data.get("paper_details") or []
    recs_data = data.get("recommendations") or {}
    recs = RecommendationViewBuilder().build(recs_data)

    exporter = DashboardExporter(args.output_dir)
    paths = exporter.export(result["summary"], result["pipeline_health"], papers, recs, fmt_json=args.json, fmt_md=args.markdown, fmt_csv=args.csv)
    if args.verbose:
        for fmt, path in paths.items(): print(f"  {fmt}: {path}")
    print(f"Exported to {args.output_dir}")
    return 0

if __name__ == "__main__": sys.exit(main())
