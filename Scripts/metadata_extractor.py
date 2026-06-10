from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal environments
    import logging

    class _LoggerCompat:
        def __init__(self) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
            self._logger = logging.getLogger("scientra.metadata_extractor")

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


ENGINE_VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAPERS_DIR = PROJECT_ROOT / "02_Metadata" / "papers"
DEFAULT_RAW_TEXT_DIR = PROJECT_ROOT / "03_Summary" / "raw_text"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "02_Metadata" / "yaml"
DEFAULT_AGGREGATE_PATH = PROJECT_ROOT / "02_Metadata" / "metadata.yaml"
DEFAULT_FAILURE_DIR = PROJECT_ROOT / "02_Metadata" / "failures"
DEFAULT_LOG_DIR = PROJECT_ROOT / "07_Workflows" / "logs"
DEFAULT_STATE_PATH = PROJECT_ROOT / "02_Metadata" / "metadata_extractor_state.json"


@dataclass(frozen=True)
class MetadataPaths:
    papers_dir: Path
    raw_text_dir: Path
    output_dir: Path
    aggregate_path: Path
    failure_dir: Path
    log_dir: Path
    state_path: Path

    @property
    def failure_path(self) -> Path:
        return self.failure_dir / "metadata_extractor_failures.jsonl"


@dataclass(frozen=True)
class MetadataOptions:
    workers: int
    force: bool
    limit: int | None
    offline: bool
    use_crossref: bool
    use_pubmed: bool
    timeout_seconds: int
    retries: int
    crossref_email: str | None
    pubmed_email: str | None
    pubmed_api_key: str | None


@dataclass(frozen=True)
class InputRecord:
    key: str
    metadata_path: Path | None
    raw_text_path: Path | None


@dataclass(frozen=True)
class ExtractResult:
    key: str
    status: str
    output_path: Path | None
    metadata: dict[str, Any] | None
    error: str | None = None


