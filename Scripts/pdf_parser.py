from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from grobid_client import (
    DEFAULT_GROBID_CONFIG_PATH,
    GrobidClient,
    GrobidClientError,
    load_grobid_config,
)

try:
    import yaml
except Exception:  # pragma: no cover - PyYAML is part of the target stack.
    yaml = None

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal environments
    import logging

    class _LoggerCompat:
        def __init__(self) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
            self._logger = logging.getLogger("scientra.pdf_parser")

        def remove(self) -> None:
            return None

        def add(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def info(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.info(_format_log(message, *args, **kwargs))

        def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.warning(_format_log(message, *args, **kwargs))

        def error(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.error(_format_log(message, *args, **kwargs))

        def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.exception(_format_log(message, *args, **kwargs))

    def _format_log(message: str, *args: Any, **kwargs: Any) -> str:
        try:
            return message.format(*args, **kwargs)
        except Exception:
            return message

    logger = _LoggerCompat()


PARSER_VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "01_PDF"
DEFAULT_METADATA_DIR = PROJECT_ROOT / "02_Metadata"
DEFAULT_RAW_TEXT_DIR = PROJECT_ROOT / "03_Summary" / "raw_text"
DEFAULT_LOG_DIR = PROJECT_ROOT / "07_Workflows" / "logs"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


@dataclass(frozen=True)
class ParserPaths:
    input_dir: Path
    metadata_dir: Path
    raw_text_dir: Path
    log_dir: Path
    report_dir: Path

    @property
    def papers_dir(self) -> Path:
        return self.metadata_dir / "papers"

    @property
    def tei_dir(self) -> Path:
        return self.metadata_dir / "tei"

    @property
    def yaml_root_dir(self) -> Path:
        return self.metadata_dir

    @property
    def failures_dir(self) -> Path:
        return self.metadata_dir / "failures"

    @property
    def state_path(self) -> Path:
        return self.metadata_dir / "pdf_parser_state.json"

    @property
    def failure_path(self) -> Path:
        return self.failures_dir / "pdf_parser_failures.jsonl"

    @property
    def parse_status_path(self) -> Path:
        return self.metadata_dir / "parse_status.sqlite"


@dataclass(frozen=True)
class ParserOptions:
    grobid_url: str | None
    grobid_config_path: Path
    timeout_seconds: int | None
    max_attempts: int | None
    retry_wait_seconds: float | None
    workers: int
    inter_request_sleep: float
    force: bool
    recursive: bool
    limit: int | None
    save_tei: bool
    grobid_only: bool


@dataclass(frozen=True)
class ProcessResult:
    pdf_path: Path
    status: str
    metadata_path: Path | None = None
    raw_text_path: Path | None = None
    tei_path: Path | None = None
    paper_id: str | None = None
    parser_used: str | None = None
    grobid_fulltext_status: str | None = None
    grobid_attempts: int = 0
    error_type: str | None = None
    fallback_triggered: bool = False
    error: str | None = None


class PdfParserEngine:
    def __init__(self, paths: ParserPaths, options: ParserOptions) -> None:
        self.paths = paths
        self.options = options
        self.state_lock = threading.Lock()
        self.failure_lock = threading.Lock()
        self.parse_status_lock = threading.Lock()
        self.state = self._load_state()

    def ensure_directories(self) -> None:
        for path in [
            self.paths.input_dir,
            self.paths.metadata_dir,
            self.paths.raw_text_dir,
            self.paths.log_dir,
            self.paths.report_dir,
            self.paths.papers_dir,
            self.paths.tei_dir,
            self.paths.failures_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def collect_pdfs(self) -> list[Path]:
        pattern = "**/*.pdf" if self.options.recursive else "*.pdf"
        pdfs = sorted(path for path in self.paths.input_dir.glob(pattern) if path.is_file())
        if self.options.limit is not None:
            pdfs = pdfs[: self.options.limit]
        return pdfs

    def process_batch(self) -> list[ProcessResult]:
        self.ensure_directories()
        pdfs = self.collect_pdfs()
        logger.info("Found {} PDF files in {}", len(pdfs), self.paths.input_dir)
        if not pdfs:
            return []

        workers = max(1, self.options.workers)
        if workers == 1:
            results: list[ProcessResult] = []
            for index, pdf_path in enumerate(pdfs):
                if index > 0 and self.options.inter_request_sleep > 0:
                    logger.info(
                        "Sleeping {} seconds before next GROBID request",
                        self.options.inter_request_sleep,
                    )
                    time.sleep(self.options.inter_request_sleep)
                results.append(self.process_one(pdf_path))
            return results

        results: list[ProcessResult] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self.process_one, pdf_path) for pdf_path in pdfs]
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def process_one(self, pdf_path: Path) -> ProcessResult:
        stage = "start"
        sha256 = ""
        relative_key = self._relative_key(pdf_path)
        metadata_path: Path | None = None
        raw_text_path: Path | None = None
        tei_path: Path | None = None
        parser_used: str | None = None
        grobid_base_url: str | None = None
        grobid_health_status = "not_checked"
        fallback_triggered = False
        grobid_request: dict[str, Any] = {
            "status": "not_attempted",
            "elapsed_seconds": None,
            "attempts": 0,
            "retry_count": 0,
            "failure_reasons": [],
        }
        try:
            stage = "hash"
            sha256 = file_sha256(pdf_path)
            output_base = build_output_base(relative_key, sha256)
            paper_id = f"paper_{sha256[:16]}"
            grobid_artifact_dir = self.paths.metadata_dir / paper_id / "grobid"
            metadata_path = self.paths.papers_dir / f"{output_base}.metadata.json"
            metadata_yaml_path = self.metadata_yaml_path(relative_key)
            raw_text_path = self.paths.raw_text_dir / f"{output_base}.txt"
            tei_path = grobid_artifact_dir / "fulltext.tei.xml"

            if self._can_skip(relative_key, sha256, metadata_path, raw_text_path):
                logger.info("Skipping completed PDF: {}", pdf_path)
                return ProcessResult(
                    pdf_path=pdf_path,
                    status="skipped",
                    metadata_path=metadata_path,
                    raw_text_path=raw_text_path,
                    tei_path=tei_path if tei_path.exists() else None,
                    paper_id=paper_id,
                )

            logger.info("Processing PDF: {}", pdf_path)
            client = GrobidClient(
                base_url=self.options.grobid_url,
                config_path=self.options.grobid_config_path,
                timeout_seconds=self.options.timeout_seconds,
                max_attempts=self.options.max_attempts,
                retry_wait_seconds=self.options.retry_wait_seconds,
            )
            grobid_base_url = client.base_url

            stage = "grobid_health"
            health = client.health_status()
            grobid_available = bool(health.get("available"))
            grobid_health_status = "available" if grobid_available else "unavailable"

            if grobid_available:
                parser_used = "GROBID"
                logger.info("GROBID health check succeeded at {}", client.base_url)
                stage = "grobid"
                try:
                    response = client.process_fulltext_document(pdf_path)
                except GrobidClientError as exc:
                    grobid_request = {
                        "status": "failed",
                        "elapsed_seconds": round(getattr(exc, "elapsed_seconds", 0.0) or 0.0, 3),
                        "attempts": getattr(exc, "attempts", 0),
                        "retry_count": getattr(exc, "retry_count", 0),
                        "failure_reasons": getattr(exc, "failure_reasons", []) or [str(exc)],
                        "error_type": getattr(exc, "error_type", "grobid_request_failed"),
                        "status_code": getattr(exc, "status_code", None),
                    }
                    write_grobid_error(
                        grobid_artifact_dir,
                        pdf_path=pdf_path,
                        status_code=getattr(exc, "status_code", None),
                        error_type=getattr(exc, "error_type", "grobid_request_failed"),
                        response_text=getattr(exc, "response_text", None) or str(exc),
                        attempts=getattr(exc, "attempts", 0),
                        fallback_used=not self.options.grobid_only,
                        failure_reasons=getattr(exc, "failure_reasons", []) or [str(exc)],
                    )
                    if self.options.grobid_only:
                        raise
                    parser_used = "PyMuPDF"
                    fallback_triggered = True
                    tei_path = None
                    logger.warning(
                        "GROBID fulltext failed for {}; falling back to PyMuPDF: {}",
                        pdf_path,
                        exc,
                    )
                    stage = "pymupdf"
                    structured = pymupdf_to_structured_payload(
                        pdf_path=pdf_path,
                        relative_key=relative_key,
                        sha256=sha256,
                        grobid_url=client.base_url,
                    )
                else:
                    grobid_request = {
                        "status": "succeeded",
                        "elapsed_seconds": round(response.elapsed_seconds, 3),
                        "attempts": response.attempts,
                        "retry_count": response.retry_count,
                        "failure_reasons": response.failure_reasons,
                        "error_type": None,
                        "status_code": response.status_code,
                    }
                    if self.options.save_tei:
                        write_text_atomic(tei_path, response.text)
                    else:
                        tei_path = None

                    stage = "tei_parse"
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
                            grobid_artifact_dir,
                            pdf_path=pdf_path,
                            status_code=response.status_code,
                            error_type="tei_parse_failed",
                            response_text=f"{type(exc).__name__}: {exc}",
                            attempts=response.attempts,
                            fallback_used=not self.options.grobid_only,
                            failure_reasons=[f"TEI parse failed: {exc}"],
                        )
                        if self.options.grobid_only:
                            raise
                        grobid_request["status"] = "tei_parse_failed"
                        grobid_request["error_type"] = "tei_parse_failed"
                        parser_used = "PyMuPDF"
                        fallback_triggered = True
                        tei_path = None
                        stage = "pymupdf"
                        structured = pymupdf_to_structured_payload(
                            pdf_path=pdf_path,
                            relative_key=relative_key,
                            sha256=sha256,
                            grobid_url=client.base_url,
                        )
                    else:
                        if self.options.save_tei:
                            write_grobid_meta(
                                grobid_artifact_dir,
                                pdf_path=pdf_path,
                                response=response,
                                structured=structured,
                                client=client,
                            )
            else:
                grobid_request = {
                    "status": "failed",
                    "elapsed_seconds": health.get("elapsed_seconds"),
                    "attempts": 0,
                    "retry_count": 0,
                    "failure_reasons": [health.get("error") or "GROBID service unavailable"],
                    "error_type": "grobid_service_unavailable",
                    "status_code": health.get("status_code"),
                }
                write_grobid_error(
                    grobid_artifact_dir,
                    pdf_path=pdf_path,
                    status_code=health.get("status_code"),
                    error_type="grobid_service_unavailable",
                    response_text=health.get("error") or health.get("body") or "",
                    attempts=0,
                    fallback_used=False,
                    failure_reasons=grobid_request["failure_reasons"],
                )
                logger.warning(
                    "GROBID health check failed at {}; parse is blocked until service is available",
                    client.base_url,
                )
                raise GrobidClientError(
                    f"GROBID service unavailable: {health.get('url')}: {health.get('error')}",
                    attempts=0,
                    failure_reasons=grobid_request["failure_reasons"],
                    error_type="grobid_service_unavailable",
                    status_code=health.get("status_code"),
                    response_text=health.get("error") or health.get("body") or "",
                    elapsed_seconds=health.get("elapsed_seconds"),
                )

            structured["grobid_request"] = grobid_request
            structured["parse_status"] = build_parse_status(
                status="succeeded",
                parser_used=parser_used,
                grobid_base_url=client.base_url,
                grobid_health_endpoint=client.health_endpoint,
                grobid_process_fulltext_endpoint=client.process_fulltext_endpoint,
                grobid_health_status=grobid_health_status,
                fallback_triggered=fallback_triggered,
                tei_path=tei_path,
                structured=structured,
                error=None,
            )

            stage = "raw_text"
            raw_text = build_raw_text(structured)
            write_text_atomic(raw_text_path, raw_text)

            stage = "metadata"
            structured["outputs"] = {
                "metadata_path": str(metadata_path),
                "raw_text_path": str(raw_text_path),
                "tei_path": str(tei_path) if tei_path else None,
            }
            write_json_atomic(metadata_path, structured)
            write_yaml_atomic(metadata_yaml_path, build_metadata_yaml_payload(structured))
            self._record_parse_status(
                pdf_path=pdf_path,
                relative_key=relative_key,
                sha256=sha256,
                status="succeeded",
                parser_used=parser_used,
                grobid_base_url=client.base_url,
                grobid_health_status=grobid_health_status,
                fallback_triggered=fallback_triggered,
                metadata_path=metadata_path,
                raw_text_path=raw_text_path,
                tei_path=tei_path,
                structured=structured,
                error=None,
                metadata_yaml_path=metadata_yaml_path,
            )

            self._mark_state(
                relative_key=relative_key,
                status="succeeded",
                sha256=sha256,
                metadata_path=metadata_path,
                raw_text_path=raw_text_path,
                tei_path=tei_path,
                error=None,
            )
            logger.info("Succeeded: {}", pdf_path)
            return ProcessResult(
                pdf_path=pdf_path,
                status="succeeded",
                metadata_path=metadata_path,
                raw_text_path=raw_text_path,
                tei_path=tei_path,
                paper_id=structured.get("paper_id"),
                parser_used=parser_used,
                grobid_fulltext_status=grobid_request.get("status"),
                grobid_attempts=int(grobid_request.get("attempts") or 0),
                error_type=grobid_request.get("error_type"),
                fallback_triggered=fallback_triggered,
            )
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            logger.error("Failed at stage {} for {}: {}", stage, pdf_path, error_message)
            self._record_failure(
                pdf_path=pdf_path,
                relative_key=relative_key,
                stage=stage,
                sha256=sha256,
                error=exc,
            )
            self._mark_state(
                relative_key=relative_key,
                status="failed",
                sha256=sha256,
                metadata_path=None,
                raw_text_path=None,
                tei_path=None,
                error=error_message,
            )
            failure_structured = {
                "paper_id": f"paper_{sha256[:16]}" if sha256 else None,
                "metadata": {},
                "sections": [],
                "tei_abstract": None,
                "abstract_candidate": None,
                "abstract_source": None,
                "abstract_fallback_triggered": False,
                "grobid_request": grobid_request,
            }
            failure_structured["parse_status"] = build_parse_status(
                status="failed",
                parser_used=parser_used or "unknown",
                grobid_base_url=grobid_base_url,
                grobid_health_endpoint=None,
                grobid_process_fulltext_endpoint=None,
                grobid_health_status=grobid_health_status,
                fallback_triggered=fallback_triggered,
                tei_path=tei_path if tei_path and tei_path.exists() else None,
                structured=failure_structured,
                error=error_message,
            )
            self._record_parse_status(
                pdf_path=pdf_path,
                relative_key=relative_key,
                sha256=sha256,
                status="failed",
                parser_used=parser_used or "unknown",
                grobid_base_url=grobid_base_url,
                grobid_health_status=grobid_health_status,
                fallback_triggered=fallback_triggered,
                metadata_path=metadata_path,
                raw_text_path=raw_text_path,
                tei_path=tei_path if tei_path and tei_path.exists() else None,
                structured=failure_structured,
                error=error_message,
                metadata_yaml_path=None,
            )
            error_type = getattr(exc, "error_type", type(exc).__name__)
            return ProcessResult(
                pdf_path=pdf_path,
                status="failed",
                paper_id=f"paper_{sha256[:16]}" if sha256 else None,
                parser_used=parser_used or "unknown",
                grobid_fulltext_status="failed",
                grobid_attempts=getattr(exc, "attempts", 0),
                error_type=error_type,
                fallback_triggered=fallback_triggered,
                error=error_message,
            )

    def metadata_yaml_path(self, relative_key: str) -> Path:
        paper_key = safe_path_name(Path(relative_key).with_suffix("").as_posix())
        return self.paths.yaml_root_dir / paper_key / "metadata.yaml"

    def _can_skip(
        self,
        relative_key: str,
        sha256: str,
        metadata_path: Path,
        raw_text_path: Path,
    ) -> bool:
        if self.options.force:
            return False
        entry = self.state.get("files", {}).get(relative_key)
        if not entry:
            return False
        return (
            entry.get("status") == "succeeded"
            and entry.get("sha256") == sha256
            and metadata_path.exists()
            and raw_text_path.exists()
        )

    def _relative_key(self, pdf_path: Path) -> str:
        try:
            return pdf_path.relative_to(self.paths.input_dir).as_posix()
        except ValueError:
            return pdf_path.name

    def _load_state(self) -> dict[str, Any]:
        if not self.paths.state_path.exists():
            return {"version": PARSER_VERSION, "files": {}}
        try:
            return json.loads(self.paths.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.paths.state_path.with_suffix(".corrupt.json")
            self.paths.state_path.replace(backup)
            logger.warning("State file was corrupt and moved to {}", backup)
            return {"version": PARSER_VERSION, "files": {}}

    def _mark_state(
        self,
        relative_key: str,
        status: str,
        sha256: str,
        metadata_path: Path | None,
        raw_text_path: Path | None,
        tei_path: Path | None,
        error: str | None,
    ) -> None:
        entry = {
            "status": status,
            "sha256": sha256,
            "updated_at": utc_now(),
            "metadata_path": str(metadata_path) if metadata_path else None,
            "raw_text_path": str(raw_text_path) if raw_text_path else None,
            "tei_path": str(tei_path) if tei_path else None,
            "error": error,
        }
        with self.state_lock:
            self.state.setdefault("files", {})[relative_key] = entry
            self.state["version"] = PARSER_VERSION
            self.state["updated_at"] = utc_now()
            write_json_atomic(self.paths.state_path, self.state)

    def _record_failure(
        self,
        pdf_path: Path,
        relative_key: str,
        stage: str,
        sha256: str,
        error: Exception,
    ) -> None:
        record = {
            "timestamp": utc_now(),
            "pdf_path": str(pdf_path),
            "relative_key": relative_key,
            "stage": stage,
            "sha256": sha256 or None,
            "error_type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
        with self.failure_lock:
            self.paths.failures_dir.mkdir(parents=True, exist_ok=True)
            with self.paths.failure_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _record_parse_status(
        self,
        pdf_path: Path,
        relative_key: str,
        sha256: str,
        status: str,
        parser_used: str,
        grobid_base_url: str | None,
        grobid_health_status: str,
        fallback_triggered: bool,
        metadata_path: Path | None,
        raw_text_path: Path | None,
        tei_path: Path | None,
        structured: dict[str, Any] | None,
        error: str | None,
        metadata_yaml_path: Path | None = None,
    ) -> None:
        parse_status = (
            structured.get("parse_status", {})
            if isinstance(structured, dict)
            else build_parse_status(
                status=status,
                parser_used=parser_used,
                grobid_base_url=grobid_base_url,
                grobid_health_endpoint=None,
                grobid_process_fulltext_endpoint=None,
                grobid_health_status=grobid_health_status,
                fallback_triggered=fallback_triggered,
                tei_path=tei_path,
                structured=structured,
                error=error,
            )
        )
        record = {
            "paper_key": relative_key,
            "paper_id": structured.get("paper_id") if isinstance(structured, dict) else None,
            "source_pdf": str(pdf_path),
            "sha256": sha256 or None,
            "status": status,
            "parser_used": parser_used,
            "grobid_base_url": grobid_base_url,
            "grobid_health_status": grobid_health_status,
            "grobid_fulltext_status": parse_status.get("grobid_fulltext_status"),
            "grobid_elapsed_seconds": parse_status.get("grobid_elapsed_seconds"),
            "grobid_attempts": parse_status.get("grobid_attempts"),
            "grobid_retry_count": parse_status.get("grobid_retry_count"),
            "grobid_failure_reason": parse_status.get("grobid_failure_reason"),
            "grobid_status_code": parse_status.get("grobid_status_code"),
            "grobid_error_type": parse_status.get("grobid_error_type"),
            "fallback_reason": parse_status.get("fallback_reason"),
            "fallback_triggered": fallback_triggered,
            "tei_xml_generated": bool(tei_path and tei_path.exists()),
            "tei_xml_path": str(tei_path) if tei_path else None,
            "extracted_title_from_tei": bool(parse_status.get("tei_extraction", {}).get("title")),
            "extracted_abstract_from_tei": bool(parse_status.get("tei_extraction", {}).get("abstract")),
            "extracted_body_from_tei": bool(parse_status.get("tei_extraction", {}).get("body")),
            "tei_abstract_found": bool(parse_status.get("tei_abstract_found")),
            "abstract_source": parse_status.get("abstract_source"),
            "abstract_candidate_length": parse_status.get("abstract_candidate_length"),
            "abstract_fallback_triggered": bool(parse_status.get("abstract_fallback_triggered")),
            "metadata_path": str(metadata_path) if metadata_path else None,
            "metadata_yaml_path": str(metadata_yaml_path) if metadata_yaml_path else None,
            "raw_text_path": str(raw_text_path) if raw_text_path else None,
            "error": error,
            "updated_at": utc_now(),
        }
        with self.parse_status_lock:
            update_parse_status_sqlite(self.paths.parse_status_path, record)


def tei_to_structured_payload(
    tei_xml: str,
    pdf_path: Path,
    relative_key: str,
    sha256: str,
    grobid_url: str,
    grobid_elapsed_seconds: float,
) -> dict[str, Any]:
    root = ET.fromstring(tei_xml)
    header = first_descendant(root, "teiHeader")
    title = extract_title(header, root)
    authors = extract_authors(root)
    doi = extract_idno(root, "doi")
    year = extract_year(root)
    tei_abstract = extract_abstract(root)
    sections = extract_sections(root)
    references = extract_references(root)
    abstract_candidate = None if tei_abstract else extract_body_abstract_candidate(sections)
    abstract = tei_abstract or abstract_candidate
    abstract_source = "tei" if tei_abstract else ("body_fallback" if abstract_candidate else None)
    abstract_fallback_triggered = bool(not tei_abstract and abstract_candidate)

    paper_id = f"paper_{sha256[:16]}"
    return {
        "paper_id": paper_id,
        "parser": {
            "name": "Scientra Copilot PDF Engine",
            "version": PARSER_VERSION,
            "method": "grobid",
            "uses_llm": False,
            "grobid_url": grobid_url,
            "grobid_elapsed_seconds": round(grobid_elapsed_seconds, 3),
            "parsed_at": utc_now(),
        },
        "source": {
            "pdf_path": str(pdf_path),
            "relative_key": relative_key,
            "file_name": pdf_path.name,
            "file_size_bytes": pdf_path.stat().st_size,
            "sha256": sha256,
        },
        "metadata": {
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
        },
        "metadata_sources": {
            "title": "grobid_header" if title else None,
            "authors": "grobid_header" if authors else None,
            "year": "grobid_header" if year else None,
            "doi": "grobid_header" if doi else None,
            "abstract": abstract_source,
        },
        "tei_abstract": tei_abstract,
        "abstract": abstract,
        "abstract_source": abstract_source,
        "abstract_candidate": abstract_candidate,
        "abstract_fallback_triggered": abstract_fallback_triggered,
        "sections": sections,
        "references": references,
        "counts": {
            "sections": len(sections),
            "references": len(references),
            "raw_text_chars": sum(len(section.get("text", "")) for section in sections)
            + len(abstract or ""),
        },
    }


def pymupdf_to_structured_payload(
    pdf_path: Path,
    relative_key: str,
    sha256: str,
    grobid_url: str,
) -> dict[str, Any]:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - depends on local runtime
        raise RuntimeError("PyMuPDF/fitz is required for PDF fallback parsing") from exc

    document = fitz.open(pdf_path)
    pages: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        page_blocks = sorted(
            page.get_text("blocks"),
            key=lambda block: (round(float(block[1]), 1), round(float(block[0]), 1), int(block[5])),
        )
        paragraphs: list[str] = []
        for block in page_blocks:
            text = clean_text(str(block[4]))
            if not text:
                continue
            paragraphs.append(text)
            blocks.append(
                {
                    "page": page_index + 1,
                    "paragraph": len(paragraphs),
                    "block_no": int(block[5]),
                    "text": text,
                }
            )
        if paragraphs:
            pages.append(
                {
                    "section_id": f"page_{page_index + 1:04d}",
                    "level": 1,
                    "heading": f"Page {page_index + 1}",
                    "heading_path": [f"Page {page_index + 1}"],
                    "text": "\n\n".join(paragraphs),
                    "paragraphs": paragraphs,
                }
            )

    pdf_metadata = document.metadata or {}
    title, title_source = infer_pymupdf_title_with_source(blocks, pdf_metadata)
    abstract = infer_pymupdf_abstract(blocks)
    doi = infer_doi_from_text("\n\n".join(block["text"] for block in blocks))
    year = infer_year_from_text("\n\n".join(block["text"] for block in blocks))
    paper_id = f"paper_{sha256[:16]}"
    return {
        "paper_id": paper_id,
        "parser": {
            "name": "Scientra Copilot PDF Engine",
            "version": PARSER_VERSION,
            "method": "pymupdf",
            "uses_llm": False,
            "grobid_url": grobid_url,
            "parsed_at": utc_now(),
        },
        "source": {
            "pdf_path": str(pdf_path),
            "relative_key": relative_key,
            "file_name": pdf_path.name,
            "file_size_bytes": pdf_path.stat().st_size,
            "sha256": sha256,
        },
        "metadata": {
            "title": title,
            "authors": [],
            "year": year,
            "doi": doi,
        },
        "metadata_sources": {
            "title": title_source,
            "authors": None,
            "year": "first_page_regex" if year else None,
            "doi": "regex" if doi else None,
            "abstract": "first_page" if abstract else None,
        },
        "tei_abstract": None,
        "abstract": abstract,
        "abstract_source": "pymupdf_rules" if abstract else None,
        "abstract_candidate": abstract,
        "abstract_fallback_triggered": False,
        "sections": pages,
        "references": [],
        "counts": {
            "sections": len(pages),
            "references": 0,
            "raw_text_chars": sum(len(section.get("text", "")) for section in pages)
            + len(abstract or ""),
        },
    }


def build_parse_status(
    status: str,
    parser_used: str,
    grobid_base_url: str | None,
    grobid_health_endpoint: str | None,
    grobid_process_fulltext_endpoint: str | None,
    grobid_health_status: str,
    fallback_triggered: bool,
    tei_path: Path | None,
    structured: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    metadata = structured.get("metadata", {}) if isinstance(structured, dict) else {}
    sections = structured.get("sections", []) if isinstance(structured, dict) else []
    tei_abstract = structured.get("tei_abstract") if isinstance(structured, dict) else None
    abstract_candidate = structured.get("abstract_candidate") if isinstance(structured, dict) else None
    parser_method = structured.get("parser", {}).get("method") if isinstance(structured, dict) else None
    tei_generated = bool(tei_path and tei_path.exists())
    extracted_from_tei = parser_used == "GROBID" and parser_method == "grobid"
    tei_abstract_found = bool(extracted_from_tei and tei_abstract)
    abstract_fallback_triggered = bool(
        structured.get("abstract_fallback_triggered")
        if isinstance(structured, dict)
        else False
    )
    grobid_request = structured.get("grobid_request", {}) if isinstance(structured, dict) else {}
    grobid_failure_reasons = grobid_request.get("failure_reasons") or []
    if isinstance(grobid_failure_reasons, str):
        grobid_failure_reasons = [grobid_failure_reasons]
    return {
        "status": status,
        "parser_used": parser_used,
        "grobid_base_url": grobid_base_url,
        "health_endpoint": grobid_health_endpoint,
        "process_fulltext_endpoint": grobid_process_fulltext_endpoint,
        "grobid_health_status": grobid_health_status,
        "grobid_fulltext_status": grobid_request.get("status") or "not_attempted",
        "grobid_elapsed_seconds": grobid_request.get("elapsed_seconds"),
        "grobid_attempts": int(grobid_request.get("attempts") or 0),
        "grobid_retry_count": int(grobid_request.get("retry_count") or 0),
        "grobid_status_code": grobid_request.get("status_code"),
        "grobid_error_type": grobid_request.get("error_type"),
        "grobid_failure_reasons": grobid_failure_reasons,
        "grobid_failure_reason": "; ".join(str(reason) for reason in grobid_failure_reasons),
        "fallback_triggered": fallback_triggered,
        "fallback_reason": "; ".join(str(reason) for reason in grobid_failure_reasons) if fallback_triggered else None,
        "tei_xml_generated": tei_generated,
        "tei_xml_path": str(tei_path) if tei_path else None,
        "tei_extraction": {
            "title": bool(extracted_from_tei and metadata.get("title")),
            "abstract": tei_abstract_found,
            "body": bool(extracted_from_tei and sections),
        },
        "tei_abstract_found": tei_abstract_found,
        "abstract_source": structured.get("abstract_source") if isinstance(structured, dict) else None,
        "abstract_candidate_length": len(abstract_candidate or ""),
        "abstract_fallback_triggered": abstract_fallback_triggered,
        "error": error,
        "updated_at": utc_now(),
    }


def extract_title(header: ET.Element | None, root: ET.Element) -> str | None:
    if header is not None:
        title_stmt = first_descendant(header, "titleStmt")
        if title_stmt is not None:
            for child in direct_children(title_stmt, "title"):
                title = clean_text(text_content(child))
                if title:
                    return title

    analytic = first_descendant(root, "analytic")
    if analytic is not None:
        for child in direct_children(analytic, "title"):
            title = clean_text(text_content(child))
            if title:
                return title
    return None


def extract_authors(root: ET.Element) -> list[dict[str, Any]]:
    analytic = first_descendant(root, "analytic")
    author_nodes = list(direct_children(analytic, "author")) if analytic is not None else []
    if not author_nodes:
        author_nodes = list(descendants(root, "author"))

    authors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for author in author_nodes:
        parsed = parse_author(author)
        name = parsed.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        authors.append(parsed)
    return authors


def parse_author(author: ET.Element) -> dict[str, Any]:
    pers_name = first_descendant(author, "persName")
    if pers_name is None:
        name = clean_text(text_content(author))
        return {"name": name} if name else {}

    forenames = [clean_text(text_content(node)) for node in descendants(pers_name, "forename")]
    forenames = [value for value in forenames if value]
    surname_node = first_descendant(pers_name, "surname")
    surname = clean_text(text_content(surname_node)) if surname_node is not None else None
    name_parts = [*forenames, surname]
    name = clean_text(" ".join(part for part in name_parts if part))
    return {
        "name": name,
        "forenames": forenames,
        "surname": surname,
    }


def extract_idno(root: ET.Element, id_type: str) -> str | None:
    for node in descendants(root, "idno"):
        if node.attrib.get("type", "").lower() == id_type.lower():
            value = clean_text(text_content(node))
            if value:
                return value
    return None


def extract_year(root: ET.Element) -> int | None:
    for node in descendants(root, "date"):
        for value in [node.attrib.get("when"), node.attrib.get("notBefore"), text_content(node)]:
            if not value:
                continue
            match = re.search(r"\b(19|20)\d{2}\b", value)
            if match:
                return int(match.group(0))
    return None


def extract_abstract(root: ET.Element) -> str | None:
    abstract = first_descendant(root, "abstract")
    if abstract is None:
        return None
    paragraphs = [clean_text(text_content(node)) for node in descendants(abstract, "p")]
    paragraphs = [text for text in paragraphs if text]
    if paragraphs:
        return "\n\n".join(paragraphs)
    value = clean_text(text_content(abstract))
    return value or None


def extract_body_abstract_candidate(sections: list[dict[str, Any]]) -> str | None:
    if not sections:
        return None

    first_section = sections[0]
    paragraphs = [
        clean_text(paragraph)
        for paragraph in first_section.get("paragraphs", [])
        if clean_text(paragraph)
    ]
    if not paragraphs:
        text = clean_text(first_section.get("text"))
        paragraphs = [text] if text else []
    if not paragraphs:
        return None

    selected: list[str] = []
    for paragraph in paragraphs:
        selected.append(paragraph)
        candidate = " ".join(selected)
        if len(candidate) >= 800 and has_abstract_closing_signal(candidate):
            break
        if len(candidate) >= 2000:
            break

    candidate = " ".join(selected)
    if len(candidate) < 800 and len(paragraphs) > len(selected):
        for paragraph in paragraphs[len(selected) :]:
            candidate = f"{candidate} {paragraph}".strip()
            if len(candidate) >= 800:
                break

    return trim_abstract_candidate(candidate)


def has_abstract_closing_signal(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in [
            "our findings",
            "our results",
            "we identify",
            "we show",
            "here we",
        ]
    )


def trim_abstract_candidate(text: str, max_chars: int = 2000) -> str | None:
    text = clean_text(text)
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    sentence_end = max(window.rfind(". "), window.rfind("; "), window.rfind("! "), window.rfind("? "))
    if sentence_end >= 800:
        return window[: sentence_end + 1].strip()
    return window.rstrip()


def extract_sections(root: ET.Element) -> list[dict[str, Any]]:
    body = first_descendant(root, "body")
    if body is None:
        return []

    sections: list[dict[str, Any]] = []
    section_counter = 0

    def walk_div(div: ET.Element, level: int, heading_path: list[str]) -> None:
        nonlocal section_counter
        heading_node = first_direct_child(div, "head")
        heading = clean_text(text_content(heading_node)) if heading_node is not None else None
        current_path = [*heading_path, heading] if heading else heading_path
        paragraphs = [clean_text(text_content(child)) for child in direct_children(div, "p")]
        paragraphs = [text for text in paragraphs if text]

        if paragraphs:
            section_counter += 1
            sections.append(
                {
                    "section_id": f"sec_{section_counter:04d}",
                    "level": level,
                    "heading": heading or "Untitled",
                    "heading_path": current_path,
                    "text": "\n\n".join(paragraphs),
                    "paragraphs": paragraphs,
                }
            )

        for child_div in direct_children(div, "div"):
            walk_div(child_div, level + 1, current_path)

    top_divs = list(direct_children(body, "div"))
    for div in top_divs:
        walk_div(div, 1, [])

    if not sections:
        paragraphs = [clean_text(text_content(node)) for node in descendants(body, "p")]
        paragraphs = [text for text in paragraphs if text]
        if paragraphs:
            sections.append(
                {
                    "section_id": "sec_0001",
                    "level": 1,
                    "heading": "Body",
                    "heading_path": ["Body"],
                    "text": "\n\n".join(paragraphs),
                    "paragraphs": paragraphs,
                }
            )
    return sections


def extract_references(root: ET.Element) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    back = first_descendant(root, "back")
    search_root = back if back is not None else root
    for index, bibl in enumerate(descendants(search_root, "biblStruct"), start=1):
        title = None
        analytic = first_descendant(bibl, "analytic")
        if analytic is not None:
            title_node = first_descendant(analytic, "title")
            title = clean_text(text_content(title_node)) if title_node is not None else None
        doi = extract_idno(bibl, "doi")
        year = extract_year(bibl)
        authors = extract_authors(bibl)
        raw = clean_text(text_content(bibl))
        references.append(
            {
                "reference_id": f"ref_{index:04d}",
                "title": title,
                "authors": authors,
                "year": year,
                "doi": doi,
                "raw": raw,
            }
        )
    return references


def build_raw_text(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata", {})
    authors = metadata.get("authors") or []
    author_names = [author.get("name") for author in authors if author.get("name")]
    parts: list[str] = []

    title = metadata.get("title")
    if title:
        parts.append(f"# {title}")

    if author_names:
        parts.append("Authors: " + "; ".join(author_names))
    if metadata.get("year"):
        parts.append(f"Year: {metadata['year']}")
    if metadata.get("doi"):
        parts.append(f"DOI: {metadata['doi']}")

    abstract = payload.get("abstract")
    if abstract:
        parts.append("## Abstract\n" + abstract)

    for section in payload.get("sections", []):
        heading = section.get("heading") or "Untitled"
        text = section.get("text") or ""
        if text:
            parts.append(f"## {heading}\n{text}")

    return "\n\n".join(parts).strip() + "\n"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def descendants(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in node.iter() if local_name(child.tag) == name]


def direct_children(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in list(node) if local_name(child.tag) == name]


def first_descendant(node: ET.Element | None, name: str) -> ET.Element | None:
    matches = descendants(node, name)
    return matches[0] if matches else None


def first_direct_child(node: ET.Element | None, name: str) -> ET.Element | None:
    matches = direct_children(node, name)
    return matches[0] if matches else None


def text_content(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\x00", "").split())
    return cleaned or None


def infer_pymupdf_title(blocks: list[dict[str, Any]], metadata: dict[str, Any]) -> str | None:
    title, _source = infer_pymupdf_title_with_source(blocks, metadata)
    return title


def infer_pymupdf_title_with_source(
    blocks: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> tuple[str | None, str | None]:
    metadata_title = clean_text(metadata.get("title"))
    if metadata_title and metadata_title.lower() not in {"untitled", "none"}:
        return metadata_title, "pdf_meta"
    for block in blocks:
        if block.get("page") != 1:
            continue
        text = clean_text(block.get("text"))
        if not text:
            continue
        if text.lower() in {"article", "research article"}:
            continue
        if "doi.org" in text.lower() or text.lower().startswith(("received:", "accepted:")):
            continue
        if 20 <= len(text) <= 220:
            return text.replace("\n", " "), "first_page"
    return filename_title(metadata.get("file_name") or ""), "filename"


def infer_pymupdf_abstract(blocks: list[dict[str, Any]]) -> str | None:
    for block in blocks:
        text = clean_text(block.get("text"))
        if not text:
            continue
        lowered = text.lower()
        if (
            block.get("page") == 1
            and len(text) > 400
            and ("here we" in lowered or "our findings" in lowered)
        ):
            return text
    return None


def infer_doi_from_text(text: str) -> str | None:
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", text, flags=re.IGNORECASE)
    return match.group(0).rstrip(".") if match else None


def infer_year_from_text(text: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", text[:5000])
    return int(match.group(0)) if match else None


def filename_title(value: str | None) -> str | None:
    text = clean_text(Path(value or "").stem.replace("_", " ").replace("-", " "))
    if not text or len(text) < 8:
        return None
    return text


def write_grobid_meta(
    artifact_dir: Path,
    pdf_path: Path,
    response: Any,
    structured: dict[str, Any],
    client: GrobidClient,
) -> None:
    metadata = structured.get("metadata", {})
    payload = {
        "pdf_path": str(pdf_path),
        "grobid_base_url": client.base_url,
        "endpoint": response.endpoint,
        "status_code": response.status_code,
        "elapsed_seconds": round(response.elapsed_seconds, 3),
        "attempts": response.attempts,
        "retry_count": response.retry_count,
        "consolidateHeader": int(client.request.consolidate_header),
        "consolidateCitations": int(client.request.consolidate_citations),
        "tei_length": len(response.text),
        "title": metadata.get("title"),
        "abstract_length": len(structured.get("abstract") or ""),
        "body_length": sum(len(section.get("text", "")) for section in structured.get("sections", [])),
        "references_count": len(structured.get("references", [])),
        "written_at": utc_now(),
    }
    write_json_atomic(artifact_dir / "grobid_meta.json", payload)


def write_grobid_error(
    artifact_dir: Path,
    pdf_path: Path,
    status_code: int | None,
    error_type: str,
    response_text: str | None,
    attempts: int,
    fallback_used: bool,
    failure_reasons: list[str] | None = None,
) -> None:
    payload = {
        "pdf_path": str(pdf_path),
        "status_code": status_code,
        "error_type": error_type,
        "traceback_or_response_text": (response_text or "")[:4000],
        "attempts": attempts,
        "failure_reasons": failure_reasons or [],
        "fallback_used": bool(fallback_used),
        "written_at": utc_now(),
    }
    write_json_atomic(artifact_dir / "error.json", payload)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_output_base(relative_key: str, sha256: str) -> str:
    stem = Path(relative_key).with_suffix("").as_posix()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    safe = safe[:120] or "paper"
    return f"{safe}_{sha256[:12]}"


def safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe[:120] or "paper"


def build_metadata_yaml_payload(structured: dict[str, Any]) -> dict[str, Any]:
    metadata = structured.get("metadata", {})
    metadata_sources = structured.get("metadata_sources", {})
    outputs = structured.get("outputs", {})
    return {
        "paper_id": structured.get("paper_id"),
        "source_pdf": dig(structured, "source", "pdf_path"),
        "title": metadata.get("title"),
        "title_source": metadata_sources.get("title"),
        "doi": metadata.get("doi"),
        "doi_source": metadata_sources.get("doi"),
        "year": metadata.get("year"),
        "year_source": metadata_sources.get("year"),
        "authors": metadata.get("authors") or [],
        "authors_source": metadata_sources.get("authors"),
        "abstract": structured.get("abstract"),
        "abstract_source": structured.get("abstract_source"),
        "abstract_candidate": structured.get("abstract_candidate"),
        "tei_abstract": structured.get("tei_abstract"),
        "parse_status": structured.get("parse_status", {}),
        "outputs": outputs,
    }


def build_parse_report(
    pdfs: list[Path],
    results: list[ProcessResult],
    paths: ParserPaths,
) -> dict[str, Any]:
    total = len(pdfs)
    grobid_success = sum(1 for result in results if result.grobid_fulltext_status == "succeeded")
    fallback_success = sum(
        1
        for result in results
        if result.status in {"succeeded", "skipped"}
        and result.parser_used == "PyMuPDF"
        and result.fallback_triggered
    )
    parse_success = sum(1 for result in results if result.status in {"succeeded", "skipped"})
    grobid_failed = total - grobid_success
    fallback_ratio = fallback_success / total if total else 0.0
    grobid_rate = grobid_success / total if total else 0.0
    parse_total_rate = parse_success / total if total else 0.0
    error_distribution: dict[str, int] = {}
    for result in results:
        if result.error_type:
            error_distribution[result.error_type] = error_distribution.get(result.error_type, 0) + 1
    quality_gate = {
        "grobid_fulltext_success_rate_threshold": 0.8,
        "fallback_ratio_threshold": 0.2,
        "grobid_fulltext_success_rate_pass": grobid_rate >= 0.8,
        "fallback_ratio_pass": fallback_ratio <= 0.2,
        "passed": grobid_rate >= 0.8 and fallback_ratio <= 0.2,
    }
    return {
        "generated_at": utc_now(),
        "parser_version": PARSER_VERSION,
        "input_dir": str(paths.input_dir),
        "total_pdf_count": total,
        "grobid_fulltext_success": grobid_success,
        "grobid_fulltext_failed": grobid_failed,
        "pymupdf_fallback_success": fallback_success,
        "parse_total_success": parse_success,
        "grobid_fulltext_success_rate": round(grobid_rate, 4),
        "parse_total_success_rate": round(parse_total_rate, 4),
        "fallback_ratio": round(fallback_ratio, 4),
        "error_distribution": error_distribution,
        "quality_gate": quality_gate,
        "papers": [
            {
                "pdf_path": str(result.pdf_path),
                "paper_id": result.paper_id,
                "status": result.status,
                "parser_used": result.parser_used,
                "grobid_fulltext_status": result.grobid_fulltext_status,
                "grobid_attempts": result.grobid_attempts,
                "error_type": result.error_type,
                "fallback_used": result.fallback_triggered,
                "fallback_reason": result.error if result.fallback_triggered else None,
                "tei_path": str(result.tei_path) if result.tei_path else None,
                "metadata_path": str(result.metadata_path) if result.metadata_path else None,
                "raw_text_path": str(result.raw_text_path) if result.raw_text_path else None,
                "error": result.error,
            }
            for result in results
        ],
    }


def write_parse_report(report: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(report_dir / "parse_report.json", report)
    lines = [
        "# PDF Parse Report",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- input_dir: {report['input_dir']}",
        f"- total_pdf_count: {report['total_pdf_count']}",
        f"- grobid_fulltext_success: {report['grobid_fulltext_success']}",
        f"- grobid_fulltext_failed: {report['grobid_fulltext_failed']}",
        f"- pymupdf_fallback_success: {report['pymupdf_fallback_success']}",
        f"- parse_total_success: {report['parse_total_success']}",
        f"- grobid_fulltext_success_rate: {report['grobid_fulltext_success_rate']}",
        f"- fallback_ratio: {report['fallback_ratio']}",
        f"- quality_gate_passed: {report['quality_gate']['passed']}",
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
    lines.append("| PDF | Status | Parser | GROBID Status | Attempts | Error Type | Fallback |")
    lines.append("|---|---|---|---|---:|---|---|")
    for item in report["papers"]:
        lines.append(
            "| {pdf} | {status} | {parser} | {grobid} | {attempts} | {error_type} | {fallback} |".format(
                pdf=Path(item["pdf_path"]).name.replace("|", "\\|"),
                status=item.get("status") or "",
                parser=item.get("parser_used") or "",
                grobid=item.get("grobid_fulltext_status") or "",
                attempts=item.get("grobid_attempts") or 0,
                error_type=item.get("error_type") or "",
                fallback=item.get("fallback_used"),
            )
        )
    write_text_atomic(report_dir / "parse_report.md", "\n".join(lines) + "\n")


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def write_yaml_atomic(path: Path, payload: dict[str, Any]) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write metadata.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    temp_path.replace(path)


def dig(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def update_parse_status_sqlite(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS parse_status (
                paper_key TEXT PRIMARY KEY,
                paper_id TEXT,
                source_pdf TEXT NOT NULL,
                sha256 TEXT,
                status TEXT NOT NULL,
                parser_used TEXT NOT NULL,
                grobid_base_url TEXT,
                grobid_health_status TEXT,
                grobid_fulltext_status TEXT,
                grobid_elapsed_seconds REAL,
                grobid_attempts INTEGER NOT NULL DEFAULT 0,
                grobid_retry_count INTEGER NOT NULL DEFAULT 0,
                grobid_failure_reason TEXT,
                grobid_status_code INTEGER,
                grobid_error_type TEXT,
                fallback_reason TEXT,
                fallback_triggered INTEGER NOT NULL,
                tei_xml_generated INTEGER NOT NULL,
                tei_xml_path TEXT,
                extracted_title_from_tei INTEGER NOT NULL,
                extracted_abstract_from_tei INTEGER NOT NULL,
                extracted_body_from_tei INTEGER NOT NULL,
                tei_abstract_found INTEGER NOT NULL DEFAULT 0,
                abstract_source TEXT,
                abstract_candidate_length INTEGER NOT NULL DEFAULT 0,
                abstract_fallback_triggered INTEGER NOT NULL DEFAULT 0,
                metadata_path TEXT,
                metadata_yaml_path TEXT,
                raw_text_path TEXT,
                error TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        ensure_parse_status_columns(connection)
        connection.execute(
            """
            INSERT INTO parse_status (
                paper_key, paper_id, source_pdf, sha256, status, parser_used,
                grobid_base_url, grobid_health_status, grobid_fulltext_status,
                grobid_elapsed_seconds, grobid_attempts, grobid_retry_count,
                grobid_failure_reason, grobid_status_code, grobid_error_type,
                fallback_reason, fallback_triggered,
                tei_xml_generated, tei_xml_path, extracted_title_from_tei,
                extracted_abstract_from_tei, extracted_body_from_tei,
                tei_abstract_found, abstract_source, abstract_candidate_length,
                abstract_fallback_triggered, metadata_path, metadata_yaml_path,
                raw_text_path, error, updated_at
            ) VALUES (
                :paper_key, :paper_id, :source_pdf, :sha256, :status, :parser_used,
                :grobid_base_url, :grobid_health_status, :grobid_fulltext_status,
                :grobid_elapsed_seconds, :grobid_attempts, :grobid_retry_count,
                :grobid_failure_reason, :grobid_status_code, :grobid_error_type,
                :fallback_reason, :fallback_triggered,
                :tei_xml_generated, :tei_xml_path, :extracted_title_from_tei,
                :extracted_abstract_from_tei, :extracted_body_from_tei,
                :tei_abstract_found, :abstract_source, :abstract_candidate_length,
                :abstract_fallback_triggered, :metadata_path, :metadata_yaml_path,
                :raw_text_path, :error, :updated_at
            )
            ON CONFLICT(paper_key) DO UPDATE SET
                paper_id=excluded.paper_id,
                source_pdf=excluded.source_pdf,
                sha256=excluded.sha256,
                status=excluded.status,
                parser_used=excluded.parser_used,
                grobid_base_url=excluded.grobid_base_url,
                grobid_health_status=excluded.grobid_health_status,
                grobid_fulltext_status=excluded.grobid_fulltext_status,
                grobid_elapsed_seconds=excluded.grobid_elapsed_seconds,
                grobid_attempts=excluded.grobid_attempts,
                grobid_retry_count=excluded.grobid_retry_count,
                grobid_failure_reason=excluded.grobid_failure_reason,
                grobid_status_code=excluded.grobid_status_code,
                grobid_error_type=excluded.grobid_error_type,
                fallback_reason=excluded.fallback_reason,
                fallback_triggered=excluded.fallback_triggered,
                tei_xml_generated=excluded.tei_xml_generated,
                tei_xml_path=excluded.tei_xml_path,
                extracted_title_from_tei=excluded.extracted_title_from_tei,
                extracted_abstract_from_tei=excluded.extracted_abstract_from_tei,
                extracted_body_from_tei=excluded.extracted_body_from_tei,
                tei_abstract_found=excluded.tei_abstract_found,
                abstract_source=excluded.abstract_source,
                abstract_candidate_length=excluded.abstract_candidate_length,
                abstract_fallback_triggered=excluded.abstract_fallback_triggered,
                metadata_path=excluded.metadata_path,
                metadata_yaml_path=excluded.metadata_yaml_path,
                raw_text_path=excluded.raw_text_path,
                error=excluded.error,
                updated_at=excluded.updated_at
            """,
            {
                **record,
                "fallback_triggered": int(bool(record.get("fallback_triggered"))),
                "tei_xml_generated": int(bool(record.get("tei_xml_generated"))),
                "extracted_title_from_tei": int(bool(record.get("extracted_title_from_tei"))),
                "extracted_abstract_from_tei": int(bool(record.get("extracted_abstract_from_tei"))),
                "extracted_body_from_tei": int(bool(record.get("extracted_body_from_tei"))),
                "tei_abstract_found": int(bool(record.get("tei_abstract_found"))),
                "grobid_attempts": int(record.get("grobid_attempts") or 0),
                "grobid_retry_count": int(record.get("grobid_retry_count") or 0),
                "abstract_candidate_length": int(record.get("abstract_candidate_length") or 0),
                "abstract_fallback_triggered": int(bool(record.get("abstract_fallback_triggered"))),
            },
        )


def ensure_parse_status_columns(connection: sqlite3.Connection) -> None:
    existing = {
        row[1]
        for row in connection.execute("PRAGMA table_info(parse_status)").fetchall()
    }
    columns = {
        "tei_abstract_found": "INTEGER NOT NULL DEFAULT 0",
        "abstract_source": "TEXT",
        "abstract_candidate_length": "INTEGER NOT NULL DEFAULT 0",
        "abstract_fallback_triggered": "INTEGER NOT NULL DEFAULT 0",
        "metadata_yaml_path": "TEXT",
        "grobid_fulltext_status": "TEXT",
        "grobid_elapsed_seconds": "REAL",
        "grobid_attempts": "INTEGER NOT NULL DEFAULT 0",
        "grobid_retry_count": "INTEGER NOT NULL DEFAULT 0",
        "grobid_failure_reason": "TEXT",
        "grobid_status_code": "INTEGER",
        "grobid_error_type": "TEXT",
        "fallback_reason": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE parse_status ADD COLUMN {name} {definition}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"pdf_parser_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    try:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(log_path, level="INFO", rotation="10 MB", retention=20, encoding="utf-8")
    except AttributeError:
        pass
    return log_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch parse Scientra Copilot PDFs with GROBID. No LLM is used.",
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--raw-text-dir", type=Path, default=DEFAULT_RAW_TEXT_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--grobid-config", type=Path, default=DEFAULT_GROBID_CONFIG_PATH)
    parser.add_argument("--grobid-url", default=None, help="Override Config/grobid.yaml grobid_base_url.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Deprecated read timeout override.")
    parser.add_argument("--retries", type=int, default=None, help="Deprecated extra retry count override.")
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--retry-wait-seconds", type=float, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--inter-request-sleep", type=float, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--no-save-tei", action="store_true")
    parser.add_argument("--check-grobid", action="store_true")
    parser.add_argument("--grobid-only", action="store_true", help="Do not use PyMuPDF fallback after GROBID request failures.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    paths = ParserPaths(
        input_dir=args.input_dir.resolve(),
        metadata_dir=args.metadata_dir.resolve(),
        raw_text_dir=args.raw_text_dir.resolve(),
        log_dir=args.log_dir.resolve(),
        report_dir=args.report_dir.resolve(),
    )
    log_path = configure_logging(paths.log_dir)
    grobid_config = load_grobid_config(args.grobid_config.resolve())
    max_attempts = args.max_attempts
    if max_attempts is None and args.retries is not None:
        max_attempts = max(1, args.retries + 1)
    workers = args.workers if args.workers is not None else grobid_config.batch.concurrency
    if workers > grobid_config.batch.concurrency:
        logger.warning(
            "Requested workers={} exceeds GROBID batch concurrency={}; using {}",
            workers,
            grobid_config.batch.concurrency,
            grobid_config.batch.concurrency,
        )
        workers = grobid_config.batch.concurrency
    options = ParserOptions(
        grobid_url=args.grobid_url,
        grobid_config_path=args.grobid_config.resolve(),
        timeout_seconds=args.timeout_seconds,
        max_attempts=max_attempts,
        retry_wait_seconds=args.retry_wait_seconds,
        workers=workers,
        inter_request_sleep=(
            args.inter_request_sleep
            if args.inter_request_sleep is not None
            else grobid_config.batch.inter_request_sleep
        ),
        force=args.force,
        recursive=not args.no_recursive,
        limit=args.limit,
        save_tei=not args.no_save_tei,
        grobid_only=args.grobid_only,
    )

    logger.info("PDF Engine started")
    logger.info("Log file: {}", log_path)
    logger.info("Input directory: {}", paths.input_dir)
    logger.info("Metadata directory: {}", paths.metadata_dir)
    logger.info("Raw text directory: {}", paths.raw_text_dir)
    logger.info("GROBID config: {}", options.grobid_config_path)
    logger.info(
        "GROBID timeout: connect={}s read={}s total={}s",
        grobid_config.timeout.connect,
        grobid_config.timeout.read,
        grobid_config.timeout.total,
    )
    logger.info(
        "GROBID retry: max_attempts={} wait_seconds={}",
        max_attempts or grobid_config.retry.max_attempts,
        options.retry_wait_seconds or grobid_config.retry.wait_seconds,
    )
    logger.info(
        "GROBID batch: workers={} inter_request_sleep={}s",
        options.workers,
        options.inter_request_sleep,
    )

    if args.check_grobid:
        client = GrobidClient(
            base_url=options.grobid_url,
            config_path=options.grobid_config_path,
            timeout_seconds=options.timeout_seconds,
            max_attempts=1,
        )
        if not client.is_alive():
            logger.error("GROBID is not reachable at {}", client.base_url)
            return 2
        logger.info("GROBID is reachable at {}", client.base_url)
        return 0

    engine = PdfParserEngine(paths, options)
    try:
        results = engine.process_batch()
    except GrobidClientError as exc:
        logger.error("GROBID error: {}", exc)
        return 2

    report = build_parse_report(engine.collect_pdfs(), results, paths)
    write_parse_report(report, paths.report_dir)
    logger.info("Parse report: {}", paths.report_dir / "parse_report.md")

    counts = {"succeeded": 0, "skipped": 0, "failed": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    logger.info(
        "PDF Engine finished: succeeded={}, skipped={}, failed={}",
        counts.get("succeeded", 0),
        counts.get("skipped", 0),
        counts.get("failed", 0),
    )
    if counts.get("failed", 0):
        logger.warning("Failure records: {}", paths.failure_path)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
