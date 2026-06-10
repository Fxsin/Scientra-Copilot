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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal environments
    import logging

    class _LoggerCompat:
        def __init__(self) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
            self._logger = logging.getLogger("scientra.summary_engine")

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


SUMMARY_ENGINE_VERSION = "0.1.0"
PROMPT_VERSION = "2026-06-08.v1"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
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
SECTION_ALIASES = {
    "core_finding": "Core Finding",
    "core finding": "Core Finding",
    "evidence": "Evidence",
    "methods": "Methods",
    "key_results": "Key Results",
    "key results": "Key Results",
    "limitations": "Limitations",
    "relevance_to_my_research": "Relevance to My Research",
    "relevance to my research": "Relevance to My Research",
    "research_relevance": "Relevance to My Research",
    "research relevance": "Relevance to My Research",
}


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
class SummaryOptions:
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


@dataclass(frozen=True)
class SummaryResult:
    paper_id: str
    status: str
    summary_path: Path | None
    cache_path: Path | None
    error: str | None = None


class DeepSeekClient:
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

    def chat_completion(
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
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            request = urllib.request.Request(
                self.chat_completions_url(),
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Scientra-Copilot-Summary-Engine/0.1",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"HTTP {exc.code}: {error_body[:800]}")
                if not should_retry_http(exc.code):
                    break
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc

            if attempt < self.retries:
                time.sleep(1.5 * (2**attempt))

        raise RuntimeError(f"DeepSeek request failed: {last_error}") from last_error

    def chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"


class SummaryEngine:
    def __init__(
        self,
        root: str | Path = PROJECT_ROOT,
        options: SummaryOptions | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.options = options or default_options()
        self.state_path = self.root / "03_Summary" / "summary_engine_state.json"
        self.failure_path = self.root / "03_Summary" / "failures" / "summary_engine_failures.jsonl"
        self.cache_dir = self.root / "03_Summary" / "cache"
        self.log_dir = self.root / "07_Workflows" / "logs"
        self.state_lock = threading.Lock()
        self.failure_lock = threading.Lock()
        self.state = self.load_state()

    def ensure_directories(self) -> None:
        for path in [
            self.root / "03_Summary",
            self.root / "03_Summary" / "failures",
            self.cache_dir,
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
            metadata = load_metadata_payload(paths.get("metadata_yaml_path"), paths.get("metadata_json_path"))
            paper_id = str(metadata.get("paper_id") or key)
            raw_text_path = resolve_raw_text_path(
                self.root,
                key,
                paper_id,
                paths.get("raw_text_path"),
                metadata,
            )
            tei_path = resolve_tei_path(
                self.root,
                key,
                paper_id,
                paths.get("tei_path"),
                metadata,
            )
            papers.append(
                PaperRecord(
                    key=key,
                    paper_id=paper_id,
                    title=clean_scalar(metadata.get("title") or dig(metadata, "metadata", "title")),
                    doi=clean_scalar(metadata.get("doi") or dig(metadata, "metadata", "doi")),
                    year=normalize_year(metadata.get("year") or dig(metadata, "metadata", "year")),
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
        logger.info("Found {} papers for summary generation", len(papers))
        if not papers:
            return []

        workers = max(1, self.options.workers)
        if workers == 1:
            return [self.summarize_paper(paper) for paper in papers]

        results: list[SummaryResult] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self.summarize_paper, paper) for paper in papers]
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def summarize_by_paper_id(self, paper_id: str) -> SummaryResult:
        self.ensure_directories()
        for paper in self.discover_papers():
            if paper.paper_id == paper_id or paper.key == paper_id:
                return self.summarize_paper(paper)
        raise ValueError(f"paper not found: {paper_id}")

    def summarize_paper(self, paper: PaperRecord) -> SummaryResult:
        stage = "start"
        summary_path = self.summary_path(paper.paper_id)
        try:
            stage = "source_anchors"
            sources = build_source_anchors(paper, self.root)
            selected_sources = select_sources(
                sources,
                max_input_chars=self.options.max_input_chars,
                max_source_chars=self.options.max_source_chars,
            )
            if not selected_sources:
                raise ValueError("no source text available")

            cache_key = self.cache_key(paper, selected_sources)
            cache_path = self.cache_path(paper.paper_id, cache_key)
            previous_state = self.state.get("papers", {}).get(paper.paper_id, {})

            if (
                not self.options.force
                and summary_path.exists()
                and previous_state.get("cache_key") == cache_key
            ):
                logger.info("Skipping unchanged summary: {}", paper.paper_id)
                return SummaryResult(paper.paper_id, "skipped", summary_path, cache_path)

            if not self.options.force and cache_path.exists():
                logger.info("Using cached summary: {}", paper.paper_id)
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                write_text_atomic(summary_path, render_summary_markdown(cached))
                self.mark_state(paper, cache_key, summary_path, cache_path, status="cached")
                return SummaryResult(paper.paper_id, "cached", summary_path, cache_path)

            if self.options.cache_only:
                raise RuntimeError(f"cache miss for {paper.paper_id}; cache-only mode is enabled")
            if not self.options.api_key:
                raise RuntimeError("DEEPSEEK_API_KEY is required when cache is unavailable")

            stage = "prompt"
            messages = build_messages(
                paper=paper,
                sources=selected_sources,
                target_min_tokens=self.options.target_min_tokens,
                target_max_tokens=self.options.target_max_tokens,
            )

            stage = "deepseek"
            client = DeepSeekClient(
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
            model_content = extract_message_content(response)
            summary_payload = parse_model_summary(model_content)
            normalized = normalize_summary_payload(summary_payload)
            cache_payload = {
                "paper_id": paper.paper_id,
                "paper_key": paper.key,
                "title": paper.title,
                "doi": paper.doi,
                "year": paper.year,
                "summary_engine_version": SUMMARY_ENGINE_VERSION,
                "prompt_version": PROMPT_VERSION,
                "model": self.options.model,
                "target_tokens": {
                    "min": self.options.target_min_tokens,
                    "max": self.options.target_max_tokens,
                },
                "source_hash": hash_sources(selected_sources),
                "generated_at": utc_now(),
                "sections": normalized,
                "citation_sources": [asdict(source) for source in selected_sources],
                "raw_model_response": response,
            }

            stage = "write"
            write_json_atomic(cache_path, cache_payload)
            write_text_atomic(summary_path, render_summary_markdown(cache_payload))
            self.mark_state(paper, cache_key, summary_path, cache_path, status="succeeded")
            logger.info("Summary generated: {}", summary_path)
            return SummaryResult(paper.paper_id, "succeeded", summary_path, cache_path)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.error("Summary failed at stage {} for {}: {}", stage, paper.paper_id, error)
            self.record_failure(paper, stage, exc)
            self.mark_state(paper, None, summary_path, None, status="failed", error=error)
            return SummaryResult(paper.paper_id, "failed", summary_path, None, error)

    def summary_path(self, paper_id: str) -> Path:
        return self.root / "03_Summary" / safe_path_name(paper_id) / "summary.md"

    def cache_path(self, paper_id: str, cache_key: str) -> Path:
        return self.cache_dir / safe_path_name(paper_id) / f"{cache_key}.summary.json"

    def cache_key(self, paper: PaperRecord, sources: list[SourceAnchor]) -> str:
        payload = {
            "paper_id": paper.paper_id,
            "model": self.options.model,
            "summary_engine_version": SUMMARY_ENGINE_VERSION,
            "prompt_version": PROMPT_VERSION,
            "target_min_tokens": self.options.target_min_tokens,
            "target_max_tokens": self.options.target_max_tokens,
            "source_hash": hash_sources(sources),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": SUMMARY_ENGINE_VERSION, "papers": {}}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.state_path.with_suffix(".corrupt.json")
            self.state_path.replace(backup)
            logger.warning("Summary state file was corrupt and moved to {}", backup)
            return {"version": SUMMARY_ENGINE_VERSION, "papers": {}}

    def mark_state(
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
                "summary_engine_version": SUMMARY_ENGINE_VERSION,
                "updated_at": utc_now(),
                "error": error,
            }
            self.state["version"] = SUMMARY_ENGINE_VERSION
            self.state["updated_at"] = utc_now()
            write_json_atomic(self.state_path, self.state)

    def record_failure(self, paper: PaperRecord, stage: str, error: Exception) -> None:
        payload = {
            "timestamp": utc_now(),
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


def build_source_anchors(paper: PaperRecord, root: Path) -> list[SourceAnchor]:
    sources: list[SourceAnchor] = []
    abstract = clean_scalar(paper.metadata.get("abstract"))
    if abstract:
        sources.append(
            SourceAnchor(
                source_id="",
                source_type="abstract",
                page=None,
                paragraph=0,
                section="Abstract",
                text=abstract,
            )
        )

    summary_path = find_existing_summary_path(root, paper)
    if summary_path:
        sources.extend(parse_markdown_sources(summary_path, source_type="summary"))

    body_sources: list[SourceAnchor] = []
    if paper.tei_path and paper.tei_path.exists():
        body_sources = parse_tei_sources(paper.tei_path)
    elif paper.metadata_json_path and paper.metadata_json_path.exists():
        body_sources = parse_metadata_json_sources(paper.metadata_json_path)

    if body_sources:
        sources.extend(body_sources)
    elif paper.raw_text_path and paper.raw_text_path.exists():
        sources.extend(parse_markdown_sources(paper.raw_text_path, source_type="raw_text"))

    for chunk_path in find_chunk_paths(root, paper):
        if chunk_path.suffix.lower() == ".json":
            sources.extend(parse_json_chunk_sources(chunk_path))
        else:
            sources.extend(parse_markdown_sources(chunk_path, source_type="chunks"))

    deduped = dedupe_sources(sources)
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


def parse_tei_sources(path: Path) -> list[SourceAnchor]:
    root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    body = first_descendant(root, "body")
    if body is None:
        return []

    sources: list[SourceAnchor] = []
    paragraph_counter = 0

    def walk(node: ET.Element, current_page: str | None, heading_stack: list[str]) -> str | None:
        nonlocal paragraph_counter
        name = local_name(node.tag)

        if name == "pb":
            return clean_scalar(node.attrib.get("n")) or current_page

        if name == "div":
            heading = clean_scalar(text_content(first_direct_child(node, "head")))
            next_stack = [*heading_stack, heading] if heading else heading_stack
            page = current_page
            for child in list(node):
                if local_name(child.tag) == "head":
                    continue
                page = walk(child, page, next_stack)
            return page

        if name == "p":
            text = clean_scalar(text_content(node))
            if text:
                paragraph_counter += 1
                sources.append(
                    SourceAnchor(
                        source_id="",
                        source_type="tei",
                        page=page_from_coords(node) or current_page,
                        paragraph=paragraph_counter,
                        section=" > ".join(heading_stack) if heading_stack else None,
                        text=text,
                    )
                )
            return current_page

        page = current_page
        for child in list(node):
            page = walk(child, page, heading_stack)
        return page

    walk(body, None, [])
    return sources


def parse_metadata_json_sources(path: Path) -> list[SourceAnchor]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources: list[SourceAnchor] = []
    paragraph_counter = 0
    for section in payload.get("sections", []):
        section_name = clean_scalar(section.get("heading"))
        paragraphs = section.get("paragraphs")
        if not isinstance(paragraphs, list):
            paragraphs = [section.get("text")]
        for paragraph in paragraphs:
            text = clean_scalar(paragraph)
            if not text:
                continue
            paragraph_counter += 1
            sources.append(
                SourceAnchor(
                    source_id="",
                    source_type="metadata_json",
                    page=None,
                    paragraph=paragraph_counter,
                    section=section_name,
                    text=text,
                )
            )
    return sources


def parse_markdown_sources(path: Path, source_type: str) -> list[SourceAnchor]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = [clean_scalar(part) for part in re.split(r"\n\s*\n+", text)]
    sources: list[SourceAnchor] = []
    paragraph_counter = 0
    current_section: str | None = None
    for part in parts:
        if not part:
            continue
        if part.startswith("#"):
            current_section = part.lstrip("#").strip()
            continue
        paragraph_counter += 1
        sources.append(
            SourceAnchor(
                source_id="",
                source_type=source_type,
                page=None,
                paragraph=paragraph_counter,
                section=current_section,
                text=part,
            )
        )
    return sources


def parse_json_chunk_sources(path: Path) -> list[SourceAnchor]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(payload, dict):
        chunks = payload.get("chunks")
        if isinstance(chunks, list):
            items = chunks
        else:
            items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        return []

    sources: list[SourceAnchor] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text = clean_scalar(item.get("text") or item.get("content"))
        if not text:
            continue
        sources.append(
            SourceAnchor(
                source_id="",
                source_type="chunks",
                page=clean_scalar(item.get("page") or item.get("page_number")),
                paragraph=normalize_int(item.get("paragraph") or item.get("paragraph_id")) or index,
                section=clean_scalar(item.get("section")),
                text=text,
            )
        )
    return sources


def select_sources(
    sources: list[SourceAnchor],
    max_input_chars: int,
    max_source_chars: int,
) -> list[SourceAnchor]:
    trimmed = [
        SourceAnchor(
            source_id=source.source_id,
            source_type=source.source_type,
            page=source.page,
            paragraph=source.paragraph,
            section=source.section,
            text=source.text[:max_source_chars],
        )
        for source in sources
        if source.text.strip()
    ]
    total_chars = sum(len(source.text) for source in trimmed)
    if total_chars <= max_input_chars:
        return trimmed

    scored = sorted(
        enumerate(trimmed),
        key=lambda item: (-source_selection_score(item[1]), item[0]),
    )
    selected_indexes: set[int] = set()
    running_chars = 0
    for index, source in scored:
        source_chars = len(source.text)
        if running_chars + source_chars > max_input_chars and selected_indexes:
            continue
        selected_indexes.add(index)
        running_chars += source_chars
        if running_chars >= max_input_chars:
            break

    return [source for index, source in enumerate(trimmed) if index in selected_indexes]


def source_selection_score(source: SourceAnchor) -> float:
    score = 1.0
    section = (source.section or "").lower()
    text = source.text[:500].lower()
    joined = f"{section} {text}"
    for keyword, value in [
        ("abstract", 8.0),
        ("result", 6.0),
        ("finding", 6.0),
        ("method", 5.0),
        ("discussion", 5.0),
        ("conclusion", 5.0),
        ("limitation", 4.0),
        ("future", 4.0),
        ("receptor", 3.0),
        ("binding", 3.0),
        ("resistance", 3.0),
    ]:
        if keyword in joined:
            score += value
    if source.paragraph is not None and source.paragraph <= 3:
        score += 2.0
    return score


def build_messages(
    paper: PaperRecord,
    sources: list[SourceAnchor],
    target_min_tokens: int,
    target_max_tokens: int,
) -> list[dict[str, str]]:
    system = (
        "You are Scientra Copilot Summary Engine. Compress a scientific paper into a faithful "
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
            "Each key must map to a list of objects:",
            '{"text": "one concise claim", "citations": ["S001", "S002"]}',
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
            *[format_source_block(source) for source in sources],
            "",
            "Return JSON only. Do not wrap it in markdown.",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def format_source_block(source: SourceAnchor) -> str:
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


def extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not choices:
        raise ValueError("DeepSeek response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        reasoning_content = message.get("reasoning_content")
        if reasoning_content and "{" in reasoning_content and "}" in reasoning_content:
            return str(reasoning_content)
    if not content:
        raise ValueError("DeepSeek response message has no content")
    return content


def parse_model_summary(content: str) -> dict[str, Any]:
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


def normalize_summary_payload(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {}
    for section in SECTION_ORDER:
        raw_value = find_section_value(payload, section)
        normalized[section] = normalize_section_items(raw_value)
    return normalized


def find_section_value(payload: dict[str, Any], section: str) -> Any:
    if section in payload:
        return payload[section]
    target = section.casefold()
    for key, value in payload.items():
        alias = SECTION_ALIASES.get(str(key).casefold())
        if alias == section or str(key).casefold() == target:
            return value
    return []


def normalize_section_items(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        return [{"text": value, "citations": []}]
    if isinstance(value, dict):
        return [
            {
                "text": clean_scalar(value.get("text") or value.get("claim") or value.get("summary")) or "",
                "citations": normalize_citations(value.get("citations") or value.get("sources")),
            }
        ]
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                items.append({"text": item, "citations": []})
            elif isinstance(item, dict):
                text = clean_scalar(item.get("text") or item.get("claim") or item.get("summary"))
                if text:
                    items.append(
                        {
                            "text": text,
                            "citations": normalize_citations(item.get("citations") or item.get("sources")),
                        }
                    )
        return items
    return []


def normalize_citations(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.findall(r"S\d{3}", value)
        return unique_preserve_order(values or [value])
    if isinstance(value, list):
        citations: list[str] = []
        for item in value:
            if isinstance(item, str):
                match = re.search(r"S\d{3}", item)
                citations.append(match.group(0) if match else item)
            elif isinstance(item, dict):
                source_id = item.get("source_id") or item.get("id")
                if source_id:
                    citations.append(str(source_id))
        return unique_preserve_order(citations)
    return []


def render_summary_markdown(payload: dict[str, Any]) -> str:
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
            text = clean_scalar(item.get("text")) or ""
            citations = item.get("citations", [])
            if not text or not citations:
                continue
            citation_text = format_citations(citations, sources_by_id)
            lines.append(f"- {text}{citation_text}")
            wrote_item = True
        if not wrote_item:
            lines.append("- No sourced statement generated.")
        lines.append("")

    lines.extend(["# Citation Anchors", ""])
    used_ids = collect_used_citation_ids(payload)
    if not used_ids:
        lines.append("- No source IDs were cited by the model output.")
    else:
        for source_id in used_ids:
            source = sources_by_id.get(source_id)
            if not source:
                lines.append(f"- {source_id}: unresolved source")
                continue
            source_section = compact_source_section(
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


def format_citations(citations: list[str], sources_by_id: dict[str, dict[str, Any]]) -> str:
    resolved: list[str] = []
    for source_id in citations:
        source = sources_by_id.get(source_id)
        if not source:
            resolved.append(source_id)
            continue
        page = source.get("page") or "unknown"
        paragraph = source.get("paragraph")
        paragraph_text = paragraph if paragraph is not None else "unknown"
        source_section = compact_source_section(
            source.get("section") or source.get("source_type") or "unknown"
        )
        resolved.append(
            f"{source_id} source_section={source_section} page={page} paragraph={paragraph_text}"
        )
    return f" ({'; '.join(resolved)})" if resolved else ""


def compact_source_section(value: Any, limit: int = 64) -> str:
    section = clean_scalar(value) or "unknown"
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


def collect_used_citation_ids(payload: dict[str, Any]) -> list[str]:
    citations: list[str] = []
    for section in payload.get("sections", {}).values():
        for item in section:
            citations.extend(item.get("citations", []))
    return unique_preserve_order(citations)


def default_options() -> SummaryOptions:
    return SummaryOptions(
        model=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
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
    )


def options_from_args(args: argparse.Namespace) -> SummaryOptions:
    return SummaryOptions(
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key or os.environ.get("DEEPSEEK_API_KEY"),
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
    )


def load_metadata_payload(
    metadata_yaml_path: Path | None,
    metadata_json_path: Path | None,
) -> dict[str, Any]:
    if metadata_yaml_path and metadata_yaml_path.exists():
        return yaml.safe_load(metadata_yaml_path.read_text(encoding="utf-8")) or {}
    if metadata_json_path and metadata_json_path.exists():
        return json.loads(metadata_json_path.read_text(encoding="utf-8"))
    return {}


def resolve_raw_text_path(
    root: Path,
    key: str,
    paper_id: str,
    explicit_path: Path | None,
    metadata: dict[str, Any],
) -> Path | None:
    candidates = [
        explicit_path,
        path_or_none(dig(metadata, "outputs", "raw_text_path")),
        root / "03_Summary" / "raw_text" / f"{key}.txt",
        root / "03_Summary" / "raw_text" / f"{paper_id}.txt",
    ]
    return first_existing_path(candidates)


def resolve_tei_path(
    root: Path,
    key: str,
    paper_id: str,
    explicit_path: Path | None,
    metadata: dict[str, Any],
) -> Path | None:
    candidates = [
        explicit_path,
        path_or_none(dig(metadata, "outputs", "tei_path")),
        root / "02_Metadata" / "tei" / f"{key}.tei.xml",
        root / "02_Metadata" / "tei" / f"{paper_id}.tei.xml",
    ]
    return first_existing_path(candidates)


def find_existing_summary_path(root: Path, paper: PaperRecord) -> Path | None:
    canonical_output = root / "03_Summary" / safe_path_name(paper.paper_id) / "summary.md"
    candidates = [
        root / "03_Summary" / safe_path_name(paper.key) / "summary.md",
        root / "03_Summary" / "summaries" / f"{paper.paper_id}.md",
        root / "03_Summary" / "summaries" / f"{paper.key}.md",
        root / "03_Summary" / f"{paper.paper_id}.summary.md",
        root / "03_Summary" / f"{paper.key}.summary.md",
    ]
    for path in candidates:
        if path.exists() and path.resolve() != canonical_output.resolve():
            return path
    return None


def find_chunk_paths(root: Path, paper: PaperRecord) -> list[Path]:
    candidates: list[Path] = []
    for identifier in [paper.paper_id, paper.key]:
        chunk_dir = root / "03_Summary" / "chunks" / safe_path_name(identifier)
        if chunk_dir.exists():
            candidates.extend(
                sorted(
                    path
                    for path in chunk_dir.iterdir()
                    if path.suffix.lower() in {".md", ".txt", ".json"}
                )
            )
        for suffix in [".md", ".txt", ".json"]:
            path = root / "03_Summary" / "chunks" / f"{identifier}{suffix}"
            if path.exists():
                candidates.append(path)
    return unique_paths(candidates)


def path_or_none(value: Any) -> Path | None:
    if not value:
        return None
    return Path(str(value))


def first_existing_path(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path and path.exists():
            return path
    return None


def dedupe_sources(sources: list[SourceAnchor]) -> list[SourceAnchor]:
    seen: set[str] = set()
    result: list[SourceAnchor] = []
    for source in sources:
        text_key = re.sub(r"\s+", " ", source.text).strip().casefold()
        if not text_key or text_key in seen:
            continue
        seen.add(text_key)
        result.append(source)
    return result


def hash_sources(sources: list[SourceAnchor]) -> str:
    digest = hashlib.sha256()
    for source in sources:
        digest.update(json.dumps(asdict(source), sort_keys=True, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def page_from_coords(node: ET.Element) -> str | None:
    for element in [node, *list(node.iter())]:
        coords = element.attrib.get("coords")
        if not coords:
            continue
        match = re.search(r"(?<!\d)(\d+)\s*,", coords)
        if match:
            return match.group(1)
    return None


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def descendants(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in node.iter() if local_name(child.tag) == name]


def first_descendant(node: ET.Element | None, name: str) -> ET.Element | None:
    matches = descendants(node, name)
    return matches[0] if matches else None


def direct_children(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in list(node) if local_name(child.tag) == name]


def first_direct_child(node: ET.Element | None, name: str) -> ET.Element | None:
    matches = direct_children(node, name)
    return matches[0] if matches else None


def text_content(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def dig(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def clean_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value.replace("\x00", "")).strip()
    return cleaned or None


def normalize_year(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = clean_scalar(value)
    if not text:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def normalize_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = clean_scalar(value)
    if not text:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe or "paper"


def unique_preserve_order(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


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


def should_retry_http(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_logging(root: Path) -> Path:
    log_dir = root / "07_Workflows" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"summary_engine_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    try:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(log_path, level="INFO", rotation="10 MB", retention=20, encoding="utf-8")
    except AttributeError:
        pass
    return log_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Scientra Copilot paper summaries with DeepSeek V4 Pro.",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--all", action="store_true", help="Summarize all discovered papers.")
    selector.add_argument("--paper-id", help="Summarize one paper_id or paper key.")

    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL))
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
    parser.add_argument("--force", action="store_true", help="Force a fresh DeepSeek request.")
    parser.add_argument("--regenerate", action="store_true", help="Alias for --force.")
    parser.add_argument("--cache-only", action="store_true", help="Use cache only; fail on cache miss.")
    parser.add_argument("--json", action="store_true", help="Print JSON run summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = args.root.resolve()
    log_path = configure_logging(root)
    options = options_from_args(args)
    engine = SummaryEngine(root=root, options=options)

    logger.info("Summary Engine started")
    logger.info("Log file: {}", log_path)
    logger.info("Model: {}", options.model)
    logger.info("Base URL: {}", options.base_url)
    logger.info("Cache only: {}", options.cache_only)
    logger.info("Force regenerate: {}", options.force)

    if args.paper_id:
        results = [engine.summarize_by_paper_id(args.paper_id)]
    else:
        results = engine.summarize_all()

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    payload = {
        "summary_engine_version": SUMMARY_ENGINE_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": options.model,
        "results": [
            {
                "paper_id": result.paper_id,
                "status": result.status,
                "summary_path": str(result.summary_path) if result.summary_path else None,
                "cache_path": str(result.cache_path) if result.cache_path else None,
                "error": result.error,
            }
            for result in results
        ],
        "counts": counts,
        "summary_regenerated": bool(options.force),
        "embedding_regenerated": False,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Scientra Copilot Summary Engine")
        print(f"summary_engine_version: {SUMMARY_ENGINE_VERSION}")
        print(f"model: {options.model}")
        print(f"results: {counts}")
        for result in results:
            print(f"{result.paper_id}: {result.status} -> {result.summary_path}")
        print("embedding_regenerated: false")

    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
