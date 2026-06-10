from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from loguru import logger
except Exception:
    import logging

    class _LoggerCompat:
        def __init__(self) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
            self._logger = logging.getLogger("scientra.summary_agent")

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

    def _format_log(message: str, *args: Any, **kwargs: Any) -> str:
        try:
            return message.format(*args, **kwargs)
        except Exception:
            return message

    logger = _LoggerCompat()


SUMMARY_AGENT_VERSION = "0.1.0"
PROMPT_VERSION = "2026-06-09.v1"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DEFAULT_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
def _detect_project_root() -> Path:
    """Walk up from this file until a 'Config/workflow_config.yaml' is found."""
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()

SECTION_ORDER = [
    "Core Finding",
    "Evidence",
    "Methods",
    "Key Results",
    "Limitations",
    "Relevance to My Research",
]


@dataclass(frozen=True)
class SourceAnchor:
    source_id: str
    source_type: str
    page: str | None
    paragraph: int | None
    section: str | None
    text: str


@dataclass(frozen=True)
class PaperRecord:
    key: str
    paper_id: str
    title: str | None
    doi: str | None
    year: int | None
    metadata: dict[str, Any]
    metadata_yaml_path: Path | None
    metadata_json_path: Path | None
    tei_path: Path | None
    raw_text_path: Path | None


@dataclass(frozen=True)
class AgentSummaryOptions:
    model: str
    base_url: str
    api_key: str | None
    target_min_tokens: int
    target_max_tokens: int
    max_output_tokens: int
    temperature: float
    max_input_chars: int
    max_source_chars: int
    force: bool
    cache_only: bool
    workers: int
    limit: int | None
    timeout_seconds: int
    retries: int
    prompt_only: bool


@dataclass(frozen=True)
class SummaryResult:
    paper_id: str
    status: str
    summary_path: Path | None
    cache_path: Path | None
    prompt_path: Path | None = None
    error: str | None = None


