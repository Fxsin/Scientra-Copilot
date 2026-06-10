from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scientra.embedding import (  # noqa: E402
        DEFAULT_DRY_RUN_REPORT_PATH,
        DEFAULT_EMBEDDING_CONFIG_PATH,
        DEFAULT_EMBEDDING_STATUS_PATH,
        DEFAULT_REAL_RUN_REPORT_PATH,
        EMBEDDING_ENGINE_VERSION,
        run_embedding_dry_run,
        run_embedding_real_run,
    )
except ModuleNotFoundError:
    from scientra.embedding import (  # type: ignore  # noqa: E402
        DEFAULT_DRY_RUN_REPORT_PATH,
        DEFAULT_EMBEDDING_CONFIG_PATH,
        DEFAULT_EMBEDDING_STATUS_PATH,
        DEFAULT_REAL_RUN_REPORT_PATH,
        EMBEDDING_ENGINE_VERSION,
        run_embedding_dry_run,
        run_embedding_real_run,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Scientra Copilot embeddings. P6 currently supports a no-write dry-run.",
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_EMBEDDING_CONFIG_PATH)
    parser.add_argument("--batch", default="batch_5")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--status-db", type=Path, default=DEFAULT_EMBEDDING_STATUS_PATH)
    parser.add_argument("--batch-size", type=int, default=8)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate inputs without model loading or LanceDB writes.")
    mode.add_argument("--real-run", action="store_true", help="Load BGE-M3, generate embeddings, and write LanceDB.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.real_run:
        report = run_embedding_real_run(
            root=args.root,
            config_path=args.config,
            batch_name=args.batch,
            report_path=args.report or DEFAULT_REAL_RUN_REPORT_PATH,
            status_path=args.status_db,
            batch_size=args.batch_size,
        )
        mode = "real_run"
    else:
        report = run_embedding_dry_run(
            root=args.root,
            config_path=args.config,
            batch_name=args.batch,
            report_path=args.report or DEFAULT_DRY_RUN_REPORT_PATH,
        )
        mode = "dry_run"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Scientra Copilot Embedding Engine")
        print(f"embedding_engine_version: {EMBEDDING_ENGINE_VERSION}")
        print(f"mode: {mode}")
        if mode == "real_run":
            print(f"paper_count: {report['paper_count']}")
            print(f"metadata_embeddings: {report['metadata_embedding_count']}")
            print(f"summary_embeddings: {report['summary_embedding_count']}")
            print(f"chunk_embeddings: {report['chunk_embedding_count']}")
            print(f"lancedb_path: {report['lancedb_path']}")
            print(f"table_record_counts: {json.dumps(report['table_record_counts'], ensure_ascii=False)}")
            print(f"recommend_p7_query_api: {str(report['recommend_p7_query_api']).lower()}")
            print(f"report_path: {report['report_path']}")
            print(f"status_path: {report['status_path']}")
        else:
            print(f"checked_papers: {report['checked_papers']}")
            print(f"passed_papers: {report['passed_papers']}")
            print(f"failed_papers: {report['failed_papers']}")
            print(f"all_passed: {str(report['all_passed']).lower()}")
            print(f"recommend_real_run: {str(report['recommend_real_run']).lower()}")
            print(f"report_path: {report['report_path']}")
            print("bge_model_loaded: false")
            print("lancedb_written: false")

    if mode == "real_run":
        return 0 if report["recommend_p7_query_api"] else 1
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
