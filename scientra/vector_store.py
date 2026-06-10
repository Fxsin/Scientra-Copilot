from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _detect_project_root() -> Path:
    """Walk up from this file until a 'Config/workflow_config.yaml' is found."""
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
DEFAULT_LANCEDB_DIR = PROJECT_ROOT / "04_VectorDB" / "lancedb"
DEFAULT_TABLE_NAME = "literature_vectors"


@dataclass(frozen=True)
class VectorSearchResult:
    record_id: str
    paper_id: str
    level: str
    score: float | None
    text: str
    title: str | None
    doi: str | None
    year: int | None
    tags: list[str]
    metadata: dict[str, Any]


class VectorStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class LanceDBDryRunPlan:
    path: str
    tables: dict[str, str]
    will_connect: bool = False
    will_create_database: bool = False
    will_create_tables: bool = False
    will_write_records: bool = False


def build_lancedb_dry_run_plan(root: str | Path, config: dict[str, Any]) -> LanceDBDryRunPlan:
    """Return the planned LanceDB target without connecting to or creating LanceDB."""
    root = Path(root)
    lancedb_config = config.get("lancedb") or {}
    raw_path = Path(str(lancedb_config.get("path") or DEFAULT_LANCEDB_DIR))
    db_path = raw_path if raw_path.is_absolute() else root / raw_path
    tables = lancedb_config.get("tables") or {}
    return LanceDBDryRunPlan(
        path=str(db_path),
        tables={str(key): str(value) for key, value in tables.items()},
    )