class HttpJsonClient:
    def __init__(
        self,
        timeout_seconds: int,
        retries: int,
        user_agent: str,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.user_agent = user_agent

    def get_text(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(
                url,
                method="GET",
                headers={
                    "Accept": "application/json,application/xml,text/xml,text/plain,*/*",
                    "User-Agent": self.user_agent,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"HTTP {exc.code}: {body[:300]}")
                if not should_retry_http(exc.code):
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc

            if attempt < self.retries:
                time.sleep(1.5 * (2**attempt))

        raise RuntimeError(f"HTTP request failed: {last_error}")

    def get_json(self, url: str) -> dict[str, Any]:
        return json.loads(self.get_text(url))


class CrossrefClient:
    def __init__(self, http: HttpJsonClient, email: str | None = None) -> None:
        self.http = http
        self.email = email

    def lookup(self, doi: str | None, title: str | None) -> dict[str, Any] | None:
        if doi:
            item = self.lookup_by_doi(doi)
            if item:
                return item
        if title:
            return self.lookup_by_title(title)
        return None

    def lookup_by_doi(self, doi: str) -> dict[str, Any] | None:
        encoded = urllib.parse.quote(doi, safe="")
        url = f"https://api.crossref.org/works/{encoded}"
        if self.email:
            url = f"{url}?mailto={urllib.parse.quote(self.email)}"
        try:
            payload = self.http.get_json(url)
        except Exception as exc:
            logger.warning("Crossref DOI lookup failed for {}: {}", doi, exc)
            return None
        message = payload.get("message")
        return normalize_crossref_message(message) if isinstance(message, dict) else None

    def lookup_by_title(self, title: str) -> dict[str, Any] | None:
        params = {"query.title": title, "rows": "1"}
        if self.email:
            params["mailto"] = self.email
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        try:
            payload = self.http.get_json(url)
        except Exception as exc:
            logger.warning("Crossref title lookup failed for {}: {}", title, exc)
            return None
        items = payload.get("message", {}).get("items", [])
        if not items:
            return None
        return normalize_crossref_message(items[0])


class PubMedClient:
    def __init__(
        self,
        http: HttpJsonClient,
        email: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.http = http
        self.email = email
        self.api_key = api_key

    def lookup(self, doi: str | None, title: str | None) -> dict[str, Any] | None:
        pmid = None
        if doi:
            pmid = self.search(f"{doi}[doi]")
        if not pmid and title:
            pmid = self.search(f'"{title}"[Title]')
        if not pmid:
            return None
        return self.fetch_article(pmid)

    def search(self, term: str) -> str | None:
        params = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": "1",
        }
        self._add_ncbi_params(params)
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
        try:
            payload = self.http.get_json(url)
        except Exception as exc:
            logger.warning("PubMed search failed for {}: {}", term, exc)
            return None
        ids = payload.get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None

    def fetch_article(self, pmid: str) -> dict[str, Any] | None:
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
        }
        self._add_ncbi_params(params)
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
        try:
            xml_text = self.http.get_text(url)
        except Exception as exc:
            logger.warning("PubMed fetch failed for {}: {}", pmid, exc)
            return None
        try:
            return normalize_pubmed_article(xml_text, pmid)
        except ET.ParseError as exc:
            logger.warning("PubMed XML parse failed for {}: {}", pmid, exc)
            return None

    def _add_ncbi_params(self, params: dict[str, str]) -> None:
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key


class MetadataExtractorEngine:
    def __init__(self, paths: MetadataPaths, options: MetadataOptions) -> None:
        self.paths = paths
        self.options = options
        self.state_lock = threading.Lock()
        self.failure_lock = threading.Lock()
        self.state = self._load_state()

        user_agent = "Scientra-Copilot-Metadata-Engine/0.1"
        if options.crossref_email:
            user_agent = f"{user_agent} (mailto:{options.crossref_email})"
        self.http = HttpJsonClient(
            timeout_seconds=options.timeout_seconds,
            retries=options.retries,
            user_agent=user_agent,
        )
        self.crossref = CrossrefClient(self.http, options.crossref_email)
        self.pubmed = PubMedClient(self.http, options.pubmed_email, options.pubmed_api_key)

    def ensure_directories(self) -> None:
        for path in [
            self.paths.papers_dir,
            self.paths.raw_text_dir,
            self.paths.output_dir,
            self.paths.failure_dir,
            self.paths.log_dir,
            self.paths.aggregate_path.parent,
            self.paths.state_path.parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def discover_inputs(self) -> list[InputRecord]:
        records: dict[str, dict[str, Path | None]] = {}
        if self.paths.papers_dir.exists():
            for path in sorted(self.paths.papers_dir.glob("*.metadata.json")):
                key = path.name[: -len(".metadata.json")]
                records.setdefault(key, {"metadata_path": None, "raw_text_path": None})
                records[key]["metadata_path"] = path

        if self.paths.raw_text_dir.exists():
            for path in sorted(self.paths.raw_text_dir.glob("*.txt")):
                key = path.stem
                records.setdefault(key, {"metadata_path": None, "raw_text_path": None})
                records[key]["raw_text_path"] = path

        items = [
            InputRecord(
                key=key,
                metadata_path=paths["metadata_path"],
                raw_text_path=paths["raw_text_path"],
            )
            for key, paths in sorted(records.items())
        ]
        if self.options.limit is not None:
            items = items[: self.options.limit]
        return items

    def process_batch(self) -> list[ExtractResult]:
        self.ensure_directories()
        records = self.discover_inputs()
        logger.info("Found {} metadata input records", len(records))
        if not records:
            self._write_aggregate([])
            return []

        workers = max(1, self.options.workers)
        if workers == 1:
            results = [self.process_one(record) for record in records]
        else:
            results = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(self.process_one, record) for record in records]
                for future in as_completed(futures):
                    results.append(future.result())

        successful_metadata = [
            result.metadata
            for result in results
            if result.metadata is not None and result.status in {"succeeded", "skipped"}
        ]
        self._write_aggregate(successful_metadata)
        return results

    def process_one(self, record: InputRecord) -> ExtractResult:
        stage = "start"
        try:
            output_path = self.paths.output_dir / f"{record.key}.metadata.yaml"
            fingerprint = self._input_fingerprint(record)

            if self._can_skip(record.key, fingerprint, output_path):
                metadata = self.state.get("files", {}).get(record.key, {}).get("metadata")
                if isinstance(metadata, dict):
                    logger.info("Skipping completed metadata: {}", record.key)
                    return ExtractResult(record.key, "skipped", output_path, metadata)

            logger.info("Extracting metadata: {}", record.key)
            stage = "read_inputs"
            grobid_payload = read_json(record.metadata_path) if record.metadata_path else {}
            raw_text = read_text(record.raw_text_path) if record.raw_text_path else ""

            stage = "rules"
            rule_payload = extract_by_rules(grobid_payload, raw_text)
            base_doi = choose_best_doi(
                [
                    dig(grobid_payload, "metadata", "doi"),
                    rule_payload.get("doi"),
                ]
            )
            base_title = first_present(
                dig(grobid_payload, "metadata", "title"),
                rule_payload.get("title"),
            )

            crossref_payload = None
            pubmed_payload = None
            sources_used = ["grobid_metadata" if grobid_payload else None, "rules"]

            if not self.options.offline and self.options.use_crossref:
                stage = "crossref"
                crossref_payload = self.crossref.lookup(base_doi, base_title)
                if crossref_payload:
                    sources_used.append("crossref")

            if not self.options.offline and self.options.use_pubmed:
                stage = "pubmed"
                pubmed_payload = self.pubmed.lookup(base_doi, base_title)
                if pubmed_payload:
                    sources_used.append("pubmed")

            stage = "merge"
            metadata = merge_metadata(
                key=record.key,
                grobid_payload=grobid_payload,
                raw_text=raw_text,
                rule_payload=rule_payload,
                crossref_payload=crossref_payload,
                pubmed_payload=pubmed_payload,
                sources_used=[source for source in sources_used if source],
            )

            stage = "write_yaml"
            write_yaml_atomic(output_path, metadata)

            self._mark_state(
                key=record.key,
                status="succeeded",
                fingerprint=fingerprint,
                output_path=output_path,
                metadata=metadata,
                error=None,
            )
            logger.info("Succeeded: {}", record.key)
            return ExtractResult(record.key, "succeeded", output_path, metadata)
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            logger.error("Failed at stage {} for {}: {}", stage, record.key, error_message)
            self._record_failure(record, stage, exc)
            self._mark_state(
                key=record.key,
                status="failed",
                fingerprint=None,
                output_path=None,
                metadata=None,
                error=error_message,
            )
            return ExtractResult(record.key, "failed", None, None, error_message)

    def _input_fingerprint(self, record: InputRecord) -> str:
        digest = hashlib.sha256()
        digest.update(ENGINE_VERSION.encode("utf-8"))
        for path in [record.metadata_path, record.raw_text_path]:
            if path and path.exists():
                digest.update(str(path).encode("utf-8"))
                digest.update(file_sha256(path).encode("utf-8"))
        return digest.hexdigest()

    def _can_skip(self, key: str, fingerprint: str, output_path: Path) -> bool:
        if self.options.force:
            return False
        entry = self.state.get("files", {}).get(key)
        return bool(
            entry
            and entry.get("status") == "succeeded"
            and entry.get("fingerprint") == fingerprint
            and output_path.exists()
            and isinstance(entry.get("metadata"), dict)
        )

    def _load_state(self) -> dict[str, Any]:
        if not self.paths.state_path.exists():
            return {"version": ENGINE_VERSION, "files": {}}
        try:
            return json.loads(self.paths.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.paths.state_path.with_suffix(".corrupt.json")
            self.paths.state_path.replace(backup)
            logger.warning("State file was corrupt and moved to {}", backup)
            return {"version": ENGINE_VERSION, "files": {}}

    def _mark_state(
        self,
        key: str,
        status: str,
        fingerprint: str | None,
        output_path: Path | None,
        metadata: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        entry = {
            "status": status,
            "fingerprint": fingerprint,
            "output_path": str(output_path) if output_path else None,
            "updated_at": utc_now(),
            "error": error,
            "metadata": metadata,
        }
        with self.state_lock:
            self.state.setdefault("files", {})[key] = entry
            self.state["version"] = ENGINE_VERSION
            self.state["updated_at"] = utc_now()
            write_json_atomic(self.paths.state_path, self.state)

    def _record_failure(self, record: InputRecord, stage: str, error: Exception) -> None:
        payload = {
            "timestamp": utc_now(),
            "key": record.key,
            "metadata_path": str(record.metadata_path) if record.metadata_path else None,
            "raw_text_path": str(record.raw_text_path) if record.raw_text_path else None,
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
        with self.failure_lock:
            self.paths.failure_dir.mkdir(parents=True, exist_ok=True)
            with self.paths.failure_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _write_aggregate(self, metadata_items: list[dict[str, Any]]) -> None:
        payload = {
            "generated_at": utc_now(),
            "engine": {
                "name": "Scientra Copilot Metadata Engine",
                "version": ENGINE_VERSION,
                "uses_llm": False,
            },
            "count": len(metadata_items),
            "papers": sorted(metadata_items, key=lambda item: item.get("key") or item.get("paper_id") or ""),
        }
        write_yaml_atomic(self.paths.aggregate_path, payload)
        logger.info("Wrote aggregate metadata: {}", self.paths.aggregate_path)


def merge_metadata(
    key: str,
    grobid_payload: dict[str, Any],
    raw_text: str,
    rule_payload: dict[str, Any],
    crossref_payload: dict[str, Any] | None,
    pubmed_payload: dict[str, Any] | None,
    sources_used: list[str],
) -> dict[str, Any]:
    grobid_metadata = grobid_payload.get("metadata", {}) if isinstance(grobid_payload, dict) else {}
    parser_method = dig(grobid_payload, "parser", "method")
    parser_sources = grobid_payload.get("metadata_sources", {}) if isinstance(grobid_payload, dict) else {}
    field_sources: dict[str, str | None] = {}

    def choose(field: str, candidates: list[tuple[str, Any]]) -> Any:
        for source, value in candidates:
            normalized = normalize_field_value(field, value)
            if has_value(normalized):
                field_sources[field] = source
                return normalized
        field_sources[field] = None
        return [] if field in {"authors", "species", "toxin", "mechanism", "method"} else None

    def parser_source(field: str, fallback: str) -> str:
        source = clean_scalar(parser_sources.get(field))
        if source:
            return source
        if parser_method == "grobid":
            return "grobid_header"
        return fallback

    doi_candidates = [
        (parser_source("doi", "regex"), dig(grobid_payload, "metadata", "doi")),
        ("regex", rule_payload.get("doi")),
        ("crossref", dig(crossref_payload, "doi")),
        ("pubmed", dig(pubmed_payload, "doi")),
    ]

    title = choose(
        "title",
        [
            (parser_source("title", "first_page"), grobid_metadata.get("title")),
            ("first_page", rule_payload.get("title")),
            ("crossref", dig(crossref_payload, "title")),
            ("pubmed", dig(pubmed_payload, "title")),
            ("filename", filename_title(key)),
        ],
    )
    journal = choose(
        "journal",
        [
            (parser_source("journal", "pdf_meta"), grobid_metadata.get("journal")),
            ("crossref", dig(crossref_payload, "journal")),
            ("pubmed", dig(pubmed_payload, "journal")),
            ("first_page", rule_payload.get("journal")),
        ],
    )
    year = choose(
        "year",
        [
            (parser_source("year", "first_page_regex"), grobid_metadata.get("year")),
            ("first_page_regex", rule_payload.get("year")),
            ("crossref", dig(crossref_payload, "year")),
            ("pubmed", dig(pubmed_payload, "year")),
        ],
    )
    doi_source, doi = choose_best_doi_pair(doi_candidates)
    field_sources["doi"] = doi_source
    authors = choose(
        "authors",
        [
            (parser_source("authors", "pdf_meta"), grobid_metadata.get("authors")),
            ("crossref", dig(crossref_payload, "authors")),
            ("pubmed", dig(pubmed_payload, "authors")),
            ("first_page", rule_payload.get("authors")),
        ],
    )
    abstract = choose(
        "abstract",
        [
            (parser_source("abstract", "first_page"), grobid_payload.get("abstract")),
            ("first_page", rule_payload.get("abstract")),
            ("pubmed", dig(pubmed_payload, "abstract")),
            ("crossref", dig(crossref_payload, "abstract")),
        ],
    )
    abstract_source = field_sources.get("abstract")
    if abstract_source == "grobid" and grobid_payload.get("abstract_source"):
        abstract_source = grobid_payload.get("abstract_source")

    evidence_text = "\n\n".join(
        text
        for text in [
            title or "",
            abstract or "",
            raw_text or "",
        ]
        if text
    )
    extensions = extract_extension_fields(evidence_text)

    paper_id = grobid_payload.get("paper_id") or f"paper_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}"
    title_hash = normalized_title_hash(title)
    quality = metadata_quality(
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        doi=doi,
        abstract=abstract,
        normalized_hash=title_hash,
    )
    return {
        "key": key,
        "paper_id": paper_id,
        "title": title,
        "title_source": field_sources.get("title"),
        "journal": journal,
        "journal_source": field_sources.get("journal"),
        "year": year,
        "year_source": field_sources.get("year"),
        "doi": doi,
        "doi_source": field_sources.get("doi"),
        "authors": authors,
        "authors_source": field_sources.get("authors"),
        "abstract": abstract,
        "abstract_source": abstract_source,
        "abstract_candidate": grobid_payload.get("abstract_candidate"),
        "tei_abstract": grobid_payload.get("tei_abstract"),
        "normalized_title_hash": title_hash,
        "metadata_quality": quality,
        "species": extensions["species"],
        "toxin": extensions["toxin"],
        "mechanism": extensions["mechanism"],
        "method": extensions["method"],
        "extraction": {
            "engine": "Scientra Copilot Metadata Engine",
            "version": ENGINE_VERSION,
            "uses_llm": False,
            "priority_order": [
                "grobid_header",
                "pdf_meta",
                "first_page",
                "regex",
                "crossref",
                "pubmed",
                "filename",
            ],
            "sources_used": unique_preserve_order(sources_used),
            "field_sources": field_sources,
            "extracted_at": utc_now(),
        },
    }


def normalize_crossref_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": first_list_value(message.get("title")),
        "journal": first_list_value(message.get("container-title")),
        "year": crossref_year(message),
        "doi": normalize_doi(message.get("DOI")),
        "authors": normalize_crossref_authors(message.get("author")),
        "abstract": clean_markup(message.get("abstract")),
    }


def crossref_year(message: dict[str, Any]) -> int | None:
    for key in ["published-print", "published-online", "published", "issued", "created"]:
        value = message.get(key)
        date_parts = value.get("date-parts") if isinstance(value, dict) else None
        if date_parts and date_parts[0]:
            try:
                return int(date_parts[0][0])
            except (TypeError, ValueError):
                continue
    return None


def normalize_crossref_authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for author in value:
        if not isinstance(author, dict):
            continue
        name = " ".join(
            part
            for part in [
                clean_scalar(author.get("given")),
                clean_scalar(author.get("family")),
            ]
            if part
        )
        if name:
            authors.append(name)
    return unique_preserve_order(authors)


def normalize_pubmed_article(xml_text: str, pmid: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    article = first_descendant(root, "Article")
    medline = first_descendant(root, "MedlineCitation")
    journal_node = first_descendant(article, "Journal") if article is not None else None
    article_id_list = first_descendant(root, "ArticleIdList")

    doi = None
    if article_id_list is not None:
        for node in descendants(article_id_list, "ArticleId"):
            if node.attrib.get("IdType", "").lower() == "doi":
                doi = normalize_doi(text_content(node))
                break

    return {
        "pmid": pmid,
        "title": clean_scalar(text_content(first_descendant(article, "ArticleTitle"))),
        "journal": clean_scalar(text_content(first_descendant(journal_node, "Title"))),
        "year": pubmed_year(article),
        "doi": doi,
        "authors": pubmed_authors(article),
        "abstract": pubmed_abstract(article),
        "mesh_terms": pubmed_mesh_terms(medline),
    }


def pubmed_year(article: ET.Element | None) -> int | None:
    for name in ["ArticleDate", "PubDate"]:
        for node in descendants(article, name):
            year_node = first_descendant(node, "Year")
            if year_node is not None:
                value = clean_scalar(text_content(year_node))
                if value and value.isdigit():
                    return int(value)
    return None


def pubmed_authors(article: ET.Element | None) -> list[str]:
    authors: list[str] = []
    author_list = first_descendant(article, "AuthorList")
    for author in direct_children(author_list, "Author"):
        last_name = clean_scalar(text_content(first_descendant(author, "LastName")))
        fore_name = clean_scalar(text_content(first_descendant(author, "ForeName")))
        collective = clean_scalar(text_content(first_descendant(author, "CollectiveName")))
        if collective:
            authors.append(collective)
        else:
            name = " ".join(part for part in [fore_name, last_name] if part)
            if name:
                authors.append(name)
    return unique_preserve_order(authors)


def pubmed_abstract(article: ET.Element | None) -> str | None:
    abstract_node = first_descendant(article, "Abstract")
    if abstract_node is None:
        return None
    parts: list[str] = []
    for node in descendants(abstract_node, "AbstractText"):
        label = clean_scalar(node.attrib.get("Label"))
        text = clean_scalar(text_content(node))
        if text and label:
            parts.append(f"{label}: {text}")
        elif text:
            parts.append(text)
    return "\n\n".join(parts) if parts else None


def pubmed_mesh_terms(medline: ET.Element | None) -> list[str]:
    terms: list[str] = []
    heading_list = first_descendant(medline, "MeshHeadingList")
    for descriptor in descendants(heading_list, "DescriptorName"):
        value = clean_scalar(text_content(descriptor))
        if value:
            terms.append(value)
    return unique_preserve_order(terms)


def extract_by_rules(grobid_payload: dict[str, Any], raw_text: str) -> dict[str, Any]:
    metadata = grobid_payload.get("metadata", {}) if isinstance(grobid_payload, dict) else {}
    return {
        "title": first_present(metadata.get("title"), rule_title(raw_text)),
        "journal": rule_journal(raw_text),
        "year": first_present(metadata.get("year"), rule_year(raw_text)),
        "doi": choose_best_doi([metadata.get("doi"), rule_doi(raw_text)]),
        "authors": first_present(normalize_authors(metadata.get("authors")), rule_authors(raw_text)),
        "abstract": first_present(grobid_payload.get("abstract"), rule_abstract(raw_text)),
    }


def extract_extension_fields(text: str) -> dict[str, list[str]]:
    return {
        "species": extract_species(text),
        "toxin": extract_keyword_hits(text, TOXIN_PATTERNS),
        "mechanism": extract_keyword_hits(text, MECHANISM_PATTERNS),
        "method": extract_keyword_hits(text, METHOD_PATTERNS),
    }


SPECIES_PATTERNS: list[tuple[str, str]] = [
    ("Homo sapiens / human", r"\b(human|humans|Homo sapiens)\b"),
    ("Mus musculus / mouse", r"\b(mouse|mice|Mus musculus)\b"),
    ("Rattus norvegicus / rat", r"\b(rat|rats|Rattus norvegicus)\b"),
    ("Danio rerio / zebrafish", r"\b(zebrafish|Danio rerio)\b"),
    ("Drosophila melanogaster", r"\b(Drosophila melanogaster|fruit fly|fruit flies)\b"),
    ("Caenorhabditis elegans", r"\b(Caenorhabditis elegans|C\. elegans)\b"),
    ("Escherichia coli", r"\b(Escherichia coli|E\. coli)\b"),
    ("Saccharomyces cerevisiae", r"\b(Saccharomyces cerevisiae|S\. cerevisiae)\b"),
    ("Arabidopsis thaliana", r"\b(Arabidopsis thaliana|A\. thaliana)\b"),
    ("cell line", r"\b(cell line|cell lines|HEK293|HeLa|A549|SH-SY5Y|RAW264\.7)\b"),
]

TOXIN_PATTERNS: list[tuple[str, str]] = [
    ("toxin", r"\btoxin(s)?\b"),
    ("venom", r"\bvenom(s)?\b"),
    ("botulinum toxin", r"\bbotulinum toxin\b"),
    ("tetanus toxin", r"\btetanus toxin\b"),
    ("cholera toxin", r"\bcholera toxin\b"),
    ("Shiga toxin", r"\bShiga toxin\b"),
    ("ricin", r"\bricin\b"),
    ("aflatoxin", r"\baflatoxin(s)?\b"),
    ("tetrodotoxin", r"\btetrodotoxin\b"),
    ("saxitoxin", r"\bsaxitoxin\b"),
    ("microcystin", r"\bmicrocystin(s)?\b"),
    ("mycotoxin", r"\bmycotoxin(s)?\b"),
    ("neurotoxin", r"\bneurotoxin(s)?\b"),
    ("endotoxin", r"\bendotoxin(s)?\b"),
    ("exotoxin", r"\bexotoxin(s)?\b"),
]

MECHANISM_PATTERNS: list[tuple[str, str]] = [
    ("apoptosis", r"\bapoptosis|apoptotic\b"),
    ("oxidative stress", r"\boxidative stress|ROS|reactive oxygen species\b"),
    ("inflammation", r"\binflammation|inflammatory|NF-kB\b"),
    ("mitochondrial dysfunction", r"\bmitochondrial dysfunction|mitochondria\b"),
    ("ion channel modulation", r"\bion channel|sodium channel|calcium channel|potassium channel\b"),
    ("receptor binding", r"\breceptor binding|binds? to receptor|binding affinity\b"),
    ("enzyme inhibition", r"\benzyme inhibition|inhibits?|inhibitor\b"),
    ("gene regulation", r"\bgene expression|transcriptional|upregulat|downregulat\b"),
    ("cell death", r"\bcell death|necrosis|cytotoxicity\b"),
    ("signal pathway", r"\bpathway|signaling|MAPK|PI3K|AKT|JAK|STAT\b"),
]

METHOD_PATTERNS: list[tuple[str, str]] = [
    ("GROBID", r"\bGROBID\b"),
    ("LC-MS", r"\bLC[- ]?MS|LC[- ]?MS/MS\b"),
    ("HPLC", r"\bHPLC\b"),
    ("ELISA", r"\bELISA\b"),
    ("Western blot", r"\bWestern blot\b"),
    ("qPCR", r"\bqPCR|RT-qPCR|real-time PCR\b"),
    ("RNA-seq", r"\bRNA[- ]seq|transcriptomics?\b"),
    ("CRISPR", r"\bCRISPR\b"),
    ("microscopy", r"\bmicroscopy|confocal|electron microscopy\b"),
    ("flow cytometry", r"\bflow cytometry|FACS\b"),
    ("cell assay", r"\bcell viability|MTT assay|assay\b"),
    ("animal model", r"\banimal model|in vivo\b"),
    ("in vitro", r"\bin vitro\b"),
    ("bioinformatics", r"\bbioinformatics|computational analysis\b"),
    ("molecular docking", r"\bmolecular docking|docking\b"),
]


def extract_species(text: str) -> list[str]:
    hits = extract_keyword_hits(text, SPECIES_PATTERNS)
    binomials = re.findall(r"\b([A-Z][a-z]+ [a-z]{2,})\b", text)
    ignored = {"New York", "United States", "Reactive Oxygen", "Western Blot"}
    for name in binomials:
        if name not in ignored and name not in hits:
            hits.append(name)
    return hits[:20]


def extract_keyword_hits(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    hits: list[str] = []
    for label, pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(label)
    return unique_preserve_order(hits)


def rule_title(raw_text: str) -> str | None:
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return clean_scalar(line[2:])
    return None


def rule_journal(raw_text: str) -> str | None:
    match = re.search(r"(?im)^\s*(journal|published in)\s*:\s*(.+?)\s*$", raw_text)
    return clean_scalar(match.group(2)) if match else None


def rule_year(raw_text: str) -> int | None:
    match = re.search(r"(?im)^\s*year\s*:\s*((?:19|20)\d{2})\s*$", raw_text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(19|20)\d{2}\b", raw_text[:3000])
    return int(match.group(0)) if match else None


def rule_doi(raw_text: str) -> str | None:
    return choose_best_doi(extract_doi_candidates(raw_text[:8000]))


def rule_authors(raw_text: str) -> list[str]:
    match = re.search(r"(?im)^\s*authors\s*:\s*(.+?)\s*$", raw_text)
    if not match:
        return []
    value = match.group(1)
    candidates = re.split(r"\s*;\s*|\s*,\s*(?=[A-Z][A-Za-z' -]+(?:$|,))", value)
    return unique_preserve_order([clean_scalar(candidate) for candidate in candidates if clean_scalar(candidate)])


def rule_abstract(raw_text: str) -> str | None:
    match = re.search(r"(?is)^##\s+Abstract\s*\n(.+?)(?=\n##\s+|\Z)", raw_text)
    return clean_scalar(match.group(1)) if match else None


def filename_title(key: str) -> str | None:
    stem = re.sub(r"_[a-f0-9]{12,16}$", "", Path(key).stem, flags=re.IGNORECASE)
    title = clean_scalar(stem.replace("_", " ").replace("-", " "))
    if not title or len(title) < 8:
        return None
    return title


def normalized_title_hash(title: Any) -> str | None:
    text = clean_scalar(title)
    if not text:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def metadata_quality(
    title: Any,
    authors: Any,
    journal: Any,
    year: Any,
    doi: Any,
    abstract: Any,
    normalized_hash: str | None,
) -> dict[str, Any]:
    minimal_required = ["title", "doi or normalized_title_hash", "year"]
    strict_required = ["title", "authors", "journal", "year", "doi", "abstract"]
    minimal_missing: list[str] = []
    if not has_value(title):
        minimal_missing.append("title")
    if not has_value(doi) and not normalized_hash:
        minimal_missing.append("doi or normalized_title_hash")
    if not has_value(year):
        minimal_missing.append("year")

    strict_values = {
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": year,
        "doi": doi,
        "abstract": abstract,
    }
    strict_missing = [field for field, value in strict_values.items() if not has_value(value)]
    return {
        "minimal_metadata_required": minimal_required,
        "strict_metadata_required": strict_required,
        "minimal_missing_fields": minimal_missing,
        "strict_missing_fields": strict_missing,
        "minimal_metadata_complete": not minimal_missing,
        "strict_metadata_complete": not strict_missing,
    }


def normalize_field_value(field: str, value: Any) -> Any:
    if field == "doi":
        return normalize_doi(value)
    if field == "year":
        return normalize_year(value)
    if field == "authors":
        return normalize_authors(value)
    if field in {"species", "toxin", "mechanism", "method"}:
        return normalize_string_list(value)
    return clean_scalar(value)


def normalize_doi(value: Any) -> str | None:
    text = clean_scalar(value)
    if not text:
        return None
    text = repair_ocr_doi_text(text)
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.IGNORECASE)
    if not match:
        return None
    doi = match.group(0).strip().rstrip(".,;:)])")
    return doi.lower()


def extract_doi_candidates(text: str) -> list[str]:
    repaired = repair_ocr_doi_text(text)
    return [
        normalize_doi(match.group(0))
        for match in re.finditer(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", repaired, flags=re.IGNORECASE)
        if normalize_doi(match.group(0))
    ]


def repair_ocr_doi_text(text: str) -> str:
    return re.sub(r"(?<=[./_-])\s+(?=[A-Za-z0-9])", "", text)


def choose_best_doi(values: list[Any]) -> str | None:
    return choose_best_doi_pair([("doi", value) for value in values])[1]


def choose_best_doi_pair(candidates: list[tuple[str, Any]]) -> tuple[str | None, str | None]:
    normalized: list[tuple[str, str]] = []
    for source, value in candidates:
        doi = normalize_doi(value)
        if doi:
            normalized.append((source, doi))
    if not normalized:
        return None, None
    source, doi = max(normalized, key=lambda item: doi_quality_score(item[1]))
    return source, doi


def doi_quality_score(doi: str) -> tuple[int, int, int]:
    suffix_penalty = -1 if re.search(r"\.(?:g|t|s)\d{3,}$", doi) else 0
    short_penalty = -1 if len(doi.split("/", 1)[-1]) < 8 else 0
    return (suffix_penalty, short_penalty, len(doi))


def normalize_year(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = clean_scalar(value)
    if not text:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def normalize_authors(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return normalize_string_list(re.split(r"\s*;\s*|\n+", value))
    if isinstance(value, list):
        authors: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                if not name:
                    name = " ".join(
                        part
                        for part in [
                            clean_scalar(item.get("given")),
                            clean_scalar(item.get("family")),
                            clean_scalar(item.get("surname")),
                        ]
                        if part
                    )
                if name:
                    authors.append(clean_scalar(name))
            else:
                cleaned = clean_scalar(item)
                if cleaned:
                    authors.append(cleaned)
        return unique_preserve_order(authors)
    return []


def normalize_string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        items = [str(value)]
    return unique_preserve_order([clean_scalar(item) for item in items if clean_scalar(item)])


def clean_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return None
    value = html.unescape(value)
    value = value.replace("\x00", "")
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def clean_markup(value: Any) -> str | None:
    text = clean_scalar(value)
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return clean_scalar(text)


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def first_present(*values: Any) -> Any:
    for value in values:
        if has_value(value):
            return value
    return None


def first_list_value(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return clean_scalar(value[0])
    return clean_scalar(value)


def dig(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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


def text_content(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def should_retry_http(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def write_yaml_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(dump_yaml(payload), encoding="utf-8")
    temp_path.replace(path)


def dump_yaml(payload: Any) -> str:
    try:
        import yaml

        return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120)
    except Exception:
        return minimal_yaml_dump(payload)


def minimal_yaml_dump(value: Any, indent: int = 0) -> str:
    spaces = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(minimal_yaml_dump(item, indent + 2).rstrip())
            else:
                lines.append(f"{spaces}{key}: {yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        if not value:
            return f"{spaces}[]\n"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}-")
                lines.append(minimal_yaml_dump(item, indent + 2).rstrip())
            else:
                lines.append(f"{spaces}- {yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    return f"{spaces}{yaml_scalar(value)}\n"


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if re.search(r"[:#\-\n\r\t]|^\s|\s$", text):
        return json.dumps(text, ensure_ascii=False)
    return text


def unique_preserve_order(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        if value is None:
            continue
        key = str(value).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"metadata_extractor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    try:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(log_path, level="INFO", rotation="10 MB", retention=20, encoding="utf-8")
    except AttributeError:
        pass
    return log_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Scientra Copilot metadata.yaml files. No LLM is used.",
    )
    parser.add_argument("--papers-dir", type=Path, default=DEFAULT_PAPERS_DIR)
    parser.add_argument("--raw-text-dir", type=Path, default=DEFAULT_RAW_TEXT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--aggregate-path", type=Path, default=DEFAULT_AGGREGATE_PATH)
    parser.add_argument("--failure-dir", type=Path, default=DEFAULT_FAILURE_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Skip Crossref and PubMed.")
    parser.add_argument("--no-crossref", action="store_true")
    parser.add_argument("--no-pubmed", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--crossref-email", default=None)
    parser.add_argument("--pubmed-email", default=None)
    parser.add_argument("--pubmed-api-key", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    paths = MetadataPaths(
        papers_dir=args.papers_dir.resolve(),
        raw_text_dir=args.raw_text_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        aggregate_path=args.aggregate_path.resolve(),
        failure_dir=args.failure_dir.resolve(),
        log_dir=args.log_dir.resolve(),
        state_path=args.state_path.resolve(),
    )
    log_path = configure_logging(paths.log_dir)
    options = MetadataOptions(
        workers=args.workers,
        force=args.force,
        limit=args.limit,
        offline=args.offline,
        use_crossref=not args.no_crossref,
        use_pubmed=not args.no_pubmed,
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
        crossref_email=args.crossref_email,
        pubmed_email=args.pubmed_email,
        pubmed_api_key=args.pubmed_api_key,
    )

    logger.info("Metadata Engine started")
    logger.info("Log file: {}", log_path)
    logger.info("Papers metadata directory: {}", paths.papers_dir)
    logger.info("Raw text directory: {}", paths.raw_text_dir)
    logger.info("Output directory: {}", paths.output_dir)
    logger.info("Aggregate metadata path: {}", paths.aggregate_path)
    if options.offline:
        logger.info("Offline mode enabled: Crossref and PubMed are skipped")

    engine = MetadataExtractorEngine(paths, options)
    results = engine.process_batch()

    counts = {"succeeded": 0, "skipped": 0, "failed": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    logger.info(
        "Metadata Engine finished: succeeded={}, skipped={}, failed={}",
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
