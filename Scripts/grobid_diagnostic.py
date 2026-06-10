from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "Scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from grobid_client import DEFAULT_GROBID_CONFIG_PATH, GrobidClient, GrobidClientError  # noqa: E402
from pdf_parser import (  # noqa: E402
    file_sha256,
    tei_to_structured_payload,
    utc_now,
    write_grobid_error,
    write_grobid_meta,
    write_json_atomic,
    write_text_atomic,
)


DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"
DEFAULT_METADATA_DIR = PROJECT_ROOT / "02_Metadata"


def run_diagnostic(
    input_path: Path,
    report_dir: Path = DEFAULT_REPORT_DIR,
    metadata_dir: Path = DEFAULT_METADATA_DIR,
    config_path: Path = DEFAULT_GROBID_CONFIG_PATH,
    grobid_url: str | None = None,
    limit: int | None = None,
    recursive: bool = True,
) -> dict[str, Any]:
    client = GrobidClient(base_url=grobid_url, config_path=config_path)
    pdfs = collect_pdfs(input_path, recursive=recursive)
    if limit is not None:
        pdfs = pdfs[:limit]

    health = client.health_status()
    results: list[dict[str, Any]] = []

    for index, pdf_path in enumerate(pdfs):
        if index > 0 and client.batch.inter_request_sleep > 0:
            time.sleep(client.batch.inter_request_sleep)
        results.append(check_pdf(pdf_path, input_path, metadata_dir, client, health))

    report = build_report(input_path, client, health, results)
    write_report(report, report_dir)
    return report


def collect_pdfs(input_path: Path, recursive: bool = True) -> list[Path]:
    input_path = input_path.resolve()
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return [input_path]
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(path for path in input_path.glob(pattern) if path.is_file())


def check_pdf(
    pdf_path: Path,
    input_path: Path,
    metadata_dir: Path,
    client: GrobidClient,
    health: dict[str, Any],
) -> dict[str, Any]:
    sha256 = file_sha256(pdf_path)
    paper_id = f"paper_{sha256[:16]}"
    artifact_dir = metadata_dir / paper_id / "grobid"
    relative_key = relative_key_for(pdf_path, input_path)
    base_result: dict[str, Any] = {
        "paper_id": paper_id,
        "pdf_path": str(pdf_path),
        "relative_key": relative_key,
        "grobid_base_url": client.base_url,
        "health_available": bool(health.get("available")),
        "health_status_code": health.get("status_code"),
        "fallback_used": False,
    }

    if not health.get("available"):
        error_text = health.get("error") or health.get("body") or "GROBID service unavailable"
        write_grobid_error(
            artifact_dir,
            pdf_path=pdf_path,
            status_code=health.get("status_code"),
            error_type="grobid_service_unavailable",
            response_text=error_text,
            attempts=0,
            fallback_used=False,
            failure_reasons=[error_text],
        )
        return {
            **base_result,
            "status": "failed",
            "http_status_code": health.get("status_code"),
            "error_type": "grobid_service_unavailable",
            "error": error_text,
            "attempts": 0,
            "tei_length": 0,
            "title": None,
            "abstract_length": 0,
            "body_length": 0,
            "references_count": 0,
        }

    try:
        response = client.process_fulltext_document(pdf_path)
    except GrobidClientError as exc:
        write_grobid_error(
            artifact_dir,
            pdf_path=pdf_path,
            status_code=exc.status_code,
            error_type=exc.error_type,
            response_text=exc.response_text or str(exc),
            attempts=exc.attempts,
            fallback_used=False,
            failure_reasons=exc.failure_reasons,
        )
        return {
            **base_result,
            "status": "failed",
            "http_status_code": exc.status_code,
            "error_type": exc.error_type,
            "error": str(exc),
            "attempts": exc.attempts,
            "tei_length": 0,
            "title": None,
            "abstract_length": 0,
            "body_length": 0,
            "references_count": 0,
        }

    write_text_atomic(artifact_dir / "fulltext.tei.xml", response.text)
    try:
        structured = tei_to_structured_payload(
            tei_xml=response.text,
            pdf_path=pdf_path,
            relative_key=relative_key,
            sha256=sha256,
            grobid_url=client.base_url,
            grobid_elapsed_seconds=response.elapsed_seconds,
        )
    except ET.ParseError as exc:
        write_grobid_error(
            artifact_dir,
            pdf_path=pdf_path,
            status_code=response.status_code,
            error_type="tei_parse_failed",
            response_text=f"{type(exc).__name__}: {exc}",
            attempts=response.attempts,
            fallback_used=False,
            failure_reasons=[f"TEI parse failed: {exc}"],
        )
        return {
            **base_result,
            "status": "failed",
            "http_status_code": response.status_code,
            "error_type": "tei_parse_failed",
            "error": str(exc),
            "attempts": response.attempts,
            "tei_length": len(response.text),
            "title": None,
            "abstract_length": 0,
            "body_length": 0,
            "references_count": 0,
        }

    write_grobid_meta(artifact_dir, pdf_path, response, structured, client)
    body_length = sum(len(section.get("text", "")) for section in structured.get("sections", []))
    return {
        **base_result,
        "status": "succeeded",
        "http_status_code": response.status_code,
        "error_type": None,
        "error": None,
        "attempts": response.attempts,
        "elapsed_seconds": round(response.elapsed_seconds, 3),
        "tei_length": len(response.text),
        "title": structured.get("metadata", {}).get("title"),
        "abstract_length": len(structured.get("abstract") or ""),
        "body_length": body_length,
        "references_count": len(structured.get("references", [])),
        "tei_path": str(artifact_dir / "fulltext.tei.xml"),
        "grobid_meta_path": str(artifact_dir / "grobid_meta.json"),
    }