class LLMClient:
    """Generic LLM client supporting Anthropic Messages and OpenAI Chat Completions formats."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: int = 120,
        retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self._format = self._detect_format()

    def _detect_format(self) -> str:
        lower = self.base_url.lower()
        if "anthropic" in lower and "messages" not in lower:
            return "anthropic"
        return "openai"

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        if self._format == "anthropic":
            return self._anthropic_messages(messages, max_tokens, temperature)
        return self._openai_chat(messages, max_tokens, temperature)

    def _anthropic_messages(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        system_msg = ""
        user_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append({"role": "user", "content": msg["content"]})

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_msg:
            payload["system"] = system_msg

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = self._messages_url()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Scientra-Copilot-Summary-Agent/0.1",
        }

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8", errors="replace"))
                    return self._normalize_anthropic_response(raw)
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"HTTP {exc.code}: {error_body[:800]}")
                if not _should_retry_http(exc.code):
                    break
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt < self.retries:
                time.sleep(1.5 * (2**attempt))

        raise RuntimeError(f"LLM request failed: {last_error}") from last_error

    def _openai_chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = self._chat_completions_url()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Scientra-Copilot-Summary-Agent/0.1",
        }

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"HTTP {exc.code}: {error_body[:800]}")
                if not _should_retry_http(exc.code):
                    break
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt < self.retries:
                time.sleep(1.5 * (2**attempt))

        raise RuntimeError(f"LLM request failed: {last_error}") from last_error

    def _messages_url(self) -> str:
        if self.base_url.endswith("/messages"):
            return self.base_url
        if "/anthropic" in self.base_url and not self.base_url.endswith("/v1/messages"):
            return f"{self.base_url}/v1/messages"
        return f"{self.base_url}/v1/messages"

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/v1/chat/completions"

    @staticmethod
    def _normalize_anthropic_response(raw: dict[str, Any]) -> dict[str, Any]:
        content_list = raw.get("content", [])
        text = ""
        for block in content_list:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
        return {
            "choices": [{"message": {"content": text}}],
        }


class SummaryAgent:
    """Generates paper summaries using the configured LLM agent.

    In agent mode, the summary is generated by Claude Code Agent (or any
    configured model) rather than requiring a standalone DEEPSEEK_API_KEY.
    """

    def __init__(
        self,
        root: str | Path = PROJECT_ROOT,
        options: AgentSummaryOptions | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.options = options or default_options()
        self.state_path = self.root / "03_Summary" / "summary_agent_state.json"
        self.failure_path = self.root / "03_Summary" / "failures" / "summary_agent_failures.jsonl"
        self.cache_dir = self.root / "03_Summary" / "cache"
        self.prompt_dir = self.root / "03_Summary" / "agent_prompts"
        self.log_dir = self.root / "07_Workflows" / "logs"
        self.state_lock = threading.Lock()
        self.failure_lock = threading.Lock()
        self.state = self.load_state()

    def ensure_directories(self) -> None:
        for path in [
            self.root / "03_Summary",
            self.root / "03_Summary" / "failures",
            self.cache_dir,
            self.prompt_dir,
            self.log_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def discover_papers(self) -> list[PaperRecord]:
        records: dict[str, dict[str, Path | None]] = {}
        for path in sorted((self.root / "02_Metadata" / "yaml").glob("*.metadata.yaml")):
            key = path.name[: -len(".metadata.yaml")]
            records.setdefault(key, {})["metadata_yaml_path"] = path
        for path in sorted((self.root / "02_Metadata" / "papers").glob("*.metadata.json")):
            key = path.name[: -len(".metadata.json")]
            records.setdefault(key, {})["metadata_json_path"] = path
        for path in sorted((self.root / "02_Metadata" / "tei").glob("*.tei.xml")):
            key = path.name[: -len(".tei.xml")]
            records.setdefault(key, {})["tei_path"] = path
        for path in sorted((self.root / "03_Summary" / "raw_text").glob("*.txt")):
            key = path.stem
            records.setdefault(key, {})["raw_text_path"] = path

        papers: list[PaperRecord] = []
        for key, paths in sorted(records.items()):
            metadata = _load_metadata_payload(paths.get("metadata_yaml_path"), paths.get("metadata_json_path"))
            paper_id = str(metadata.get("paper_id") or key)
            raw_text_path = _resolve_raw_text_path(self.root, key, paper_id, paths.get("raw_text_path"), metadata)
            tei_path = _resolve_tei_path(self.root, key, paper_id, paths.get("tei_path"), metadata)
            papers.append(
                PaperRecord(
                    key=key,
                    paper_id=paper_id,
                    title=_clean_scalar(metadata.get("title") or _dig(metadata, "metadata", "title")),
                    doi=_clean_scalar(metadata.get("doi") or _dig(metadata, "metadata", "doi")),
                    year=_normalize_year(metadata.get("year") or _dig(metadata, "metadata", "year")),
                    metadata=metadata,
                    metadata_yaml_path=paths.get("metadata_yaml_path"),
                    metadata_json_path=paths.get("metadata_json_path"),
                    tei_path=tei_path,
                    raw_text_path=raw_text_path,
                )
            )

        if self.options.limit is not None:
            papers = papers[: self.options.limit]
        return papers

    def summarize_all(self) -> list[SummaryResult]:
        self.ensure_directories()
        papers = self.discover_papers()
        logger.info("Agent Summary: found {} papers", len(papers))
        if not papers:
            return []

        results: list[SummaryResult] = []
        for paper in papers:
            results.append(self.summarize_paper(paper))
        return results

    def summarize_by_paper_id(self, paper_id: str) -> SummaryResult:
        self.ensure_directories()
        for paper in self.discover_papers():
            if paper.paper_id == paper_id or paper.key == paper_id:
                return self.summarize_paper(paper)
        raise ValueError(f"paper not found: {paper_id}")

    def summarize_paper(self, paper: PaperRecord) -> SummaryResult:
        stage = "start"
        summary_path = self._summary_path(paper.paper_id)
        try:
            stage = "source_anchors"
            sources = _build_source_anchors(paper, self.root)
            selected_sources = _select_sources(
                sources,
                max_input_chars=self.options.max_input_chars,
                max_source_chars=self.options.max_source_chars,
            )
            if not selected_sources:
                raise ValueError("no source text available")

            cache_key = self._cache_key(paper, selected_sources)
            cache_path = self._cache_path(paper.paper_id, cache_key)
            previous_state = self.state.get("papers", {}).get(paper.paper_id, {})

            if (
                not self.options.force
                and summary_path.exists()
                and previous_state.get("cache_key") == cache_key
            ):
                logger.info("Agent: skipping unchanged summary: {}", paper.paper_id)
                return SummaryResult(paper.paper_id, "skipped", summary_path, cache_path)

            if not self.options.force and cache_path.exists():
                logger.info("Agent: using cached summary: {}", paper.paper_id)
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                _write_text_atomic(summary_path, _render_summary_markdown(cached))
                self._mark_state(paper, cache_key, summary_path, cache_path, status="cached")
                return SummaryResult(paper.paper_id, "cached", summary_path, cache_path)

            if self.options.cache_only:
                raise RuntimeError(f"cache miss for {paper.paper_id}; cache-only mode is enabled")

            stage = "prompt"
            messages = _build_messages(
                paper=paper,
                sources=selected_sources,
                target_min_tokens=self.options.target_min_tokens,
                target_max_tokens=self.options.target_max_tokens,
            )

            if self.options.prompt_only or not self.options.api_key:
                return self._write_prompt_file(paper, messages, selected_sources, summary_path)

            stage = "llm_call"
            client = LLMClient(
                api_key=self.options.api_key,
                base_url=self.options.base_url,
                model=self.options.model,
                timeout_seconds=self.options.timeout_seconds,
                retries=self.options.retries,
            )
            response = client.chat_completion(
                messages=messages,
                max_tokens=self.options.max_output_tokens,
                temperature=self.options.temperature,
            )

            stage = "parse_response"
            model_content = _extract_message_content(response)
            summary_payload = _parse_model_summary(model_content)
            normalized = _normalize_summary_payload(summary_payload)
            cache_payload = {
                "paper_id": paper.paper_id,
                "paper_key": paper.key,
                "title": paper.title,
                "doi": paper.doi,
                "year": paper.year,
                "summary_agent_version": SUMMARY_AGENT_VERSION,
                "prompt_version": PROMPT_VERSION,
                "model": self.options.model,
                "target_tokens": {
                    "min": self.options.target_min_tokens,
                    "max": self.options.target_max_tokens,
                },
                "source_hash": _hash_sources(selected_sources),
                "generated_at": _utc_now(),
                "sections": normalized,
                "citation_sources": [asdict(source) for source in selected_sources],
                "raw_model_response": response,
            }

            stage = "write"
            _write_json_atomic(cache_path, cache_payload)
            _write_text_atomic(summary_path, _render_summary_markdown(cache_payload))
            self._mark_state(paper, cache_key, summary_path, cache_path, status="succeeded")
            logger.info("Agent Summary generated: {}", summary_path)
            return SummaryResult(paper.paper_id, "succeeded", summary_path, cache_path)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.error("Agent Summary failed at stage {} for {}: {}", stage, paper.paper_id, error)
            self._record_failure(paper, stage, exc)
            self._mark_state(paper, None, summary_path, None, status="failed", error=error)
            return SummaryResult(paper.paper_id, "failed", summary_path, None, error=error)

    def _write_prompt_file(
        self,
        paper: PaperRecord,
        messages: list[dict[str, str]],
        sources: list[SourceAnchor],
        summary_path: Path,
    ) -> SummaryResult:
        # If summary.md already exists (resolved by Claude Code Agent),
        # skip re-prompting and return "resolved" to prevent infinite pending_agent loop.
        if summary_path.exists():
            logger.info("Agent: summary already resolved, skipping: {}", paper.paper_id)
            return SummaryResult(paper.paper_id, "resolved", summary_path, None)

        prompt_path = self.prompt_dir / _safe_path_name(paper.paper_id) / "prompt.json"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_payload = {
            "paper_id": paper.paper_id,
            "paper_key": paper.key,
            "title": paper.title,
            "doi": paper.doi,
            "year": paper.year,
            "messages": messages,
            "source_count": len(sources),
            "generated_at": _utc_now(),
            "summary_agent_version": SUMMARY_AGENT_VERSION,
            "prompt_version": PROMPT_VERSION,
            "target_path": str(summary_path),
        }
        _write_json_atomic(prompt_path, prompt_payload)
        logger.info("Agent prompt written (no API key): {}", prompt_path)
        return SummaryResult(
            paper.paper_id,
            "pending_agent",
            summary_path,
            None,
            prompt_path=prompt_path,
        )

    def _summary_path(self, paper_id: str) -> Path:
        return self.root / "03_Summary" / _safe_path_name(paper_id) / "summary.md"

    def _cache_path(self, paper_id: str, cache_key: str) -> Path:
        return self.cache_dir / _safe_path_name(paper_id) / f"{cache_key}.summary.json"

    def _cache_key(self, paper: PaperRecord, sources: list[SourceAnchor]) -> str:
        payload = {
            "paper_id": paper.paper_id,
            "model": self.options.model,
            "summary_agent_version": SUMMARY_AGENT_VERSION,
            "prompt_version": PROMPT_VERSION,
            "target_min_tokens": self.options.target_min_tokens,
            "target_max_tokens": self.options.target_max_tokens,
            "source_hash": _hash_sources(sources),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": SUMMARY_AGENT_VERSION, "papers": {}}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.state_path.with_suffix(".corrupt.json")
            self.state_path.replace(backup)
            logger.warning("Agent state file was corrupt and moved to {}", backup)
            return {"version": SUMMARY_AGENT_VERSION, "papers": {}}

    def _mark_state(
        self,
        paper: PaperRecord,
        cache_key: str | None,
        summary_path: Path | None,
        cache_path: Path | None,
        status: str,
        error: str | None = None,
    ) -> None:
        with self.state_lock:
            self.state.setdefault("papers", {})[paper.paper_id] = {
                "paper_key": paper.key,
                "status": status,
                "cache_key": cache_key,
                "summary_path": str(summary_path) if summary_path else None,
                "cache_path": str(cache_path) if cache_path else None,
                "model": self.options.model,
                "summary_agent_version": SUMMARY_AGENT_VERSION,
                "updated_at": _utc_now(),
                "error": error,
            }
            self.state["version"] = SUMMARY_AGENT_VERSION
            self.state["updated_at"] = _utc_now()
            _write_json_atomic(self.state_path, self.state)

    def _record_failure(self, paper: PaperRecord, stage: str, error: Exception) -> None:
        payload = {
            "timestamp": _utc_now(),
            "paper_id": paper.paper_id,
            "paper_key": paper.key,
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
        with self.failure_lock:
            self.failure_path.parent.mkdir(parents=True, exist_ok=True)
            with self.failure_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# generate_summary_via_agent — the canonical entry point for Agent Mode
# ---------------------------------------------------------------------------


def generate_summary_via_agent(
    raw_text: str,
    metadata: dict[str, Any],
    tags: dict[str, Any] | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Generate a structured summary via the configured agent model.

    This is the primary entry point for the Agent SDK and workflow runner
    when summary_mode is "agent".

    Args:
        raw_text: Full raw text of the paper.
        metadata: Parsed metadata dict (title, authors, doi, year, abstract, etc.).
        tags: Optional assigned tags dict.
        model: Override model name.
        base_url: Override API base URL.
        api_key: Override API key.

    Returns:
        A dict with keys: sections (dict), citation_sources (list), model, generated_at.
    """
    resolved_model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
    resolved_base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL)
    resolved_api_key = api_key or _resolve_api_key()

    paper = PaperRecord(
        key=metadata.get("paper_id", "unknown"),
        paper_id=str(metadata.get("paper_id", "unknown")),
        title=_clean_scalar(metadata.get("title")),
        doi=_clean_scalar(metadata.get("doi")),
        year=_normalize_year(metadata.get("year")),
        metadata=metadata,
        metadata_yaml_path=None,
        metadata_json_path=None,
        tei_path=None,
        raw_text_path=None,
    )

    source = SourceAnchor(
        source_id="S001",
        source_type="raw_text",
        page=None,
        paragraph=0,
        section="Full Text",
        text=raw_text[:180_000],
    )
    sources = [source]

    messages = _build_messages(
        paper=paper,
        sources=sources,
        target_min_tokens=500,
        target_max_tokens=1000,
    )

    if not resolved_api_key:
        return {
            "status": "pending_agent",
            "paper_id": paper.paper_id,
            "messages": messages,
            "sources": [asdict(s) for s in sources],
            "error": "No API key available; prompt prepared for agent resolution.",
        }

    client = LLMClient(
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        model=resolved_model,
    )
    response = client.chat_completion(messages=messages, max_tokens=4096, temperature=0.2)
    model_content = _extract_message_content(response)
    summary_payload = _parse_model_summary(model_content)
    normalized = _normalize_summary_payload(summary_payload)

    return {
        "status": "succeeded",
        "paper_id": paper.paper_id,
        "sections": normalized,
        "citation_sources": [asdict(s) for s in sources],
        "model": resolved_model,
        "generated_at": _utc_now(),
        "raw_model_response": response,
    }


