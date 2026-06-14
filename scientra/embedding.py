from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal environments
    import logging

    class _LoggerCompat:
        def __init__(self) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
            self._logger = logging.getLogger("scientra.embedding_engine")

        def remove(self) -> None:
            return None

        def add(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def info(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.info(format_log(message, *args, **kwargs))

        def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.warning(format_log(message, *args, **kwargs))

        def error(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.error(format_log(message, *args, **kwargs))

    def format_log(message: str, *args: Any, **kwargs: Any) -> str:
        try:
            return message.format(*args, **kwargs)
        except Exception:
            return message

    logger = _LoggerCompat()


try:
    from scientra.vector_store import DEFAULT_LANCEDB_DIR, DEFAULT_TABLE_NAME, LanceVectorStore
except ModuleNotFoundError:
    from scientra.vector_store import DEFAULT_LANCEDB_DIR, DEFAULT_TABLE_NAME, LanceVectorStore


EMBEDDING_ENGINE_VERSION = "0.2.0"
DEFAULT_MODEL_NAME = "BAAI/bge-m3"
def _detect_project_root() -> Path:
    """Walk up from this file until a 'Config/workflow_config.yaml' is found."""
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
DEFAULT_EMBEDDING_CONFIG_PATH = PROJECT_ROOT / "Config" / "embedding.yaml"
DEFAULT_DRY_RUN_REPORT_PATH = PROJECT_ROOT / "05_Index" / "embedding_dry_run_report.md"
DEFAULT_REAL_RUN_REPORT_PATH = PROJECT_ROOT / "05_Index" / "embedding_report.md"
DEFAULT_EMBEDDING_STATUS_PATH = PROJECT_ROOT / "04_VectorDB" / "embedding_status.sqlite"
LEVEL_METADATA = "metadata"
LEVEL_SUMMARY = "summary"
LEVEL_CHUNK = "chunk"
SUPPORTED_LEVELS = [LEVEL_METADATA, LEVEL_SUMMARY, LEVEL_CHUNK]


@dataclass(frozen=True)
class PaperDocument:
    key: str
    paper_id: str
    title: str | None
    doi: str | None
    year: int | None
    authors: list[str]
    abstract: str | None
    tags: list[str]
    metadata: dict[str, Any]
    metadata_path: Path | None
    summary_path: Path | None
    raw_text_path: Path | None
    chunk_paths: list[Path]


@dataclass(frozen=True)
class EmbeddingRecord:
    record_id: str
    paper_id: str
    level: str
    source_id: str
    title: str | None
    doi: str | None
    year: int | None
    tags: list[str]
    text: str
    text_hash: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class EmbeddingOptions:
    root: Path
    model_name: str
    db_dir: Path
    table_name: str
    batch_size: int
    device: str | None
    normalize_embeddings: bool
    force: bool
    dry_run: bool
    levels: list[str]
    limit: int | None


class BgeM3Embedder:
    """Lazy BGE-M3 embedder.

    The module remains importable without model dependencies. Actual embedding
    requires either sentence-transformers or FlagEmbedding to be installed.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        self.model_name = model_name
        self.device = None if device in {None, "", "auto"} else device
        self.normalize_embeddings = normalize_embeddings
        self._model: Any | None = None
        self._backend: str | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
        try:
            from sentence_transformers import SentenceTransformer

            kwargs: dict[str, Any] = {}
            if self.device:
                kwargs["device"] = self.device
            self._model = SentenceTransformer(self.model_name, **kwargs)
            self._backend = "sentence_transformers"
            return
        except Exception as sentence_transformers_error:
            try:
                from FlagEmbedding import BGEM3FlagModel

                kwargs = {"use_fp16": False}
                if self.device:
                    kwargs["device"] = self.device
                self._model = BGEM3FlagModel(self.model_name, **kwargs)
                self._backend = "FlagEmbedding"
                return
            except Exception as flag_embedding_error:
                raise RuntimeError(
                    "BGE-M3 embedding requires sentence-transformers or FlagEmbedding. "
                    f"sentence-transformers error: {sentence_transformers_error}; "
                    f"FlagEmbedding error: {flag_embedding_error}"
                ) from flag_embedding_error

    def encode(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        self.load()
        if not texts:
            return []
        if self._backend == "sentence_transformers":
            vectors = self._model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
            )
            return [vector_to_list(vector) for vector in vectors]
        if self._backend == "FlagEmbedding":
            payload = self._model.encode(
                texts,
                batch_size=batch_size,
                max_length=8192,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            dense_vectors = payload["dense_vecs"] if isinstance(payload, dict) else payload
            return [vector_to_list(vector) for vector in dense_vectors]
        raise RuntimeError("BGE-M3 backend is not loaded")


class EmbeddingEngine:
    def __init__(self, options: EmbeddingOptions) -> None:
        self.options = options
        self.state_path = options.root / "04_VectorDB" / "embedding_engine_state.json"
        self.report_path = options.root / "04_VectorDB" / "embedding_report.json"
        self.log_dir = options.root / "07_Workflows" / "logs"
        self.state = self.load_state()

    def ensure_directories(self) -> None:
        paths = [self.log_dir]
        if not self.options.dry_run:
            paths.extend([self.options.root / "04_VectorDB", self.options.db_dir])
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    def index_all(self) -> dict[str, Any]:
        self.ensure_directories()
        papers = discover_papers(self.options.root)
        if self.options.limit is not None:
            papers = papers[: self.options.limit]
        records = build_embedding_records(papers, levels=self.options.levels)
        records_to_index = self.select_records_to_index(records)
        logger.info("Discovered {} records, {} need indexing", len(records), len(records_to_index))

        if self.options.dry_run:
            report = self.build_report(records, records_to_index, status="dry_run")
            write_json_atomic(self.report_path, report)
            return report

        embedder = BgeM3Embedder(
            model_name=self.options.model_name,
            device=self.options.device,
            normalize_embeddings=self.options.normalize_embeddings,
        )
        vector_rows: list[dict[str, Any]] = []
        total = len(records_to_index)
        for i, batch in enumerate(batched(records_to_index, self.options.batch_size)):
            texts = [record.text for record in batch]
            vectors = embedder.encode(texts, batch_size=self.options.batch_size)
            for record, vector in zip(batch, vectors):
                vector_rows.append(self.to_vector_row(record, vector))
            if total >= 10 and (i + 1) % max(1, total // 10) == 0:
                logger.info(
                    "Embedding progress: {}/{} records ({:.0f}%)",
                    min((i + 1) * self.options.batch_size, total),
                    total,
                    min((i + 1) * self.options.batch_size, total) / total * 100,
                )

        store = LanceVectorStore(db_dir=self.options.db_dir, table_name=self.options.table_name)
        store_status = store.upsert_vectors(vector_rows)
        self.update_state(records_to_index)
        report = self.build_report(records, records_to_index, status="indexed")
        report["store_status"] = store_status
        write_json_atomic(self.report_path, report)
        return report

    def search(
        self,
        query: str,
        top_k: int,
        level: str | None = None,
        tags: list[str] | None = None,
        year: int | None = None,
        year_gte: int | None = None,
        year_lte: int | None = None,
        doi: str | None = None,
    ) -> list[dict[str, Any]]:
        embedder = BgeM3Embedder(
            model_name=self.options.model_name,
            device=self.options.device,
            normalize_embeddings=self.options.normalize_embeddings,
        )
        query_vector = embedder.encode([query], batch_size=1)[0]
        store = LanceVectorStore(db_dir=self.options.db_dir, table_name=self.options.table_name)
        results = store.search(
            query_vector=query_vector,
            top_k=top_k,
            level=level,
            tags=tags,
            year=year,
            year_gte=year_gte,
            year_lte=year_lte,
            doi=doi,
        )
        return [
            {
                "record_id": result.record_id,
                "paper_id": result.paper_id,
                "level": result.level,
                "score": result.score,
                "title": result.title,
                "doi": result.doi,
                "year": result.year,
                "tags": result.tags,
                "text": result.text,
                "metadata": result.metadata,
            }
            for result in results
        ]

    def record_needs_index(self, record: EmbeddingRecord) -> bool:
        entry = self.state.get("records", {}).get(record.record_id)
        if not entry:
            return True
        return (
            entry.get("text_hash") != record.text_hash
            or entry.get("embedding_model") != self.options.model_name
            or entry.get("embedding_engine_version") != EMBEDDING_ENGINE_VERSION
        )

    def select_records_to_index(self, records: list[EmbeddingRecord]) -> list[EmbeddingRecord]:
        if self.options.force:
            return records
        changed_groups = {
            (record.paper_id, record.level)
            for record in records
            if self.record_needs_index(record)
        }
        return [
            record
            for record in records
            if (record.paper_id, record.level) in changed_groups
        ]

    def to_vector_row(self, record: EmbeddingRecord, vector: list[float]) -> dict[str, Any]:
        return {
            "record_id": record.record_id,
            "paper_id": record.paper_id,
            "level": record.level,
            "source_id": record.source_id,
            "title": record.title,
            "doi": record.doi,
            "year": record.year,
            "tags": record.tags,
            "text": record.text,
            "text_hash": record.text_hash,
            "vector": vector,
            "embedding_model": self.options.model_name,
            "embedding_engine_version": EMBEDDING_ENGINE_VERSION,
            "indexed_at": utc_now(),
            "metadata": record.metadata,
        }

    def update_state(self, records: list[EmbeddingRecord]) -> None:
        self.state.setdefault("records", {})
        for record in records:
            self.state["records"][record.record_id] = {
                "paper_id": record.paper_id,
                "level": record.level,
                "text_hash": record.text_hash,
                "embedding_model": self.options.model_name,
                "embedding_engine_version": EMBEDDING_ENGINE_VERSION,
                "updated_at": utc_now(),
            }
        self.state["version"] = EMBEDDING_ENGINE_VERSION
        self.state["updated_at"] = utc_now()
        write_json_atomic(self.state_path, self.state)

    def build_report(
        self,
        all_records: list[EmbeddingRecord],
        indexed_records: list[EmbeddingRecord],
        status: str,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "embedding_engine_version": EMBEDDING_ENGINE_VERSION,
            "embedding_model": self.options.model_name,
            "db_dir": str(self.options.db_dir),
            "table_name": self.options.table_name,
            "generated_at": utc_now(),
            "total_records": len(all_records),
            "records_to_index": len(indexed_records),
            "levels": count_by_level(all_records),
            "levels_to_index": count_by_level(indexed_records),
            "embedding_regenerated": False if status == "dry_run" else bool(indexed_records),
            "summary_regenerated": False,
            "pdf_parsing_regenerated": False,
        }

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": EMBEDDING_ENGINE_VERSION, "records": {}}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.state_path.with_suffix(".corrupt.json")
            self.state_path.replace(backup)
            return {"version": EMBEDDING_ENGINE_VERSION, "records": {}}


def discover_papers(root: str | Path = PROJECT_ROOT) -> list[PaperDocument]:
    root = Path(root)
    records: dict[str, dict[str, Path | None]] = {}
    for path in sorted((root / "02_Metadata" / "yaml").glob("*.metadata.yaml")):
        key = path.name[: -len(".metadata.yaml")]
        records.setdefault(key, {})["metadata_path"] = path
    for path in sorted((root / "02_Metadata" / "papers").glob("*.metadata.json")):
        key = path.name[: -len(".metadata.json")]
        records.setdefault(key, {})["metadata_json_path"] = path
    for path in sorted((root / "03_Summary" / "raw_text").glob("*.txt")):
        key = path.stem
        records.setdefault(key, {})["raw_text_path"] = path

    papers: list[PaperDocument] = []
    for key, paths in sorted(records.items()):
        metadata_path = paths.get("metadata_path") or paths.get("metadata_json_path")
        metadata = load_metadata(metadata_path)
        paper_id = str(metadata.get("paper_id") or key)
        title = clean_scalar(metadata.get("title") or dig(metadata, "metadata", "title"))
        doi = normalize_doi(metadata.get("doi") or dig(metadata, "metadata", "doi"))
        year = normalize_year(metadata.get("year") or dig(metadata, "metadata", "year"))
        authors = normalize_authors(metadata.get("authors") or dig(metadata, "metadata", "authors"))
        abstract = clean_scalar(metadata.get("abstract"))
        tags = load_paper_tags(root, paper_id)
        summary_path = find_summary_path(root, paper_id, key)
        raw_text_path = paths.get("raw_text_path") or find_raw_text_path(root, key, paper_id, metadata)
        chunk_paths = find_chunk_paths(root, paper_id, key)
        papers.append(
            PaperDocument(
                key=key,
                paper_id=paper_id,
                title=title,
                doi=doi,
                year=year,
                authors=authors,
                abstract=abstract,
                tags=tags,
                metadata=metadata,
                metadata_path=metadata_path,
                summary_path=summary_path,
                raw_text_path=raw_text_path,
                chunk_paths=chunk_paths,
            )
        )
    return papers


def build_embedding_records(
    papers: list[PaperDocument],
    levels: list[str] | None = None,
) -> list[EmbeddingRecord]:
    enabled = set(levels or SUPPORTED_LEVELS)
    records: list[EmbeddingRecord] = []
    for paper in papers:
        if LEVEL_METADATA in enabled:
            text = build_metadata_text(paper)
            if text:
                records.append(make_record(paper, LEVEL_METADATA, "metadata", text, {"kind": "metadata"}))

        if LEVEL_SUMMARY in enabled:
            text = read_text_if_exists(paper.summary_path)
            if text:
                records.append(make_record(paper, LEVEL_SUMMARY, "summary", text, {"kind": "summary"}))

        if LEVEL_CHUNK in enabled:
            chunk_records = build_chunk_records(paper)
            records.extend(chunk_records)
    return records


def build_metadata_text(paper: PaperDocument) -> str:
    parts = [
        f"Title: {paper.title}" if paper.title else "",
        f"DOI: {paper.doi}" if paper.doi else "",
        f"Year: {paper.year}" if paper.year else "",
        "Authors: " + "; ".join(paper.authors) if paper.authors else "",
        f"Abstract: {paper.abstract}" if paper.abstract else "",
        "Tags: " + "; ".join(paper.tags) if paper.tags else "",
    ]
    return "\n".join(part for part in parts if part).strip()


def build_chunk_records(paper: PaperDocument) -> list[EmbeddingRecord]:
    if paper.chunk_paths:
        records: list[EmbeddingRecord] = []
        for path in paper.chunk_paths:
            if path.suffix.lower() == ".json":
                records.extend(records_from_json_chunks(paper, path))
            else:
                records.extend(records_from_text_chunks(paper, path))
        return records

    summary_text = read_text_if_exists(paper.summary_path)
    if summary_text:
        return [
            make_record(
                paper,
                LEVEL_CHUNK,
                f"summary_chunk_{index:04d}",
                chunk,
                {"kind": "summary_chunk", "chunk_index": index},
            )
            for index, chunk in enumerate(split_text(summary_text), start=1)
        ]

    raw_text = read_text_if_exists(paper.raw_text_path)
    return [
        make_record(
            paper,
            LEVEL_CHUNK,
            f"raw_text_chunk_{index:04d}",
            chunk,
            {"kind": "raw_text_chunk", "chunk_index": index},
        )
        for index, chunk in enumerate(split_text(raw_text), start=1)
    ]


def records_from_text_chunks(paper: PaperDocument, path: Path) -> list[EmbeddingRecord]:
    text = read_text_if_exists(path)
    return [
        make_record(
            paper,
            LEVEL_CHUNK,
            f"{path.stem}_{index:04d}",
            chunk,
            {"kind": "chunk_file", "path": str(path), "chunk_index": index},
        )
        for index, chunk in enumerate(split_text(text), start=1)
    ]


def records_from_json_chunks(paper: PaperDocument, path: Path) -> list[EmbeddingRecord]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        items = payload.get("chunks") if isinstance(payload.get("chunks"), list) else [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        items = []

    records: list[EmbeddingRecord] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text = clean_scalar(item.get("text") or item.get("content"))
        if not text:
            continue
        source_id = str(item.get("chunk_id") or item.get("source_id") or f"{path.stem}_{index:04d}")
        metadata = {
            "kind": "json_chunk",
            "path": str(path),
            "chunk_index": index,
            "section": item.get("section"),
            "page": item.get("page"),
            "paragraph": item.get("paragraph"),
        }
        records.append(make_record(paper, LEVEL_CHUNK, source_id, text, metadata))
    return records


def make_record(
    paper: PaperDocument,
    level: str,
    source_id: str,
    text: str,
    metadata: dict[str, Any],
) -> EmbeddingRecord:
    normalized_text = clean_scalar(text) or ""
    text_hash = sha256_text(normalized_text)
    record_id = f"{paper.paper_id}:{level}:{source_id}:{text_hash[:12]}"
    return EmbeddingRecord(
        record_id=record_id,
        paper_id=paper.paper_id,
        level=level,
        source_id=source_id,
        title=paper.title,
        doi=paper.doi,
        year=paper.year,
        tags=paper.tags,
        text=normalized_text,
        text_hash=text_hash,
        metadata=metadata,
    )


def load_metadata(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "metadata" in payload and "title" not in payload:
        metadata = payload.get("metadata") or {}
        return {
            "paper_id": payload.get("paper_id"),
            "title": metadata.get("title"),
            "year": metadata.get("year"),
            "doi": metadata.get("doi"),
            "authors": metadata.get("authors"),
            "abstract": payload.get("abstract"),
            "outputs": payload.get("outputs", {}),
            "metadata": metadata,
        }
    return payload


def load_paper_tags(root: Path, paper_id: str) -> list[str]:
    path = root / "05_Index" / "tags" / safe_path_name(paper_id) / "tags.yaml"
    if not path.exists():
        return []
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    tags: list[str] = []
    for category_tags in (payload.get("assigned_tags") or {}).values():
        if isinstance(category_tags, list):
            tags.extend(str(tag) for tag in category_tags)
    return unique_preserve_order(tags)


def find_summary_path(root: Path, paper_id: str, key: str) -> Path | None:
    candidates = [
        root / "03_Summary" / safe_path_name(paper_id) / "summary.md",
        root / "03_Summary" / safe_path_name(key) / "summary.md",
        root / "03_Summary" / "summaries" / f"{paper_id}.md",
        root / "03_Summary" / "summaries" / f"{key}.md",
        root / "03_Summary" / f"{paper_id}.summary.md",
        root / "03_Summary" / f"{key}.summary.md",
    ]
    return first_existing_path(candidates)


def find_raw_text_path(root: Path, key: str, paper_id: str, metadata: dict[str, Any]) -> Path | None:
    candidates = [
        path_or_none(dig(metadata, "outputs", "raw_text_path")),
        root / "03_Summary" / "raw_text" / f"{key}.txt",
        root / "03_Summary" / "raw_text" / f"{paper_id}.txt",
    ]
    return first_existing_path(candidates)


def find_chunk_paths(root: Path, paper_id: str, key: str) -> list[Path]:
    candidates: list[Path] = []

    # P0 fix: Also scan 03_Evidence/ for evidence_chunks.json
    evidence_chunk_path = root / "03_Evidence" / paper_id / "evidence_chunks.json"
    if evidence_chunk_path.exists():
        candidates.append(evidence_chunk_path)
    # Also try with key if different
    if key != paper_id:
        evidence_chunk_path2 = root / "03_Evidence" / key / "evidence_chunks.json"
        if evidence_chunk_path2.exists():
            candidates.append(evidence_chunk_path2)

    for identifier in [paper_id, key]:
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


def split_text(text: str, max_chars: int = 1600, overlap_chars: int = 180) -> list[str]:
    text = clean_scalar(text) or ""
    if not text:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs or [text]:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
            overlap = current[-overlap_chars:] if overlap_chars else ""
            current = f"{overlap}\n\n{paragraph}".strip()
        else:
            for start in range(0, len(paragraph), max_chars - overlap_chars):
                chunks.append(paragraph[start : start + max_chars])
            current = ""
    if current:
        chunks.append(current)
    return chunks


def configure_logging(root: Path) -> Path:
    log_dir = root / "07_Workflows" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"embedding_engine_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    try:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(log_path, level="INFO", rotation="10 MB", retention=20, encoding="utf-8")
    except AttributeError:
        pass
    return log_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and search Scientra Copilot LanceDB embeddings with BGE-M3.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index metadata, summary, and chunk vectors.")
    add_common_args(index_parser)
    index_parser.add_argument("--levels", nargs="+", default=SUPPORTED_LEVELS, choices=SUPPORTED_LEVELS)
    index_parser.add_argument("--batch-size", type=int, default=16)
    index_parser.add_argument("--force", action="store_true")
    index_parser.add_argument("--dry-run", action="store_true")
    index_parser.add_argument("--limit", type=int, default=None)

    search_parser = subparsers.add_parser("search", help="Vector search with optional filters.")
    add_common_args(search_parser)
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=10)
    search_parser.add_argument("--level", choices=SUPPORTED_LEVELS, default=None)
    search_parser.add_argument("--tag", action="append", dest="tags", default=None)
    search_parser.add_argument("--year", type=int, default=None)
    search_parser.add_argument("--year-gte", type=int, default=None)
    search_parser.add_argument("--year-lte", type=int, default=None)
    search_parser.add_argument("--doi", default=None)

    return parser


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--model-name", default=os.environ.get("BGE_M3_MODEL", DEFAULT_MODEL_NAME))
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_LANCEDB_DIR)
    parser.add_argument("--table-name", default=DEFAULT_TABLE_NAME)
    parser.add_argument("--device", default=os.environ.get("BGE_M3_DEVICE"))
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--json", action="store_true")


def options_from_args(args: argparse.Namespace) -> EmbeddingOptions:
    root = args.root.resolve()
    db_dir = args.db_dir.resolve() if Path(args.db_dir).is_absolute() else (root / args.db_dir).resolve()
    return EmbeddingOptions(
        root=root,
        model_name=args.model_name,
        db_dir=db_dir,
        table_name=args.table_name,
        batch_size=getattr(args, "batch_size", 16),
        device=args.device,
        normalize_embeddings=not args.no_normalize,
        force=getattr(args, "force", False),
        dry_run=getattr(args, "dry_run", False),
        levels=getattr(args, "levels", SUPPORTED_LEVELS),
        limit=getattr(args, "limit", None),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    options = options_from_args(args)
    log_path = configure_logging(options.root)
    logger.info("Embedding Engine started")
    logger.info("Log file: {}", log_path)
    logger.info("Model: {}", options.model_name)
    logger.info("LanceDB: {}", options.db_dir)

    engine = EmbeddingEngine(options)
    try:
        if args.command == "index":
            payload = engine.index_all()
        else:
            payload = {
                "query": args.query,
                "results": engine.search(
                    query=args.query,
                    top_k=args.top_k,
                    level=args.level,
                    tags=args.tags,
                    year=args.year,
                    year_gte=args.year_gte,
                    year_lte=args.year_lte,
                    doi=args.doi,
                ),
            }
    except Exception as exc:
        logger.error("Embedding Engine failed: {}", exc)
        if args.json:
            print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        else:
            print(f"Embedding Engine failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
    return 0


def batched(values: list[Any], batch_size: int) -> list[list[Any]]:
    batch_size = max(1, batch_size)
    return [values[index : index + batch_size] for index in range(0, len(values), batch_size)]


def count_by_level(records: list[EmbeddingRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.level] = counts.get(record.level, 0) + 1
    return counts


def vector_to_list(vector: Any) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in vector]


def read_text_if_exists(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def first_existing_path(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path and path.exists():
            return path
    return None


def path_or_none(value: Any) -> Path | None:
    if not value:
        return None
    return Path(str(value))


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


def normalize_doi(value: Any) -> str | None:
    text = clean_scalar(value)
    if not text:
        return None
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.IGNORECASE)
    if not match:
        return text.lower()
    return match.group(0).strip().rstrip(".,;:)])").lower()


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
        return [value]
    if isinstance(value, list):
        authors: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    authors.append(str(name))
            elif item:
                authors.append(str(item))
        return unique_preserve_order(authors)
    return []


def safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe or "paper"


def unique_preserve_order(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        text = str(value)
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_embedding_config(path: str | Path = DEFAULT_EMBEDDING_CONFIG_PATH) -> dict[str, Any]:
    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    payload.setdefault("embedding_model", DEFAULT_MODEL_NAME)
    payload.setdefault("embedding_dimension", 1024)
    payload.setdefault("device", "auto")
    payload.setdefault("chunking", {})
    payload.setdefault("lancedb", {})
    payload["lancedb"].setdefault("path", "04_VectorDB/lancedb")
    payload["lancedb"].setdefault(
        "tables",
        {
            "metadata": "metadata_embeddings",
            "summary": "summary_embeddings",
            "chunks": "chunk_embeddings",
        },
    )
    payload.setdefault("tags", {})
    payload["tags"].setdefault("use_assigned_tags_only", True)
    payload["tags"].setdefault("include_candidate_tags", False)
    return payload


def run_embedding_dry_run(
    root: str | Path = PROJECT_ROOT,
    config_path: str | Path = DEFAULT_EMBEDDING_CONFIG_PATH,
    batch_name: str = "batch_5",
    report_path: str | Path = DEFAULT_DRY_RUN_REPORT_PATH,
) -> dict[str, Any]:
    """Validate P6 inputs without loading BGE-M3 or touching LanceDB."""
    root = Path(root)
    config = load_embedding_config(config_path)
    papers = discover_batch_embedding_inputs(root=root, batch_name=batch_name)
    paper_reports = [build_embedding_dry_run_item(root, item, config) for item in papers]
    passed = [item for item in paper_reports if item["can_enter_real_embedding"]]
    failed = [item for item in paper_reports if not item["can_enter_real_embedding"]]
    lancedb_plan = build_vector_store_dry_run_plan(root, config)
    report = {
        "status": "dry_run",
        "embedding_engine_version": EMBEDDING_ENGINE_VERSION,
        "embedding_model": config.get("embedding_model"),
        "embedding_dimension": config.get("embedding_dimension"),
        "device": config.get("device"),
        "bge_model_loaded": False,
        "embeddings_generated": False,
        "lancedb_created": False,
        "lancedb_written": False,
        "lancedb_plan": lancedb_plan,
        "checked_papers": len(paper_reports),
        "passed_papers": len(passed),
        "failed_papers": len(failed),
        "all_passed": len(paper_reports) > 0 and not failed,
        "recommend_real_run": len(paper_reports) > 0 and not failed,
        "papers": paper_reports,
        "generated_at": utc_now(),
    }
    write_embedding_dry_run_markdown(Path(report_path), report)
    report["report_path"] = str(report_path)
    return report


def discover_batch_embedding_inputs(root: Path, batch_name: str) -> list[dict[str, Any]]:
    batch_dir = root / "01_PDF" / batch_name
    pdf_paths = sorted(batch_dir.glob("*.pdf"))
    items: list[dict[str, Any]] = []
    for pdf_path in pdf_paths:
        stem = pdf_path.stem
        safe_stem = safe_path_name(stem)
        raw_safe_stem = raw_safe_path_name(stem)
        truncated_dirs = [
            root / "02_Metadata" / candidate / "metadata.yaml"
            for candidate in [*truncated_safe_candidates(safe_stem), raw_safe_stem, *truncated_safe_candidates(raw_safe_stem)]
        ]
        metadata_path = first_existing_path(
            [
                root / "02_Metadata" / stem / "metadata.yaml",
                root / "02_Metadata" / safe_stem / "metadata.yaml",
                root / "02_Metadata" / raw_safe_stem / "metadata.yaml",
                *truncated_dirs,
            ]
        ) or root / "02_Metadata" / safe_stem / "metadata.yaml"
        metadata = read_yaml_if_exists(metadata_path)
        paper_id = str(metadata.get("paper_id") or safe_stem)
        tags_path = first_existing_path(
            [
                root / "02_Metadata" / stem / "tags.yaml",
                root / "02_Metadata" / safe_stem / "tags.yaml",
                root / "02_Metadata" / raw_safe_stem / "tags.yaml",
                root / "05_Index" / "tags" / paper_id / "tags.yaml",
                root / "05_Index" / "tags" / safe_stem / "tags.yaml",
            ]
        ) or root / "02_Metadata" / safe_stem / "tags.yaml"
        summary_path = first_existing_path(
            [
                root / "03_Summary" / paper_id / "summary.md",
                root / "03_Summary" / stem / "summary.md",
                root / "03_Summary" / safe_stem / "summary.md",
                root / "03_Summary" / raw_safe_stem / "summary.md",
            ]
        ) or root / "03_Summary" / safe_stem / "summary.md"
        raw_text_path = find_batch_raw_text_path(root, stem)
        items.append(
            {
                "stem": stem,
                "pdf_path": pdf_path,
                "metadata_path": metadata_path,
                "tags_path": tags_path,
                "summary_path": summary_path,
                "raw_text_path": raw_text_path,
            }
        )
    return items


def find_batch_raw_text_path(root: Path, stem: str) -> Path | None:
    raw_dir = root / "03_Summary" / "raw_text"
    safe_stem = safe_path_name(stem)
    raw_safe_stem = raw_safe_path_name(stem)
    matches = sorted(raw_dir.glob(f"{stem}_*.txt"))
    matches.extend(sorted(raw_dir.glob(f"{safe_stem}_*.txt")))
    matches.extend(sorted(raw_dir.glob(f"{raw_safe_stem}_*.txt")))
    for candidate in [*truncated_safe_candidates(safe_stem), *truncated_safe_candidates(raw_safe_stem)]:
        matches.extend(sorted(raw_dir.glob(f"{candidate}_*.txt")))
    if matches:
        return matches[0]
    exact = raw_dir / f"{stem}.txt"
    safe_exact = raw_dir / f"{safe_stem}.txt"
    return first_existing_path([exact, safe_exact])


def truncated_safe_candidates(safe_stem: str) -> list[str]:
    values = []
    for length in [160, 140, 120, 100, 80]:
        if len(safe_stem) > length:
            values.append(safe_stem[:length])
    return values


def raw_safe_path_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")[:180] or "paper"


def build_embedding_dry_run_item(
    root: Path,
    item: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    metadata_path = item["metadata_path"]
    tags_path = item["tags_path"]
    summary_path = item["summary_path"]
    raw_text_path = item["raw_text_path"]

    metadata = read_yaml_if_exists(metadata_path)
    tags_payload = read_yaml_if_exists(tags_path)
    summary_text = read_text_if_exists(summary_path)
    raw_text = read_text_if_exists(raw_text_path)
    paper_id = str(
        metadata.get("paper_id")
        or tags_payload.get("paper_id")
        or item["stem"]
    )

    assigned_tags = tags_payload.get("assigned_tags") or {}
    candidate_tags = tags_payload.get("candidate_tags") or {}
    assigned_filter_tags = flatten_category_tags(assigned_tags)
    candidate_filter_tags = flatten_category_tags(candidate_tags)
    candidate_tags_excluded = (
        bool(config.get("tags", {}).get("use_assigned_tags_only", True))
        and not bool(config.get("tags", {}).get("include_candidate_tags", False))
        and not set(candidate_filter_tags).intersection(assigned_filter_tags)
    )

    metadata_text = build_metadata_embedding_text(metadata, assigned_filter_tags)
    summary_embedding_text = build_summary_embedding_text(summary_text)
    chunks = chunk_raw_text_for_embedding(
        raw_text=raw_text,
        paper_id=paper_id,
        config=config.get("chunking") or {},
    )
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    chunk_ids_again = [
        chunk["chunk_id"]
        for chunk in chunk_raw_text_for_embedding(
            raw_text=raw_text,
            paper_id=paper_id,
            config=config.get("chunking") or {},
        )
    ]

    checks = {
        "metadata_yaml_exists": metadata_path.exists(),
        "tags_yaml_exists": tags_path.exists(),
        "summary_md_exists": summary_path.exists(),
        "raw_text_exists": raw_text_path is not None and raw_text_path.exists(),
        "assigned_tags_exists": bool(assigned_filter_tags),
        "candidate_tags_excluded_from_filter": candidate_tags_excluded,
        "summary_has_citation_anchors": summary_has_citation_anchors(summary_text),
        "raw_text_chunkable": bool(chunks),
        "chunk_id_stable": chunk_ids == chunk_ids_again and bool(chunk_ids),
        "metadata_text_ready": bool(metadata_text),
        "summary_text_ready": bool(summary_embedding_text),
    }
    failures = [name for name, passed in checks.items() if not passed]

    return {
        "paper_key": item["stem"],
        "paper_id": paper_id,
        "metadata_path": str(metadata_path),
        "tags_path": str(tags_path),
        "summary_path": str(summary_path),
        "raw_text_path": str(raw_text_path) if raw_text_path else None,
        "checks": checks,
        "failures": failures,
        "can_enter_real_embedding": not failures,
        "assigned_tags": assigned_tags,
        "candidate_tags": candidate_tags,
        "formal_filter_tags": assigned_filter_tags,
        "candidate_filter_tags": candidate_filter_tags,
        "candidate_tags_excluded": candidate_tags_excluded,
        "metadata_text_length": len(metadata_text),
        "metadata_text_preview": preview_text(metadata_text),
        "summary_text_length": len(summary_embedding_text),
        "summary_text_preview": preview_text(summary_embedding_text),
        "raw_text_length": len(raw_text),
        "chunk_count": len(chunks),
        "chunk_id_stable": checks["chunk_id_stable"],
        "chunk_id_preview": chunk_ids[:5],
        "first_chunk_preview": preview_text(chunks[0]["text"]) if chunks else "",
        "records_planned": {
            "metadata": 1 if metadata_text else 0,
            "summary": 1 if summary_embedding_text else 0,
            "chunks": len(chunks),
        },
    }


def chunk_raw_text_for_embedding(
    raw_text: str,
    paper_id: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    try:
        from scientra.chunker import ChunkingConfig, chunk_text
    except ModuleNotFoundError:
        from scientra.chunker import ChunkingConfig, chunk_text

    chunking_config = ChunkingConfig.from_mapping(config)
    chunks = chunk_text(raw_text, paper_id=paper_id, source="raw_text", config=chunking_config)
    return [
        {
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "text_hash": chunk.text_hash,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "source_section": chunk.source_section,
        }
        for chunk in chunks
    ]


def build_metadata_embedding_text(metadata: dict[str, Any], assigned_filter_tags: list[str]) -> str:
    authors = normalize_authors(metadata.get("authors"))
    parts = [
        f"Title: {clean_scalar(metadata.get('title'))}" if metadata.get("title") else "",
        f"DOI: {normalize_doi(metadata.get('doi'))}" if metadata.get("doi") else "",
        f"Year: {normalize_year(metadata.get('year'))}" if metadata.get("year") else "",
        f"Journal: {clean_scalar(metadata.get('journal'))}" if metadata.get("journal") else "",
        "Authors: " + "; ".join(authors) if authors else "",
        f"Abstract: {clean_scalar(metadata.get('abstract'))}" if metadata.get("abstract") else "",
        "Assigned Tags: " + "; ".join(assigned_filter_tags) if assigned_filter_tags else "",
    ]
    return "\n".join(part for part in parts if part).strip()


def build_summary_embedding_text(summary_text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", (summary_text or "").strip())


def summary_has_citation_anchors(summary_text: str) -> bool:
    if not summary_text:
        return False
    has_heading = re.search(r"(?mi)^#\s+Citation Anchors\s*$", summary_text) is not None
    has_anchor = re.search(r"\bS\d{3}\b", summary_text) is not None
    return has_heading and has_anchor


def read_yaml_if_exists(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def flatten_category_tags(category_tags: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for category, tags in (category_tags or {}).items():
        if not isinstance(tags, list):
            continue
        for tag in tags:
            values.append(f"{category}:{tag}")
    return unique_preserve_order(values)


def preview_text(text: str, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_vector_store_dry_run_plan(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    try:
        from scientra.vector_store import build_lancedb_dry_run_plan
    except ModuleNotFoundError:
        from scientra.vector_store import build_lancedb_dry_run_plan

    plan = build_lancedb_dry_run_plan(root, config)
    return {
        "path": plan.path,
        "tables": plan.tables,
        "will_connect": plan.will_connect,
        "will_create_database": plan.will_create_database,
        "will_create_tables": plan.will_create_tables,
        "will_write_records": plan.will_write_records,
    }


def write_embedding_dry_run_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Embedding Engine Dry-Run Report",
        "",
        f"Generated at: {report['generated_at']}",
        "",
        "## Scope",
        "",
        "- Mode: P6 dry-run",
        "- DeepSeek called: false",
        "- PDF reparsed: false",
        "- Tag Engine rerun: false",
        "- BGE-M3 loaded: false",
        "- Real embeddings generated: false",
        "- LanceDB created: false",
        "- LanceDB written: false",
        "- Query API entered: false",
        "",
        "## Configuration",
        "",
        f"- embedding_model: {report['embedding_model']}",
        f"- embedding_dimension: {report['embedding_dimension']}",
        f"- device: {report['device']}",
        f"- lancedb_path: {report['lancedb_plan']['path']}",
        f"- lancedb_tables: {json.dumps(report['lancedb_plan']['tables'], ensure_ascii=False)}",
        "- tags: assigned_tags only; candidate_tags excluded from formal filter fields",
        "",
        "## Summary",
        "",
        f"- Checked papers: {report['checked_papers']}",
        f"- Passed papers: {report['passed_papers']}",
        f"- Failed papers: {report['failed_papers']}",
        f"- Batch all passed: {str(report['all_passed']).lower()}",
        f"- Recommend P6 real-run: {str(report['recommend_real_run']).lower()}",
        "",
    ]

    for paper in report["papers"]:
        lines.extend(
            [
                f"## {paper['paper_key']}",
                "",
                f"- paper_id: {paper['paper_id']}",
                f"- metadata.yaml: {paper['metadata_path']}",
                f"- tags.yaml: {paper['tags_path']}",
                f"- summary.md: {paper['summary_path']}",
                f"- raw_text: {paper['raw_text_path']}",
                f"- can_enter_real_embedding: {str(paper['can_enter_real_embedding']).lower()}",
                f"- failures: {', '.join(paper['failures']) if paper['failures'] else 'None'}",
                f"- chunk_count: {paper['chunk_count']}",
                f"- chunk_id_stable: {str(paper['chunk_id_stable']).lower()}",
                f"- chunk_id_preview: {', '.join(paper['chunk_id_preview']) if paper['chunk_id_preview'] else 'None'}",
                f"- assigned_tags: {format_category_tags(paper['assigned_tags'])}",
                f"- candidate_tags: {format_category_tags(paper['candidate_tags'])}",
                f"- candidate_tags_excluded: {str(paper['candidate_tags_excluded']).lower()}",
                f"- formal_filter_tags: {', '.join(paper['formal_filter_tags']) if paper['formal_filter_tags'] else 'None'}",
                "",
                "### Checks",
                "",
            ]
        )
        for check_name, check_value in paper["checks"].items():
            lines.append(f"- {check_name}: {str(check_value).lower()}")
        lines.extend(
            [
                "",
                "### Metadata Embedding Input Preview",
                "",
                paper["metadata_text_preview"] or "EMPTY",
                "",
                "### Summary Embedding Input Preview",
                "",
                paper["summary_text_preview"] or "EMPTY",
                "",
                "### First Chunk Preview",
                "",
                paper["first_chunk_preview"] or "EMPTY",
                "",
            ]
        )

    lines.extend(
        [
            "## Real-Run Recommendation",
            "",
            (
                "Recommendation: enter P6 real-run with assigned_tags only."
                if report["recommend_real_run"]
                else "Recommendation: do not enter P6 real-run until failed checks are fixed."
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def format_category_tags(category_tags: dict[str, Any]) -> str:
    if not category_tags:
        return "None"
    parts = []
    for category, tags in category_tags.items():
        if tags:
            parts.append(f"{category}: {', '.join(str(tag) for tag in tags)}")
    return "; ".join(parts) if parts else "None"


def run_embedding_real_run(
    root: str | Path = PROJECT_ROOT,
    config_path: str | Path = DEFAULT_EMBEDDING_CONFIG_PATH,
    batch_name: str = "batch_5",
    report_path: str | Path = DEFAULT_REAL_RUN_REPORT_PATH,
    status_path: str | Path = DEFAULT_EMBEDDING_STATUS_PATH,
    batch_size: int = 8,
) -> dict[str, Any]:
    """Build real BGE-M3 embeddings and write the three configured LanceDB tables."""
    root = Path(root)
    config = load_embedding_config(config_path)
    dry_report = run_embedding_dry_run(
        root=root,
        config_path=config_path,
        batch_name=batch_name,
        report_path=root / "05_Index" / "embedding_dry_run_report.md",
    )
    if not dry_report["all_passed"]:
        raise RuntimeError("P6 real-run blocked: dry-run checks failed")

    started_at = time.perf_counter()
    records_by_level = build_real_embedding_records(dry_report["papers"], config)
    model_started_at = time.perf_counter()
    embedder = BgeM3Embedder(
        model_name=str(config.get("embedding_model") or DEFAULT_MODEL_NAME),
        device=str(config.get("device") or "auto"),
        normalize_embeddings=True,
    )
    embedder.load()
    model_load_seconds = time.perf_counter() - model_started_at

    embedding_started_at = time.perf_counter()
    rows_by_level: dict[str, list[dict[str, Any]]] = {}
    for level, records in records_by_level.items():
        rows_by_level[level] = embed_records_for_lancedb(
            embedder=embedder,
            records=records,
            batch_size=batch_size,
            model_name=str(config.get("embedding_model") or DEFAULT_MODEL_NAME),
        )
    embedding_seconds = time.perf_counter() - embedding_started_at

    table_status = write_lancedb_tables(root=root, config=config, rows_by_level=rows_by_level)
    record_counts = count_lancedb_tables(root=root, config=config)
    total_seconds = time.perf_counter() - started_at
    lancedb_path = resolve_lancedb_path(root, config)
    lancedb_size = directory_size(lancedb_path)
    chunk_counts = {
        paper["paper_key"]: int(paper["chunk_count"])
        for paper in dry_report["papers"]
    }
    failed_papers = [
        paper["paper_key"]
        for paper in dry_report["papers"]
        if not paper["can_enter_real_embedding"]
    ]

    report = {
        "status": "completed",
        "embedding_engine_version": EMBEDDING_ENGINE_VERSION,
        "embedding_model": str(config.get("embedding_model") or DEFAULT_MODEL_NAME),
        "embedding_dimension": int(config.get("embedding_dimension") or 1024),
        "batch_name": batch_name,
        "paper_count": len(dry_report["papers"]),
        "metadata_embedding_count": len(records_by_level[LEVEL_METADATA]),
        "summary_embedding_count": len(records_by_level[LEVEL_SUMMARY]),
        "chunk_embedding_count": len(records_by_level[LEVEL_CHUNK]),
        "lancedb_path": str(lancedb_path),
        "lancedb_size_bytes": lancedb_size,
        "lancedb_size_human": format_bytes(lancedb_size),
        "model_load_seconds": round(model_load_seconds, 3),
        "embedding_seconds": round(embedding_seconds, 3),
        "total_seconds": round(total_seconds, 3),
        "chunk_counts": chunk_counts,
        "failed_papers": failed_papers,
        "table_status": table_status,
        "table_record_counts": record_counts,
        "recommend_p7_query_api": not failed_papers and all(
            record_counts.get(table_name, 0) > 0
            for table_name in (config.get("lancedb", {}).get("tables") or {}).values()
        ),
        "deepseek_called": False,
        "pdf_reparsed": False,
        "tag_engine_rerun": False,
        "summary_regenerated": False,
        "generated_at": utc_now(),
    }
    write_embedding_status_sqlite(Path(status_path), report, dry_report["papers"])
    write_embedding_real_run_markdown(Path(report_path), report)
    report["report_path"] = str(report_path)
    report["status_path"] = str(status_path)
    return report


def build_real_embedding_records(
    paper_reports: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {
        LEVEL_METADATA: [],
        LEVEL_SUMMARY: [],
        LEVEL_CHUNK: [],
    }
    for paper in paper_reports:
        paper_id = str(paper["paper_id"])
        metadata = read_yaml_if_exists(Path(paper["metadata_path"]))
        tags = list(paper["formal_filter_tags"])
        common = {
            "paper_id": paper_id,
            "paper_key": paper["paper_key"],
            "title": clean_scalar(metadata.get("title")),
            "doi": normalize_doi(metadata.get("doi")),
            "year": normalize_year(metadata.get("year")),
            "tags": tags,
            "candidate_tags_excluded": True,
        }
        metadata_text = build_metadata_embedding_text(metadata, tags)
        records[LEVEL_METADATA].append(
            build_real_record(
                level=LEVEL_METADATA,
                source_id="metadata",
                text=metadata_text,
                metadata={
                    **common,
                    "kind": "metadata",
                    "metadata_path": paper["metadata_path"],
                },
            )
        )

        summary_text = build_summary_embedding_text(read_text_if_exists(Path(paper["summary_path"])))
        records[LEVEL_SUMMARY].append(
            build_real_record(
                level=LEVEL_SUMMARY,
                source_id="summary",
                text=summary_text,
                metadata={
                    **common,
                    "kind": "summary",
                    "summary_path": paper["summary_path"],
                },
            )
        )

        raw_text = read_text_if_exists(Path(paper["raw_text_path"]))
        chunks = chunk_raw_text_for_embedding(
            raw_text=raw_text,
            paper_id=paper_id,
            config=config.get("chunking") or {},
        )
        for chunk in chunks:
            records[LEVEL_CHUNK].append(
                build_real_record(
                    level=LEVEL_CHUNK,
                    source_id=chunk["chunk_id"],
                    text=chunk["text"],
                    metadata={
                        **common,
                        "kind": "raw_text_chunk",
                        "raw_text_path": paper["raw_text_path"],
                        "chunk_index": chunk["chunk_index"],
                        "chunk_id": chunk["chunk_id"],
                        "char_start": chunk["char_start"],
                        "char_end": chunk["char_end"],
                        "source_section": chunk.get("source_section"),
                    },
                )
            )
    return records


def build_real_record(
    level: str,
    source_id: str,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    text = text.strip()
    paper_id = str(metadata["paper_id"])
    text_hash = sha256_text(text)
    record_id = f"{paper_id}:{level}:{safe_path_name(source_id)}:{text_hash[:12]}"
    return {
        "record_id": record_id,
        "paper_id": paper_id,
        "paper_key": metadata.get("paper_key"),
        "level": level,
        "source_id": source_id,
        "title": metadata.get("title"),
        "doi": metadata.get("doi"),
        "year": metadata.get("year"),
        "tags": list(metadata.get("tags") or []),
        "text": text,
        "text_hash": text_hash,
        "metadata": metadata,
    }


def embed_records_for_lancedb(
    embedder: BgeM3Embedder,
    records: list[dict[str, Any]],
    batch_size: int,
    model_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch in batched(records, batch_size):
        vectors = embedder.encode([record["text"] for record in batch], batch_size=batch_size)
        for record, vector in zip(batch, vectors):
            rows.append(
                {
                    **record,
                    "vector": vector,
                    "embedding_model": model_name,
                    "embedding_engine_version": EMBEDDING_ENGINE_VERSION,
                    "indexed_at": utc_now(),
                }
            )
    return rows


def write_lancedb_tables(
    root: Path,
    config: dict[str, Any],
    rows_by_level: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    tables = config.get("lancedb", {}).get("tables") or {}
    db_dir = resolve_lancedb_path(root, config)
    status: dict[str, Any] = {}
    table_map = {
        LEVEL_METADATA: tables.get("metadata", "metadata_embeddings"),
        LEVEL_SUMMARY: tables.get("summary", "summary_embeddings"),
        LEVEL_CHUNK: tables.get("chunks", "chunk_embeddings"),
    }
    for level, table_name in table_map.items():
        store = LanceVectorStore(db_dir=db_dir, table_name=table_name)
        status[table_name] = store.upsert_vectors(rows_by_level.get(level, []))
    return status


def count_lancedb_tables(root: Path, config: dict[str, Any]) -> dict[str, int]:
    try:
        import lancedb
    except Exception:
        return {}
    db = lancedb.connect(str(resolve_lancedb_path(root, config)))
    counts: dict[str, int] = {}
    for table_name in (config.get("lancedb", {}).get("tables") or {}).values():
        try:
            table = db.open_table(str(table_name))
            counts[str(table_name)] = len(table.to_arrow())
        except Exception:
            counts[str(table_name)] = 0
    return counts


def resolve_lancedb_path(root: Path, config: dict[str, Any]) -> Path:
    raw_path = Path(str(config.get("lancedb", {}).get("path") or "04_VectorDB/lancedb"))
    return raw_path if raw_path.is_absolute() else root / raw_path


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ["B", "KB", "MB", "GB"]:
        if amount < 1024 or unit == "GB":
            return f"{amount:.2f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def write_embedding_status_sqlite(
    path: Path,
    report: dict[str, Any],
    paper_reports: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_runs (
                run_id TEXT PRIMARY KEY,
                generated_at TEXT,
                embedding_model TEXT,
                paper_count INTEGER,
                metadata_count INTEGER,
                summary_count INTEGER,
                chunk_count INTEGER,
                lancedb_path TEXT,
                model_load_seconds REAL,
                embedding_seconds REAL,
                total_seconds REAL,
                recommend_p7_query_api INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_embedding_status (
                run_id TEXT,
                paper_key TEXT,
                paper_id TEXT,
                chunk_count INTEGER,
                status TEXT,
                PRIMARY KEY (run_id, paper_id)
            )
            """
        )
        run_id = report["generated_at"]
        conn.execute(
            """
            INSERT OR REPLACE INTO embedding_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                report["generated_at"],
                report["embedding_model"],
                report["paper_count"],
                report["metadata_embedding_count"],
                report["summary_embedding_count"],
                report["chunk_embedding_count"],
                report["lancedb_path"],
                report["model_load_seconds"],
                report["embedding_seconds"],
                report["total_seconds"],
                1 if report["recommend_p7_query_api"] else 0,
            ),
        )
        for paper in paper_reports:
            conn.execute(
                """
                INSERT OR REPLACE INTO paper_embedding_status VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    paper["paper_key"],
                    paper["paper_id"],
                    paper["chunk_count"],
                    "completed" if paper["can_enter_real_embedding"] else "failed",
                ),
            )


def write_embedding_real_run_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Embedding Engine Real-Run Report",
        "",
        f"Generated at: {report['generated_at']}",
        "",
        "## Scope",
        "",
        "- Mode: P6 real-run",
        "- DeepSeek called: false",
        "- PDF reparsed: false",
        "- Tag Engine rerun: false",
        "- Summary regenerated: false",
        "- BGE-M3 loaded: true",
        "- LanceDB written: true",
        "",
        "## Counts",
        "",
        f"- Literature count: {report['paper_count']}",
        f"- Metadata embeddings: {report['metadata_embedding_count']}",
        f"- Summary embeddings: {report['summary_embedding_count']}",
        f"- Chunk embeddings: {report['chunk_embedding_count']}",
        "",
        "## LanceDB",
        "",
        f"- Path: {report['lancedb_path']}",
        f"- Size: {report['lancedb_size_human']} ({report['lancedb_size_bytes']} bytes)",
        "",
        "## Timing",
        "",
        f"- BGE-M3 load time: {report['model_load_seconds']} seconds",
        f"- Embedding time: {report['embedding_seconds']} seconds",
        f"- Total time: {report['total_seconds']} seconds",
        "",
        "## Table Record Counts",
        "",
    ]
    for table_name, count in report["table_record_counts"].items():
        lines.append(f"- {table_name}: {count}")
    lines.extend(["", "## Per-Paper Chunk Counts", ""])
    for paper_key, count in report["chunk_counts"].items():
        lines.append(f"- {paper_key}: {count}")
    lines.extend(
        [
            "",
            "## Failure Audit",
            "",
            f"- Failed papers: {', '.join(report['failed_papers']) if report['failed_papers'] else 'None'}",
            "",
            "## P7 Recommendation",
            "",
            (
                "Recommendation: enter P7 Query API."
                if report["recommend_p7_query_api"]
                else "Recommendation: do not enter P7 Query API until embedding failures are fixed."
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
