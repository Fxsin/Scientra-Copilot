from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


try:
    from scientra.tags import (
        TAG_ENGINE_VERSION,
        retag_all,
        retag_by_category,
        retag_by_tag,
    )
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from scientra.tags import (  # type: ignore
        TAG_ENGINE_VERSION,
        retag_all,
        retag_by_category,
        retag_by_tag,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retag Scientra Copilot papers without regenerating summaries or embeddings.",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--all", action="store_true", help="Retag all discovered papers.")
    selector.add_argument("--category", help="Retag one ontology category.")
    selector.add_argument("--tag", help="Retag one configured tag.")

    parser.add_argument("--changed-only", action="store_true", help="Retag only papers whose versions, config hashes, or sources changed.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ontology-path", type=Path, default=None)
    parser.add_argument("--dictionary-path", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=None)
    parser.add_argument("--sqlite-path", type=Path, default=None)
    parser.add_argument("--lancedb-dir", type=Path, default=None)
    parser.add_argument("--no-sqlite", action="store_true", help="Do not update SQLite tag tables.")
    parser.add_argument("--no-lancedb", action="store_true", help="Do not update LanceDB metadata.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    common = {
        "root": args.root,
        "changed_only": args.changed_only,
        "ontology_path": args.ontology_path,
        "dictionary_path": args.dictionary_path,
        "output_dir": args.output_dir,
        "report_dir": args.report_dir,
        "update_sqlite": not args.no_sqlite,
        "update_lancedb": not args.no_lancedb,
        "sqlite_path": args.sqlite_path,
        "lancedb_dir": args.lancedb_dir,
    }

    try:
        if args.category:
            result = retag_by_category(args.category, **common)
        elif args.tag:
            result = retag_by_tag(args.tag, **common)
        else:
            result = retag_all(**common)
    except Exception as exc:
        print(f"retag failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Scientra Copilot Tag Engine")
        print(f"tag_engine_version: {TAG_ENGINE_VERSION}")
        print(f"tag_schema_version: {result['tag_schema_version']}")
        print(f"tag_dictionary_version: {result['tag_dictionary_version']}")
        print(f"total_papers: {result['total_papers']}")
        print(f"processed_papers: {result['processed_papers']}")
        print(f"skipped_papers: {result['skipped_papers']}")
        print(f"error_papers: {result['error_papers']}")
        print(f"report_path: {result['report_path']}")
        print("summary_regenerated: false")
        print("embedding_regenerated: false")
        print("llm_used: false")

    return 1 if result.get("error_papers") else 0


if __name__ == "__main__":
    raise SystemExit(main())

