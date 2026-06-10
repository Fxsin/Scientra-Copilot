from __future__ import annotations

import time
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import requests

try:
    import yaml
except Exception:  # pragma: no cover - PyYAML is part of the target stack.
    yaml = None


class GrobidClientError(RuntimeError):
    """Raised when GROBID cannot process a request."""

    def __init__(
        self,
        message: str,
        attempts: int = 0,
        retry_count: int = 0,
        failure_reasons: list[str] | None = None,
        error_type: str = "grobid_request_failed",
        status_code: int | None = None,
        response_text: str | None = None,
        elapsed_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.retry_count = retry_count
        self.failure_reasons = failure_reasons or []
        self.error_type = error_type
        self.status_code = status_code
        self.response_text = response_text
        self.elapsed_seconds = elapsed_seconds


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GROBID_CONFIG_PATH = PROJECT_ROOT / "Config" / "grobid.yaml"


@dataclass(frozen=True)
class GrobidTimeoutConfig:
    connect: float = 10.0
    read: float = 120.0
    total: float = 600.0


@dataclass(frozen=True)
class GrobidRetryConfig:
    max_attempts: int = 4
    wait_seconds: float = 10.0
    backoff_seconds: tuple[float, ...] = (10.0, 30.0, 60.0)


@dataclass(frozen=True)
class GrobidBatchConfig:
    concurrency: int = 1
    inter_request_sleep: float = 2.0


@dataclass(frozen=True)
class GrobidRequestConfig:
    consolidate_header: bool = False
    consolidate_citations: bool = False
    include_raw_citations: bool = False
    include_raw_affiliations: bool = False


@dataclass(frozen=True)
class GrobidConfig:
    grobid_base_url: str
    health_endpoint: str
    process_fulltext_endpoint: str
    config_path: Path
    timeout: GrobidTimeoutConfig
    retry: GrobidRetryConfig
    batch: GrobidBatchConfig
    request: GrobidRequestConfig


@dataclass(frozen=True)
class GrobidResponse:
    status_code: int
    text: str
    elapsed_seconds: float
    endpoint: str
    attempts: int
    retry_count: int
    failure_reasons: list[str]


class GrobidClient:
    """GROBID HTTP client for Scientra Copilot with explicit timeout and retry control."""

    def __init__(
        self,
        base_url: str | None = None,
        config_path: str | Path | None = None,
        health_endpoint: str | None = None,
        process_fulltext_endpoint: str | None = None,
        timeout_seconds: int | float | None = None,
        retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        connect_timeout: int | float | None = None,
        read_timeout: int | float | None = None,
        total_timeout: int | float | None = None,
        max_attempts: int | None = None,
        retry_wait_seconds: int | float | None = None,
    ) -> None:
        config = load_grobid_config(config_path)

        timeout = config.timeout
        if timeout_seconds is not None:
            timeout = GrobidTimeoutConfig(
                connect=timeout.connect,
                read=float(timeout_seconds),
                total=max(float(timeout_seconds), timeout.total),
            )
        timeout = GrobidTimeoutConfig(
            connect=float(connect_timeout) if connect_timeout is not None else timeout.connect,
            read=float(read_timeout) if read_timeout is not None else timeout.read,
            total=float(total_timeout) if total_timeout is not None else timeout.total,
        )

        retry = config.retry
        if retries is not None:
            # Backwards compatibility: the old option meant "extra retries".
            retry = GrobidRetryConfig(
                max_attempts=max(1, int(retries) + 1),
                wait_seconds=retry.wait_seconds,
                backoff_seconds=retry.backoff_seconds,
            )
        if max_attempts is not None:
            retry = GrobidRetryConfig(
                max_attempts=max(1, int(max_attempts)),
                wait_seconds=retry.wait_seconds,
                backoff_seconds=retry.backoff_seconds,
            )
        retry_wait = retry_wait_seconds if retry_wait_seconds is not None else retry_backoff_seconds
        if retry_wait is not None:
            retry = GrobidRetryConfig(
                max_attempts=retry.max_attempts,
                wait_seconds=float(retry_wait),
                backoff_seconds=retry.backoff_seconds,
            )

        self.config = GrobidConfig(
            grobid_base_url=(base_url or config.grobid_base_url).rstrip("/"),
            health_endpoint=normalize_endpoint(health_endpoint or config.health_endpoint),
            process_fulltext_endpoint=normalize_endpoint(
                process_fulltext_endpoint or config.process_fulltext_endpoint
            ),
            config_path=config.config_path,
            timeout=timeout,
            retry=retry,
            batch=config.batch,
            request=config.request,
        )
        self.base_url = self.config.grobid_base_url
        self.health_endpoint = self.config.health_endpoint
        self.process_fulltext_endpoint = self.config.process_fulltext_endpoint
        self.timeout = self.config.timeout
        self.retry = self.config.retry
        self.batch = self.config.batch
        self.request = self.config.request
        self.session = requests.Session()
        # Local Docker GROBID calls must not be sent through a user/system proxy.
        self.session.trust_env = False

    def is_alive(self) -> bool:
        return self.health_status().get("available") is True

    def health_status(self) -> dict[str, Any]:
        url = f"{self.base_url}{self.health_endpoint}"
        started = time.perf_counter()
        try:
            response = self.session.get(
                url,
                timeout=(self.timeout.connect, min(self.timeout.read, 30)),
                headers={"User-Agent": "Scientra-Copilot-PDF-Engine/0.1"},
            )
            body = response.text.strip()
            available = 200 <= response.status_code < 300 and "true" in body.lower()
            return {
                "url": url,
                "available": available,
                "status_code": response.status_code,
                "body": body[:200],
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "error_type": None if available else "grobid_service_unavailable",
                "error": None if available else f"unexpected health response: {response.status_code} {body[:200]}",
            }
        except requests.RequestException as exc:
            return {
                "url": url,
                "available": False,
                "status_code": None,
                "body": "",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "error_type": "grobid_service_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def process_fulltext_document(
        self,
        pdf_path: Path,
        consolidate_header: bool | None = None,
        consolidate_citations: bool | None = None,
        include_raw_citations: bool | None = None,
        include_raw_affiliations: bool | None = None,
    ) -> GrobidResponse:
        if consolidate_header is None:
            consolidate_header = self.request.consolidate_header
        if consolidate_citations is None:
            consolidate_citations = self.request.consolidate_citations
        if include_raw_citations is None:
            include_raw_citations = self.request.include_raw_citations
        if include_raw_affiliations is None:
            include_raw_affiliations = self.request.include_raw_affiliations
        fields = {
            "consolidateHeader": self._flag(consolidate_header),
            "consolidateCitations": self._flag(consolidate_citations),
            "includeRawCitations": self._flag(include_raw_citations),
            "includeRawAffiliations": self._flag(include_raw_affiliations),
        }
        return self._post_pdf(
            endpoint=self.process_fulltext_endpoint,
            pdf_path=pdf_path,
            fields=fields,
        )

    def _post_pdf(
        self,
        endpoint: str,
        pdf_path: Path,
        fields: Mapping[str, str],
    ) -> GrobidResponse:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise GrobidClientError(f"PDF not found: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise GrobidClientError(f"Not a PDF file: {pdf_path}")

        url = f"{self.base_url}{endpoint}"
        started_total = time.perf_counter()
        failure_reasons: list[str] = []
        last_error: Exception | None = None
        last_status_code: int | None = None
        last_response_text: str | None = None
        last_error_type = "grobid_request_failed"

        for attempt in range(1, self.retry.max_attempts + 1):
            elapsed_before_attempt = time.perf_counter() - started_total
            remaining = self.timeout.total - elapsed_before_attempt
            if remaining <= 0:
                last_error = TimeoutError(f"total timeout exceeded after {elapsed_before_attempt:.3f}s")
                failure_reasons.append(f"attempt {attempt}: skipped; total timeout exceeded")
                break

            read_timeout = max(1.0, min(self.timeout.read, remaining))
            attempt_started = time.perf_counter()
            try:
                with pdf_path.open("rb") as handle:
                    response = self.session.post(
                        url,
                        data=dict(fields),
                        files={"input": (pdf_path.name, handle, "application/pdf")},
                        headers={
                            "Accept": "application/xml,text/xml,*/*",
                            "User-Agent": "Scientra-Copilot-PDF-Engine/0.1",
                        },
                        timeout=(self.timeout.connect, read_timeout),
                    )
                attempt_elapsed = time.perf_counter() - attempt_started
                total_elapsed = time.perf_counter() - started_total
                last_status_code = response.status_code
                last_response_text = response.text[:2000]

                if 200 <= response.status_code < 300:
                    if not response.text.strip():
                        last_error_type = "grobid_returned_empty_tei"
                        last_error = GrobidClientError(
                            f"GROBID returned empty TEI for {pdf_path}",
                            attempts=attempt,
                            retry_count=attempt - 1,
                            error_type=last_error_type,
                            status_code=response.status_code,
                            response_text=response.text,
                            elapsed_seconds=total_elapsed,
                        )
                        failure_reasons.append(
                            f"attempt {attempt}: grobid_returned_empty_tei after {attempt_elapsed:.3f}s"
                        )
                    else:
                        return GrobidResponse(
                            status_code=response.status_code,
                            text=response.text,
                            elapsed_seconds=total_elapsed,
                            endpoint=endpoint,
                            attempts=attempt,
                            retry_count=attempt - 1,
                            failure_reasons=failure_reasons,
                        )
                else:
                    body_preview = response.text[:500].replace("\n", " ").strip()
                    last_error_type = (
                        f"grobid_http_{response.status_code}"
                        if response.status_code in {429, 503}
                        else "grobid_http_error"
                    )
                    last_error = GrobidClientError(
                        f"GROBID HTTP {response.status_code} for {pdf_path}: {body_preview}",
                        attempts=attempt,
                        retry_count=attempt - 1,
                        error_type=last_error_type,
                        status_code=response.status_code,
                        response_text=response.text,
                        elapsed_seconds=total_elapsed,
                    )
                    failure_reasons.append(
                        f"attempt {attempt}: {last_error_type} after {attempt_elapsed:.3f}s"
                    )
                    if not self._should_retry_http(response.status_code):
                        break
            except requests.Timeout as exc:
                attempt_elapsed = time.perf_counter() - attempt_started
                last_error = exc
                last_error_type = "grobid_timeout"
                failure_reasons.append(
                    f"attempt {attempt}: grobid_timeout after {attempt_elapsed:.3f}s"
                )
            except requests.RequestException as exc:
                attempt_elapsed = time.perf_counter() - attempt_started
                last_error = exc
                last_error_type = "grobid_service_unavailable"
                failure_reasons.append(
                    f"attempt {attempt}: grobid_service_unavailable/{type(exc).__name__} after {attempt_elapsed:.3f}s"
                )

            if attempt < self.retry.max_attempts:
                remaining_after_attempt = self.timeout.total - (time.perf_counter() - started_total)
                wait_seconds = self._backoff_seconds(attempt)
                if remaining_after_attempt <= wait_seconds:
                    break
                time.sleep(wait_seconds)

        attempts = min(len(failure_reasons), self.retry.max_attempts)
        elapsed_seconds = time.perf_counter() - started_total
        raise GrobidClientError(
            f"GROBID request failed for {pdf_path}: {last_error}; "
            f"attempts={attempts}; failures={failure_reasons}",
            attempts=attempts,
            retry_count=max(0, attempts - 1),
            failure_reasons=failure_reasons,
            error_type=last_error_type,
            status_code=last_status_code,
            response_text=last_response_text or traceback.format_exception_only(type(last_error), last_error)[-1].strip()
            if last_error
            else None,
            elapsed_seconds=elapsed_seconds,
        ) from last_error

    def _backoff_seconds(self, failed_attempt: int) -> float:
        index = failed_attempt - 1
        if 0 <= index < len(self.retry.backoff_seconds):
            return self.retry.backoff_seconds[index]
        return self.retry.wait_seconds

    @staticmethod
    def _flag(value: bool) -> str:
        return "1" if value else "0"

    @staticmethod
    def _should_retry_http(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code <= 599


def load_grobid_config(config_path: str | Path | None = None) -> GrobidConfig:
    path = Path(config_path) if config_path else DEFAULT_GROBID_CONFIG_PATH
    path = path.resolve()
    if not path.exists():
        raise GrobidClientError(f"GROBID config not found: {path}")

    payload = read_yaml_mapping(path)
    base_url = clean_scalar(payload.get("grobid_base_url"))
    health_endpoint = clean_scalar(payload.get("health_endpoint"))
    process_endpoint = clean_scalar(payload.get("process_fulltext_endpoint"))
    missing = [
        name
        for name, value in [
            ("grobid_base_url", base_url),
            ("health_endpoint", health_endpoint),
            ("process_fulltext_endpoint", process_endpoint),
        ]
        if not value
    ]
    if missing:
        raise GrobidClientError(
            f"GROBID config is missing required field(s): {', '.join(missing)}"
        )
    return GrobidConfig(
        grobid_base_url=os.environ.get("GROBID_BASE_URL", base_url).rstrip("/"),
        health_endpoint=normalize_endpoint(health_endpoint),
        process_fulltext_endpoint=normalize_endpoint(process_endpoint),
        config_path=path,
        timeout=parse_timeout_config(payload.get("timeout")),
        retry=parse_retry_config(payload.get("retry")),
        batch=parse_batch_config(payload.get("batch")),
        request=parse_request_config(payload.get("request")),
    )


def parse_timeout_config(value: Any) -> GrobidTimeoutConfig:
    payload = value if isinstance(value, dict) else {}
    env_timeout = os.environ.get("GROBID_TIMEOUT_SECONDS")
    connect = positive_float(payload.get("connect"), 10.0)
    read = positive_float(env_timeout, positive_float(payload.get("read"), 120.0))
    total = positive_float(payload.get("total"), max(600.0, read * 4 + 120.0))
    return GrobidTimeoutConfig(connect=connect, read=read, total=total)


def parse_retry_config(value: Any) -> GrobidRetryConfig:
    payload = value if isinstance(value, dict) else {}
    raw_backoff = payload.get("backoff_seconds")
    if isinstance(raw_backoff, list):
        backoff = tuple(positive_float(item, 0.0) for item in raw_backoff)
        backoff = tuple(item for item in backoff if item > 0)
    else:
        backoff = (10.0, 30.0, 60.0)
    return GrobidRetryConfig(
        max_attempts=max(1, int(positive_float(payload.get("max_attempts"), len(backoff) + 1))),
        wait_seconds=positive_float(payload.get("wait_seconds"), backoff[0] if backoff else 10.0),
        backoff_seconds=backoff or (10.0, 30.0, 60.0),
    )


def parse_batch_config(value: Any) -> GrobidBatchConfig:
    payload = value if isinstance(value, dict) else {}
    return GrobidBatchConfig(
        concurrency=max(1, int(positive_float(os.environ.get("GROBID_MAX_WORKERS"), positive_float(payload.get("concurrency"), 1)))),
        inter_request_sleep=positive_float(
            os.environ.get("GROBID_REQUEST_INTERVAL_SECONDS"),
            positive_float(payload.get("inter_request_sleep"), 2.0),
        ),
    )


def parse_request_config(value: Any) -> GrobidRequestConfig:
    payload = value if isinstance(value, dict) else {}
    return GrobidRequestConfig(
        consolidate_header=truthy(payload.get("consolidateHeader"), False),
        consolidate_citations=truthy(payload.get("consolidateCitations"), False),
        include_raw_citations=truthy(payload.get("includeRawCitations"), False),
        include_raw_affiliations=truthy(payload.get("includeRawAffiliations"), False),
    )


def positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def read_yaml_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        payload = yaml.safe_load(text)
        if not isinstance(payload, dict):
            raise GrobidClientError(f"GROBID config must be a YAML mapping: {path}")
        return payload

    payload: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        payload[key.strip()] = value.strip().strip('"').strip("'")
    return payload


def normalize_endpoint(value: str) -> str:
    value = value.strip()
    if not value:
        raise GrobidClientError("GROBID endpoint cannot be empty")
    return value if value.startswith("/") else f"/{value}"


def clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