class LanceVectorStore:
    """LanceDB storage adapter for Scientra Copilot embeddings."""

    def __init__(
        self,
        db_dir: str | Path = DEFAULT_LANCEDB_DIR,
        table_name: str = DEFAULT_TABLE_NAME,
    ) -> None:
        self.db_dir = Path(db_dir)
        self.table_name = table_name
        self._db: Any | None = None
        self._table: Any | None = None

    def connect(self) -> Any:
        try:
            import lancedb
        except Exception as exc:
            raise VectorStoreError(f"lancedb is required for LanceVectorStore: {exc}") from exc

        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.db_dir))
        return self._db

    @property
    def db(self) -> Any:
        return self._db or self.connect()

    def table_exists(self) -> bool:
        try:
            return self.table_name in set(self.db.table_names())
        except Exception:
            return False

    def open_table(self) -> Any:
        if self._table is not None:
            return self._table
        if not self.table_exists():
            raise VectorStoreError(f"LanceDB table not found: {self.table_name}")
        self._table = self.db.open_table(self.table_name)
        return self._table

    def upsert_vectors(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = [normalize_vector_record(record) for record in records if record]
        if not normalized:
            return {"status": "noop", "records": 0}

        if not self.table_exists():
            self._table = self.db.create_table(self.table_name, data=normalized)
            return {"status": "created", "records": len(normalized), "table": self.table_name}

        table = self.open_table()
        groups = sorted(
            {
                (record["paper_id"], record["level"])
                for record in normalized
                if record.get("paper_id") and record.get("level")
            }
        )
        for paper_id, level in groups:
            where = (
                f"paper_id = '{escape_sql_value(paper_id)}' "
                f"AND level = '{escape_sql_value(level)}'"
            )
            try:
                table.delete(where)
            except Exception:
                pass
        table.add(normalized)
        return {"status": "updated", "records": len(normalized), "table": self.table_name}

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        level: str | None = None,
        tags: list[str] | None = None,
        year: int | None = None,
        year_gte: int | None = None,
        year_lte: int | None = None,
        doi: str | None = None,
    ) -> list[VectorSearchResult]:
        table = self.open_table()
        where = build_filter_where(
            level=level,
            tags=tags,
            year=year,
            year_gte=year_gte,
            year_lte=year_lte,
            doi=doi,
        )
        query = table.search(query_vector)
        if where:
            query = query.where(where)
        rows = query.limit(top_k).to_list()
        return [row_to_search_result(row) for row in rows]

    def list_records(
        self,
        level: str | None = None,
        paper_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        table = self.open_table()
        where_parts: list[str] = []
        if level:
            where_parts.append(f"level = '{escape_sql_value(level)}'")
        if paper_id:
            where_parts.append(f"paper_id = '{escape_sql_value(paper_id)}'")
        try:
            if where_parts:
                return table.to_lance().scanner(
                    filter=" AND ".join(where_parts),
                    limit=limit,
                ).to_table().to_pylist()
            return table.to_lance().scanner(limit=limit).to_table().to_pylist()
        except Exception:
            rows = table.to_pandas().to_dict("records")
            if level:
                rows = [row for row in rows if row.get("level") == level]
            if paper_id:
                rows = [row for row in rows if row.get("paper_id") == paper_id]
            return rows[:limit]


def normalize_vector_record(record: dict[str, Any]) -> dict[str, Any]:
    required = ["record_id", "paper_id", "level", "text", "vector"]
    missing: list[str] = []
    for key in required:
        if key not in record or record[key] is None:
            missing.append(key)
        elif isinstance(record[key], str) and not record[key].strip():
            missing.append(key)
    if missing:
        raise VectorStoreError(f"vector record missing required fields: {', '.join(missing)}")

    vector = record["vector"]
    if not isinstance(vector, list) or not vector:
        raise VectorStoreError("vector record must contain a non-empty list vector")

    return {
        "record_id": str(record["record_id"]),
        "paper_id": str(record["paper_id"]),
        "level": str(record["level"]),
        "source_id": str(record.get("source_id") or ""),
        "title": nullable_text(record.get("title")),
        "doi": normalize_doi(record.get("doi")),
        "year": normalize_year(record.get("year")),
        "tags": normalize_string_list(record.get("tags")),
        "text": str(record["text"]),
        "text_hash": str(record.get("text_hash") or ""),
        "vector": [float(value) for value in vector],
        "embedding_model": str(record.get("embedding_model") or ""),
        "embedding_engine_version": str(record.get("embedding_engine_version") or ""),
        "indexed_at": str(record.get("indexed_at") or ""),
        "metadata_json": json.dumps(record.get("metadata") or {}, ensure_ascii=False),
    }


def row_to_search_result(row: dict[str, Any]) -> VectorSearchResult:
    metadata_json = row.get("metadata_json")
    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}

    score = row.get("_distance")
    if score is None:
        score = row.get("_score")
    return VectorSearchResult(
        record_id=str(row.get("record_id") or ""),
        paper_id=str(row.get("paper_id") or ""),
        level=str(row.get("level") or ""),
        score=float(score) if score is not None else None,
        text=str(row.get("text") or ""),
        title=nullable_text(row.get("title")),
        doi=nullable_text(row.get("doi")),
        year=normalize_year(row.get("year")),
        tags=normalize_string_list(row.get("tags")),
        metadata=metadata,
    )


def build_filter_where(
    level: str | None = None,
    tags: list[str] | None = None,
    year: int | None = None,
    year_gte: int | None = None,
    year_lte: int | None = None,
    doi: str | None = None,
) -> str | None:
    parts: list[str] = []
    if level:
        parts.append(f"level = '{escape_sql_value(level)}'")
    if doi:
        parts.append(f"doi = '{escape_sql_value(normalize_doi(doi) or doi)}'")
    if year is not None:
        parts.append(f"year = {int(year)}")
    if year_gte is not None:
        parts.append(f"year >= {int(year_gte)}")
    if year_lte is not None:
        parts.append(f"year <= {int(year_lte)}")
    for tag in normalize_string_list(tags):
        parts.append(f"array_contains(tags, '{escape_sql_value(tag)}')")
    return " AND ".join(parts) if parts else None


def escape_sql_value(value: str) -> str:
    return str(value).replace("'", "''")


def nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_doi(value: Any) -> str | None:
    text = nullable_text(value)
    if not text:
        return None
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.IGNORECASE)
    if not match:
        return text.lower()
    return match.group(0).strip().rstrip(".,;:)])").lower()


def normalize_year(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        return [value.strip()]
    if isinstance(value, list):
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = nullable_text(item)
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result
    return [str(value)]