# ---------------------------------------------------------------------------
# Source building (mirrors summary_engine.py logic)
# ---------------------------------------------------------------------------


def _build_source_anchors(paper: PaperRecord, root: Path) -> list[SourceAnchor]:
    sources: list[SourceAnchor] = []
    abstract = _clean_scalar(paper.metadata.get("abstract"))
    if abstract:
        sources.append(
            SourceAnchor(source_id="", source_type="abstract", page=None, paragraph=0, section="Abstract", text=abstract)
        )

    summary_path = _find_existing_summary_path(root, paper)
    if summary_path:
        sources.extend(_parse_markdown_sources(summary_path, source_type="summary"))

    body_sources: list[SourceAnchor] = []
    if paper.tei_path and paper.tei_path.exists():
        body_sources = _parse_tei_body_sources(paper.tei_path)
    elif paper.metadata_json_path and paper.metadata_json_path.exists():
        body_sources = _parse_metadata_json_sources(paper.metadata_json_path)

    if body_sources:
        sources.extend(body_sources)
    elif paper.raw_text_path and paper.raw_text_path.exists():
        sources.extend(_parse_markdown_sources(paper.raw_text_path, source_type="raw_text"))

    for chunk_path in _find_chunk_paths(root, paper):
        if chunk_path.suffix.lower() == ".json":
            sources.extend(_parse_json_chunk_sources(chunk_path))
        else:
            sources.extend(_parse_markdown_sources(chunk_path, source_type="chunks"))

    deduped = _dedupe_sources(sources)
    return [
        SourceAnchor(
            source_id=f"S{index:03d}",
            source_type=source.source_type,
            page=source.page,
            paragraph=source.paragraph,
            section=source.section,
            text=source.text,
        )
        for index, source in enumerate(deduped, start=1)
    ]


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _build_messages(
    paper: PaperRecord,
    sources: list[SourceAnchor],
    target_min_tokens: int,
    target_max_tokens: int,
) -> list[dict[str, str]]:
    system = (
        "You are Scientra Copilot Summary Agent. Compress a scientific paper into a faithful "
        "500-1000 token structured summary. Use only the provided sources. Do not invent facts. "
        "Every substantive claim must cite one or more provided source_id values. Return strict JSON only. "
        "If a claim cannot be supported by a listed source_id, omit it."
    )
    user = "\n".join(
        [
            "Create a structured paper summary.",
            "",
            "Required JSON keys:",
            json.dumps(SECTION_ORDER, ensure_ascii=False),
            "",
            'Each key must map to a list of objects: {"text": "one concise claim", "citations": ["S001", "S002"]}',
            "",
            f"Target length: {target_min_tokens}-{target_max_tokens} tokens total.",
            "Citation rules:",
            "- Use only source_id values listed below.",
            "- Do not cite missing source IDs.",
            "- Every item in every section must include at least one citation.",
            "- Do not include uncited claims, explanations, or recommendations.",
            "- For relevance, explain only source-grounded relevance to toxin/receptor/mechanism research.",
            "",
            "Paper metadata:",
            json.dumps(
                {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "doi": paper.doi,
                    "year": paper.year,
                    "assigned_tags": paper.metadata.get("assigned_tags"),
                    "candidate_tags": paper.metadata.get("candidate_tags"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "Sources:",
            *[_format_source_block(source) for source in sources],
            "",
            "Return JSON only. Do not wrap it in markdown.",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _format_source_block(source: SourceAnchor) -> str:
    return "\n".join(
        [
            f"<SOURCE {source.source_id}>",
            f"source_type: {source.source_type}",
            f"page: {source.page or 'unknown'}",
            f"paragraph: {source.paragraph if source.paragraph is not None else 'unknown'}",
            f"section: {source.section or 'unknown'}",
            f"text: {source.text}",
            f"</SOURCE {source.source_id}>",
        ]
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not choices:
        raise ValueError("LLM response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        reasoning_content = message.get("reasoning_content")
        if reasoning_content and "{" in reasoning_content and "}" in reasoning_content:
            return str(reasoning_content)
    if not content:
        raise ValueError("LLM response message has no content")
    return content


def _parse_model_summary(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _normalize_summary_payload(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {}
    for section in SECTION_ORDER:
        items = payload.get(section, [])
        if isinstance(items, str):
            items = [{"text": items, "citations": []}]
        elif isinstance(items, dict):
            items = [items]
        cleaned: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text = _clean_scalar(item.get("text"))
            citations = item.get("citations", [])
            if isinstance(citations, str):
                citations = [citations]
            citations = [_clean_scalar(c) for c in citations if _clean_scalar(c)]
            if text:
                cleaned.append({"text": text, "citations": citations})
        normalized[section] = cleaned
    return normalized


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_summary_markdown(payload: dict[str, Any]) -> str:
    sources_by_id = {
        source["source_id"]: source
        for source in payload.get("citation_sources", [])
        if source.get("source_id")
    }
    lines: list[str] = []

    for section in SECTION_ORDER:
        lines.extend([f"# {section}", ""])
        items = payload.get("sections", {}).get(section, [])
        wrote_item = False
        for item in items:
            text = _clean_scalar(item.get("text")) or ""
            citations = item.get("citations", [])
            if not text or not citations:
                continue
            citation_text = _format_citations(citations, sources_by_id)
            lines.append(f"- {text}{citation_text}")
            wrote_item = True
        if not wrote_item:
            lines.append("- No sourced statement generated.")
        lines.append("")

    lines.extend(["# Citation Anchors", ""])
    used_ids = _collect_used_citation_ids(payload)
    if not used_ids:
        lines.append("- No source IDs were cited by the model output.")
    else:
        for source_id in used_ids:
            source = sources_by_id.get(source_id)
            if not source:
                lines.append(f"- {source_id}: unresolved source")
                continue
            source_section = _compact_source_section(
                source.get("section") or source.get("source_type") or "unknown"
            )
            lines.append(
                "- "
                + f"{source_id}: source={source.get('source_type')}, "
                + f"page={source.get('page') or 'unknown'}, "
                + f"paragraph={source.get('paragraph') if source.get('paragraph') is not None else 'unknown'}, "
                + f"source_section={source_section}"
            )
    lines.append("")
    return "\n".join(lines)


def _format_citations(citations: list[str], sources_by_id: dict[str, dict[str, Any]]) -> str:
    resolved: list[str] = []
    for source_id in citations:
        source = sources_by_id.get(source_id)
        if not source:
            resolved.append(source_id)
            continue
        page = source.get("page") or "unknown"
        paragraph = source.get("paragraph")
        paragraph_text = paragraph if paragraph is not None else "unknown"
        source_section = _compact_source_section(source.get("section") or source.get("source_type") or "unknown")
        resolved.append(f"{source_id} source_section={source_section} page={page} paragraph={paragraph_text}")
    return f" ({'; '.join(resolved)})" if resolved else ""


def _compact_source_section(value: Any, limit: int = 64) -> str:
    section = _clean_scalar(value) or "unknown"
    section = re.sub(r"\s+", " ", section).strip()
    if section.lower().startswith("untitled "):
        return "Untitled"
    for marker in (" Here, ", " We next ", " pTc is ", " Dynabeads "):
        marker_index = section.find(marker)
        if marker_index >= 8:
            section = section[:marker_index].strip()
            break
    if len(section) <= limit:
        return section
    return section[: limit - 3].rstrip(" ,.;") + "..."


def _collect_used_citation_ids(payload: dict[str, Any]) -> list[str]:
    citations: list[str] = []
    for section in payload.get("sections", {}).values():
        for item in section:
            citations.extend(item.get("citations", []))
    return _unique_preserve_order(citations)


# ---------------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------------


def _select_sources(
    sources: list[SourceAnchor],
    max_input_chars: int,
    max_source_chars: int,
) -> list[SourceAnchor]:
    selected: list[SourceAnchor] = []
    total_chars = 0
    for source in sources:
        truncated = source.text
        if len(truncated) > max_source_chars:
            truncated = truncated[: max_source_chars - 3].rstrip(" ,.;") + "..."
        char_count = len(truncated)
        if total_chars + char_count > max_input_chars:
            break
        selected.append(
            SourceAnchor(
                source_id=source.source_id,
                source_type=source.source_type,
                page=source.page,
                paragraph=source.paragraph,
                section=source.section,
                text=truncated,
            )
        )
        total_chars += char_count
    return selected


# ---------------------------------------------------------------------------
# TEI / markdown / chunk parsing
# ---------------------------------------------------------------------------


def _parse_tei_body_sources(path: Path) -> list[SourceAnchor]:
    from xml.etree import ElementTree as ET

    root_elem = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}

    def _local_name(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    body = None
    for elem in root_elem.iter():
        if _local_name(elem.tag) == "body":
            body = elem
            break

    if body is None:
        return []

    sources: list[SourceAnchor] = []
    paragraph_counter = 0
    current_page: str | None = None
    heading_stack: list[str] = []

    def walk(node: Any) -> None:
        nonlocal paragraph_counter, current_page
        name = _local_name(node.tag)

        if name == "pb":
            page_n = node.attrib.get("n")
            if page_n:
                current_page = str(page_n)
            return

        if name == "div":
            head = node.find("{http://www.tei-c.org/ns/1.0}head")
            if head is not None and head.text:
                heading_stack.append(str(head.text).strip())

        if name == "p":
            text = " ".join(node.itertext()).strip()
            if len(text) >= 50:
                paragraph_counter += 1
                section_label = " > ".join(heading_stack) if heading_stack else "Body"
                sources.append(
                    SourceAnchor(
                        source_id="",
                        source_type="tei_body",
                        page=current_page,
                        paragraph=paragraph_counter,
                        section=section_label,
                        text=text,
                    )
                )

        for child in node:
            walk(child)

        if name == "div" and heading_stack:
            heading_stack.pop()

    walk(body)
    return sources


def _parse_metadata_json_sources(path: Path) -> list[SourceAnchor]:
    data = json.loads(path.read_text(encoding="utf-8"))
    body_text = data.get("body_text") or data.get("fulltext") or ""
    if isinstance(body_text, list):
        sources: list[SourceAnchor] = []
        for i, item in enumerate(body_text):
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            if len(text.strip()) >= 50:
                sources.append(
                    SourceAnchor(
                        source_id="",
                        source_type="body",
                        page=str(item.get("page", "")) if isinstance(item, dict) else "",
                        paragraph=i + 1,
                        section=item.get("section", "Body") if isinstance(item, dict) else "Body",
                        text=text.strip(),
                    )
                )
        return sources
    elif isinstance(body_text, str) and body_text.strip():
        paragraphs = [p.strip() for p in body_text.split("\n\n") if len(p.strip()) >= 50]
        return [
            SourceAnchor(source_id="", source_type="body", page="", paragraph=i + 1, section="Body", text=p)
            for i, p in enumerate(paragraphs)
        ]
    return []


def _parse_markdown_sources(path: Path, source_type: str) -> list[SourceAnchor]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    sources: list[SourceAnchor] = []
    current_section = "Unknown"
    paragraph_counter = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            current_section = stripped[2:].strip()
        elif len(stripped) >= 50 and not stripped.startswith("```"):
            paragraph_counter += 1
            sources.append(
                SourceAnchor(
                    source_id="",
                    source_type=source_type,
                    page=None,
                    paragraph=paragraph_counter,
                    section=current_section,
                    text=stripped,
                )
            )
    return sources


def _parse_json_chunk_sources(path: Path) -> list[SourceAnchor]:
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks = data if isinstance(data, list) else data.get("chunks", [])
    sources: list[SourceAnchor] = []
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
        if len(text.strip()) >= 50:
            sources.append(
                SourceAnchor(
                    source_id="",
                    source_type="chunks",
                    page=None,
                    paragraph=i + 1,
                    section=chunk.get("section", "Chunk") if isinstance(chunk, dict) else "Chunk",
                    text=text.strip(),
                )
            )
    return sources


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_api_key() -> str | None:
    for env_var in ["ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "SCIENTRA_API_KEY"]:
        key = os.environ.get(env_var)
        if key:
            return key
    return None


def _clean_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _dig(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


def _normalize_year(value: Any) -> int | None:
    if value is None:
        return None
    try:
        year = int(str(value).strip()[:4])
        if 1900 <= year <= 2100:
            return year
    except (ValueError, TypeError):
        pass
    return None


def _hash_sources(sources: list[SourceAnchor]) -> str:
    payload = [{"source_id": s.source_id, "text_hash": hashlib.sha256(s.text.encode()).hexdigest()[:16]} for s in sources]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _dedupe_sources(sources: list[SourceAnchor]) -> list[SourceAnchor]:
    seen: set[str] = set()
    result: list[SourceAnchor] = []
    for source in sources:
        text_hash = hashlib.sha256(source.text.encode()).hexdigest()
        if text_hash in seen:
            continue
        seen.add(text_hash)
        result.append(source)
    return result


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _safe_path_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_") or "unknown"


def _should_retry_http(code: int) -> bool:
    return code in (429, 500, 502, 503, 504)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _load_metadata_payload(yaml_path: Path | None, json_path: Path | None) -> dict[str, Any]:
    if yaml_path and yaml_path.exists():
        return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if json_path and json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))
    return {}


def _resolve_raw_text_path(
    root: Path, key: str, paper_id: str, explicit: Path | None, metadata: dict[str, Any]
) -> Path | None:
    candidates = [
        explicit,
        _path_or_none(_dig(metadata, "outputs", "raw_text_path")),
        root / "03_Summary" / "raw_text" / f"{key}.txt",
        root / "03_Summary" / "raw_text" / f"{paper_id}.txt",
    ]
    return _first_existing_path(candidates)


def _resolve_tei_path(
    root: Path, key: str, paper_id: str, explicit: Path | None, metadata: dict[str, Any]
) -> Path | None:
    candidates = [
        explicit,
        _path_or_none(_dig(metadata, "outputs", "tei_path")),
        root / "02_Metadata" / "tei" / f"{key}.tei.xml",
        root / "02_Metadata" / "tei" / f"{paper_id}.tei.xml",
    ]
    return _first_existing_path(candidates)


def _find_existing_summary_path(root: Path, paper: PaperRecord) -> Path | None:
    canonical_output = root / "03_Summary" / _safe_path_name(paper.paper_id) / "summary.md"
    candidates = [
        root / "03_Summary" / _safe_path_name(paper.key) / "summary.md",
        root / "03_Summary" / "summaries" / f"{paper.paper_id}.md",
        root / "03_Summary" / "summaries" / f"{paper.key}.md",
        root / "03_Summary" / f"{paper.paper_id}.summary.md",
        root / "03_Summary" / f"{paper.key}.summary.md",
    ]
    for path in candidates:
        if path.exists() and path.resolve() != canonical_output.resolve():
            return path
    return None


def _find_chunk_paths(root: Path, paper: PaperRecord) -> list[Path]:
    candidates: list[Path] = []
    chunk_dir = root / "03_Summary" / "chunks"
    for pattern in [f"{paper.paper_id}*.json", f"{paper.key}*.json", f"{paper.paper_id}*.md", f"{paper.key}*.md"]:
        candidates.extend(sorted(chunk_dir.glob(pattern)))
    return candidates


def _path_or_none(value: Any) -> Path | None:
    if value is None:
        return None
    try:
        path = Path(str(value))
        return path if path.exists() else None
    except (ValueError, TypeError):
        return None


def _first_existing_path(candidates: list[Path | None]) -> Path | None:
    for path in candidates:
        if path and path.exists():
            return path
    return None


# ---------------------------------------------------------------------------
# Options / CLI
# ---------------------------------------------------------------------------


def default_options() -> AgentSummaryOptions:
    return AgentSummaryOptions(
        model=os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL),
        api_key=_resolve_api_key(),
        target_min_tokens=500,
        target_max_tokens=1000,
        max_output_tokens=4096,
        temperature=0.2,
        max_input_chars=180_000,
        max_source_chars=2_000,
        force=False,
        cache_only=False,
        workers=1,
        limit=None,
        timeout_seconds=120,
        retries=2,
        prompt_only=False,
    )


def options_from_args(args: argparse.Namespace) -> AgentSummaryOptions:
    return AgentSummaryOptions(
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key or _resolve_api_key(),
        target_min_tokens=args.target_min_tokens,
        target_max_tokens=args.target_max_tokens,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
        max_input_chars=args.max_input_chars,
        max_source_chars=args.max_source_chars,
        force=args.force or args.regenerate,
        cache_only=args.cache_only,
        workers=args.workers,
        limit=args.limit,
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
        prompt_only=args.prompt_only,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Scientra Copilot paper summaries via Agent Mode (Claude Code Agent).",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--all", action="store_true", help="Summarize all discovered papers.")
    selector.add_argument("--paper-id", help="Summarize one paper_id or paper key.")

    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--target-min-tokens", type=int, default=500)
    parser.add_argument("--target-max-tokens", type=int, default=1000)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-input-chars", type=int, default=180_000)
    parser.add_argument("--max-source-chars", type=int, default=2_000)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Force a fresh LLM request.")
    parser.add_argument("--regenerate", action="store_true", help="Alias for --force.")
    parser.add_argument("--cache-only", action="store_true", help="Use cache only; fail on cache miss.")
    parser.add_argument("--prompt-only", action="store_true", help="Write prompt files only, no API call.")
    parser.add_argument("--json", action="store_true", help="Print JSON run summary.")
    return parser


def configure_logging(root: Path) -> Path:
    log_dir = root / "07_Workflows" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"summary_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    try:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(log_path, level="INFO", rotation="10 MB", retention=20, encoding="utf-8")
    except AttributeError:
        pass
    return log_path


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = args.root.resolve()
    log_path = configure_logging(root)
    options = options_from_args(args)
    agent = SummaryAgent(root=root, options=options)

    logger.info("Summary Agent started (mode=agent)")
    logger.info("Log file: {}", log_path)
    logger.info("Model: {}", options.model)
    logger.info("Base URL: {}", options.base_url)
    logger.info("API key: {}", "present" if options.api_key else "missing (prompt-only mode)")
    logger.info("Force regenerate: {}", options.force)

    if args.paper_id:
        results = [agent.summarize_by_paper_id(args.paper_id)]
    else:
        results = agent.summarize_all()

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    payload = {
        "summary_agent_version": SUMMARY_AGENT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": options.model,
        "results": [
            {
                "paper_id": r.paper_id,
                "status": r.status,
                "summary_path": str(r.summary_path) if r.summary_path else None,
                "prompt_path": str(r.prompt_path) if r.prompt_path else None,
                "error": r.error,
            }
            for r in results
        ],
        "counts": counts,
        "mode": "agent",
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(f"{result.status}: {result.paper_id}")
        print(f"\nCounts: {counts}")

    has_pending = counts.get("pending_agent", 0) > 0
    if has_pending:
        logger.warning(
            "{} paper(s) in pending_agent state — prompts written to {}. "
            "Resolve by generating summaries via Claude Code Agent.",
            counts["pending_agent"],
            agent.prompt_dir,
        )

    failed = counts.get("failed", 0)
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