def relative_key_for(pdf_path: Path, input_path: Path) -> str:
    input_path = input_path.resolve()
    try:
        base = input_path if input_path.is_dir() else input_path.parent
        return pdf_path.resolve().relative_to(base).as_posix()
    except ValueError:
        return pdf_path.name


def build_report(
    input_path: Path,
    client: GrobidClient,
    health: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(results)
    success = sum(1 for item in results if item.get("status") == "succeeded")
    failures = total - success
    by_error: dict[str, int] = {}
    for item in results:
        error_type = item.get("error_type")
        if error_type:
            by_error[str(error_type)] = by_error.get(str(error_type), 0) + 1
    return {
        "generated_at": utc_now(),
        "input_path": str(input_path.resolve()),
        "grobid_base_url": client.base_url,
        "health": health,
        "request": {
            "consolidateHeader": int(client.request.consolidate_header),
            "consolidateCitations": int(client.request.consolidate_citations),
            "includeRawCitations": int(client.request.include_raw_citations),
            "includeRawAffiliations": int(client.request.include_raw_affiliations),
        },
        "timeout": {
            "connect": client.timeout.connect,
            "read": client.timeout.read,
            "total": client.timeout.total,
        },
        "retry": {
            "max_attempts": client.retry.max_attempts,
            "backoff_seconds": list(client.retry.backoff_seconds),
        },
        "batch": {
            "max_workers": client.batch.concurrency,
            "inter_request_sleep": client.batch.inter_request_sleep,
        },
        "total_pdf_count": total,
        "grobid_fulltext_success": success,
        "grobid_fulltext_failed": failures,
        "grobid_fulltext_success_rate": round(success / total, 4) if total else 0.0,
        "error_distribution": by_error,
        "papers": results,
    }


def write_report(report: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "grobid_diagnostic_report.json"
    md_path = report_dir / "grobid_diagnostic_report.md"
    write_json_atomic(json_path, report)
    lines = [
        "# GROBID Diagnostic Report",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- input_path: {report['input_path']}",
        f"- grobid_base_url: {report['grobid_base_url']}",
        f"- health_available: {report['health'].get('available')}",
        f"- health_status_code: {report['health'].get('status_code')}",
        f"- total_pdf_count: {report['total_pdf_count']}",
        f"- grobid_fulltext_success: {report['grobid_fulltext_success']}",
        f"- grobid_fulltext_failed: {report['grobid_fulltext_failed']}",
        f"- grobid_fulltext_success_rate: {report['grobid_fulltext_success_rate']}",
        "",
        "## Request Settings",
        "",
        f"- consolidateHeader: {report['request']['consolidateHeader']}",
        f"- consolidateCitations: {report['request']['consolidateCitations']}",
        f"- max_workers: {report['batch']['max_workers']}",
        f"- request_interval_seconds: {report['batch']['inter_request_sleep']}",
        f"- timeout_read_seconds: {report['timeout']['read']}",
        f"- retry_backoff_seconds: {report['retry']['backoff_seconds']}",
        "",
        "## Error Distribution",
        "",
    ]
    if report["error_distribution"]:
        for key, count in sorted(report["error_distribution"].items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Per Paper", ""])
    lines.append("| PDF | Status | HTTP | TEI Length | Title | Abstract Chars | Body Chars | Refs | Attempts | Error Type | Fallback |")
    lines.append("|---|---|---:|---:|---|---:|---:|---:|---:|---|---|")
    for item in report["papers"]:
        lines.append(
            "| {pdf} | {status} | {http} | {tei} | {title} | {abstract} | {body} | {refs} | {attempts} | {error_type} | {fallback} |".format(
                pdf=Path(item["pdf_path"]).name.replace("|", "\\|"),
                status=item.get("status") or "",
                http=item.get("http_status_code") or "",
                tei=item.get("tei_length") or 0,
                title=(item.get("title") or "")[:80].replace("|", "\\|"),
                abstract=item.get("abstract_length") or 0,
                body=item.get("body_length") or 0,
                refs=item.get("references_count") or 0,
                attempts=item.get("attempts") or 0,
                error_type=item.get("error_type") or "",
                fallback=item.get("fallback_used"),
            )
        )
    write_text_atomic(md_path, "\n".join(lines) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a GROBID-only PDF diagnostic. No fallback is used.")
    parser.add_argument("--input", dest="input_path", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--grobid-config", type=Path, default=DEFAULT_GROBID_CONFIG_PATH)
    parser.add_argument("--grobid-url", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = run_diagnostic(
        input_path=args.input_path,
        report_dir=args.report_dir,
        metadata_dir=args.metadata_dir,
        config_path=args.grobid_config,
        grobid_url=args.grobid_url,
        limit=args.limit,
        recursive=not args.no_recursive,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"report_md: {args.report_dir / 'grobid_diagnostic_report.md'}")
        print(f"report_json: {args.report_dir / 'grobid_diagnostic_report.json'}")
        print(f"grobid_fulltext_success_rate: {report['grobid_fulltext_success_rate']}")
    return 0 if report["grobid_fulltext_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
