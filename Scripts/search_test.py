from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scientra.embedding import BgeM3Embedder, load_embedding_config
except ModuleNotFoundError:
    from scientra.embedding import BgeM3Embedder, load_embedding_config  # type: ignore


SEARCH_TEST_VERSION = "0.1.0"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "05_Index" / "retrieval_validation_report.md"
SUPPORTED_MODES = ["keyword", "vector", "hybrid"]


@dataclass(frozen=True)
class ValidationQuery:
    query_id: str
    query: str
    expected_paper_ids: list[str]
    filter_tags: list[str]
    relevance_terms: list[str]


DEFAULT_VALIDATION_QUERIES = [
    ValidationQuery(
        query_id="tc_receptor",
        query="Visgun receptor Tc toxin Drosophila cells",
        expected_paper_ids=["paper_2247e647bb604df2"],
        filter_tags=["TOXIN:Tc", "MECHANISM:Receptor"],
        relevance_terms=["visgun", "vsg", "tc toxin", "ptc", "receptor"],
    ),
    ValidationQuery(
        query_id="cry3ba_receptor",
        query="Cry3Ba toxin functional receptors cadherin sodium solute symporter Tribolium",
        expected_paper_ids=["paper_e798bc83e17bfa6d"],
        filter_tags=["TOXIN:Cry", "MECHANISM:Receptor"],
        relevance_terms=["cry3ba", "cadherin", "sodium solute symporter", "tribolium", "receptor"],
    ),
    ValidationQuery(
        query_id="vip3_binding",
        query="Vip3Aa binding Spodoptera frugiperda midgut BBMV radiolabeling",
        expected_paper_ids=["paper_9c2009c01d12bb27"],
        filter_tags=["TOXIN:Vip3", "MECHANISM:Binding"],
        relevance_terms=["vip3aa", "spodoptera frugiperda", "midgut", "bbmv", "binding"],
    ),
    ValidationQuery(
        query_id="peritrophic_membrane",
        query="Cry1Ie domain III binding peritrophic membrane Asian corn borer",
        expected_paper_ids=["paper_68e821863bef54be"],
        filter_tags=["TOXIN:Cry", "MECHANISM:PM"],
        relevance_terms=["cry1ie", "domain iii", "peritrophic membrane", "pm", "asian corn borer"],
    ),
    ValidationQuery(
        query_id="crispr_method",
        query="CRISPR Cas9 abdominal-A knockout fall armyworm",
        expected_paper_ids=["paper_22c134a123cc123e"],
        filter_tags=["METHOD:CRISPR"],
        relevance_terms=["crispr", "cas9", "abdominal-a", "fall armyworm", "sfabd-a"],
    ),
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Scientra Copilot LanceDB retrieval without starting the API.",
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "Config" / "embedding.yaml")
    parser.add_argument("--mode", choices=[*SUPPORTED_MODES, "all"], default="all")
    parser.add_argument("--query", default=None, help="Run one ad-hoc query instead of the built-in validation suite.")
    parser.add_argument("--tag", action="append", dest="tags", default=None, help="Require a formal assigned tag.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = args.root.resolve()
    config = load_embedding_config(args.config)
    modes = SUPPORTED_MODES if args.mode == "all" else [args.mode]

    engine = RetrievalValidator(root=root, config=config)
    started_at = time.perf_counter()
    if args.query:
        query = ValidationQuery(
            query_id="adhoc",
            query=args.query,
            expected_paper_ids=[],
            filter_tags=args.tags or [],
            relevance_terms=query_terms(args.query),
        )
        payload = {
            "status": "adhoc",
            "queries": [
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "filter_tags": query.filter_tags,
                    "modes": {
                        mode: engine.search(mode=mode, query=query, top_k=args.top_k)
                        for mode in modes
                    },
                }
            ],
        }
    else:
        payload = engine.run_validation(modes=modes, top_k=args.top_k)

    payload["search_test_version"] = SEARCH_TEST_VERSION
    payload["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)
    payload["lancedb_path"] = str(engine.db_path)
    payload["report_path"] = str(args.report)
    write_validation_report(args.report, payload)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Scientra Copilot Retrieval Validation")
        print(f"mode: {args.mode}")
        print(f"lancedb_path: {engine.db_path}")
        if payload.get("status") == "validation":
            print(f"queries: {payload['query_count']}")
            for mode, metrics in payload["aggregate_metrics"].items():
                print(
                    f"{mode}: P@5={metrics['precision_at_5']:.3f}, "
                    f"P@10={metrics['precision_at_10']:.3f}, "
                    f"tag_accuracy={metrics['tag_filtering_accuracy']:.3f}, "
                    f"chunk_relevance={metrics['chunk_relevance']:.3f}"
                )
        print(f"report_path: {args.report}")
    return 0


class RetrievalValidator:
    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self.root = root
        self.config = config
        self.db_path = resolve_lancedb_path(root, config)
        self.table_names = config.get("lancedb", {}).get("tables") or {}
        self.embedder: BgeM3Embedder | None = None
        self._rows: list[dict[str, Any]] | None = None
        self._db: Any | None = None

    @property
    def db(self) -> Any:
        if self._db is None:
            import lancedb

            self._db = lancedb.connect(str(self.db_path))
        return self._db

    @property
    def rows(self) -> list[dict[str, Any]]:
        if self._rows is None:
            self._rows = self.load_rows()
        return self._rows

    def load_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for logical_name, table_name in self.table_names.items():
            table = self.db.open_table(str(table_name))
            for row in table.to_arrow().to_pylist():
                rows.append(normalize_row(row, str(table_name), str(logical_name)))
        return rows

    def get_embedder(self) -> BgeM3Embedder:
        if self.embedder is None:
            os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
            os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
            self.embedder = BgeM3Embedder(
                model_name=str(self.config.get("embedding_model") or "BAAI/bge-m3"),
                device=str(self.config.get("device") or "auto"),
                normalize_embeddings=True,
            )
            self.embedder.load()
        return self.embedder

    def run_validation(self, modes: list[str], top_k: int) -> dict[str, Any]:
        query_reports = []
        for query in DEFAULT_VALIDATION_QUERIES:
            mode_reports = {}
            for mode in modes:
                results = self.search(mode=mode, query=query, top_k=top_k)
                mode_reports[mode] = {
                    "results": results,
                    "metrics": evaluate_results(results, query),
                }
            query_reports.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "expected_paper_ids": query.expected_paper_ids,
                    "filter_tags": query.filter_tags,
                    "modes": mode_reports,
                }
            )
        return {
            "status": "validation",
            "query_count": len(DEFAULT_VALIDATION_QUERIES),
            "table_counts": self.table_counts(),
            "queries": query_reports,
            "aggregate_metrics": aggregate_metrics(query_reports, modes),
        }

    def table_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _logical_name, table_name in self.table_names.items():
            table = self.db.open_table(str(table_name))
            counts[str(table_name)] = len(table.to_arrow())
        return counts

    def search(self, mode: str, query: ValidationQuery, top_k: int) -> list[dict[str, Any]]:
        if mode == "keyword":
            return self.keyword_search(query=query, top_k=top_k)
        if mode == "vector":
            return self.vector_search(query=query, top_k=top_k)
        if mode == "hybrid":
            return self.hybrid_search(query=query, top_k=top_k)
        raise ValueError(f"unsupported mode: {mode}")

    def keyword_search(self, query: ValidationQuery, top_k: int) -> list[dict[str, Any]]:
        terms = query_terms(query.query)
        candidates = [row for row in self.rows if row_matches_tags(row, query.filter_tags)]
        scored: list[dict[str, Any]] = []
        raw_scores = [keyword_score(row, terms) for row in candidates]
        max_score = max(raw_scores) if raw_scores else 0.0
        for row, raw_score in zip(candidates, raw_scores):
            if raw_score <= 0:
                continue
            score = raw_score / max_score if max_score else 0.0
            scored.append(format_result(row, score=score, distance=None, query=query, mode="keyword"))
        scored.sort(key=lambda item: item["similarity_score"], reverse=True)
        return scored[:top_k]

    def vector_search(self, query: ValidationQuery, top_k: int) -> list[dict[str, Any]]:
        vector = self.get_embedder().encode([query.query], batch_size=1)[0]
        candidates: list[dict[str, Any]] = []
        for logical_name, table_name in self.table_names.items():
            table = self.db.open_table(str(table_name))
            limit = max(top_k * 20, 100)
            for row in table.search(vector).limit(limit).to_list():
                normalized = normalize_row(row, str(table_name), str(logical_name))
                if row_matches_tags(normalized, query.filter_tags):
                    distance = normalized.get("distance")
                    score = distance_to_similarity(distance)
                    candidates.append(
                        format_result(
                            normalized,
                            score=score,
                            distance=distance,
                            query=query,
                            mode="vector",
                        )
                    )
        candidates.sort(key=lambda item: item["similarity_score"], reverse=True)
        return dedupe_results(candidates)[:top_k]

    def hybrid_search(self, query: ValidationQuery, top_k: int) -> list[dict[str, Any]]:
        vector_results = self.vector_search(query=query, top_k=max(top_k * 5, 50))
        keyword_results = self.keyword_search(query=query, top_k=max(top_k * 5, 50))
        merged: dict[str, dict[str, Any]] = {}
        for item in vector_results:
            merged.setdefault(item["record_id"], dict(item))
            merged[item["record_id"]]["vector_component"] = item["similarity_score"]
        for item in keyword_results:
            merged.setdefault(item["record_id"], dict(item))
            merged[item["record_id"]]["keyword_component"] = item["similarity_score"]
        for item in merged.values():
            vector_component = float(item.get("vector_component") or 0.0)
            keyword_component = float(item.get("keyword_component") or 0.0)
            item["mode"] = "hybrid"
            item["similarity_score"] = round(0.65 * vector_component + 0.35 * keyword_component, 6)
        values = list(merged.values())
        values.sort(key=lambda item: item["similarity_score"], reverse=True)
        return values[:top_k]


def normalize_row(row: dict[str, Any], table_name: str, logical_name: str) -> dict[str, Any]:
    metadata = parse_metadata_json(row.get("metadata_json"))
    return {
        "record_id": str(row.get("record_id") or ""),
        "paper_id": str(row.get("paper_id") or ""),
        "level": str(row.get("level") or logical_name),
        "table_name": table_name,
        "source_id": str(row.get("source_id") or ""),
        "title": str(row.get("title") or ""),
        "tags": normalize_tags(row.get("tags")),
        "text": str(row.get("text") or ""),
        "distance": row.get("_distance", row.get("_score")),
        "metadata": metadata,
        "chunk_id": str(metadata.get("chunk_id") or row.get("source_id") or ""),
        "chunk_index": metadata.get("chunk_index"),
        "source_section": metadata.get("source_section"),
    }


def parse_metadata_json(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return {}


def normalize_tags(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def row_matches_tags(row: dict[str, Any], filter_tags: list[str]) -> bool:
    if not filter_tags:
        return True
    row_tags = set(row.get("tags") or [])
    return all(tag in row_tags for tag in filter_tags)


def keyword_score(row: dict[str, Any], terms: list[str]) -> float:
    text = normalize_for_match(row.get("text") or "")
    title = normalize_for_match(row.get("title") or "")
    tags = normalize_for_match(" ".join(row.get("tags") or []))
    score = 0.0
    for term in terms:
        if not term:
            continue
        term_lc = normalize_for_match(term)
        score += text.count(term_lc)
        score += title.count(term_lc) * 3
        score += tags.count(term_lc) * 2
    if row.get("level") == "chunk":
        score *= 1.05
    return score


def query_terms(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.-]*", query.casefold())
    terms = [word for word in words if len(word) > 1 and word not in {"the", "and", "with", "for"}]
    phrases = []
    if len(terms) >= 2:
        phrases.extend(" ".join(terms[index : index + 2]) for index in range(len(terms) - 1))
    return unique_preserve_order([*phrases, *terms])


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).casefold())


def distance_to_similarity(distance: Any) -> float:
    if distance is None:
        return 0.0
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(value):
        return 0.0
    if value < 0:
        return max(0.0, min(1.0, value))
    return 1.0 / (1.0 + value)


def format_result(
    row: dict[str, Any],
    score: float,
    distance: Any,
    query: ValidationQuery,
    mode: str,
) -> dict[str, Any]:
    matched_tags = [
        tag for tag in row.get("tags", []) if tag in set(query.filter_tags)
    ]
    if not matched_tags:
        matched_tags = [
            tag for tag in row.get("tags", []) if tag.split(":", 1)[-1].casefold() in normalize_for_match(query.query)
        ]
    return {
        "rank": 0,
        "mode": mode,
        "similarity_score": round(float(score), 6),
        "distance": round(float(distance), 6) if isinstance(distance, (int, float)) else None,
        "paper_id": row.get("paper_id"),
        "chunk_id": row.get("chunk_id") if row.get("level") == "chunk" else "",
        "source_id": row.get("source_id"),
        "level": row.get("level"),
        "table_name": row.get("table_name"),
        "matched_tags": matched_tags,
        "all_tags": row.get("tags", []),
        "title": row.get("title"),
        "source_section": row.get("source_section"),
        "text_preview": preview_text(row.get("text") or ""),
        "record_id": row.get("record_id"),
    }


def dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    values: list[dict[str, Any]] = []
    for item in results:
        key = str(item.get("record_id") or "")
        if key in seen:
            continue
        seen.add(key)
        values.append(item)
    for index, item in enumerate(values, start=1):
        item["rank"] = index
    return values


def evaluate_results(results: list[dict[str, Any]], query: ValidationQuery) -> dict[str, float]:
    ranked = dedupe_results([dict(item) for item in results])
    expected = set(query.expected_paper_ids)
    p5 = precision_at_k(ranked, expected, 5)
    p10 = precision_at_k(ranked, expected, 10)
    tag_accuracy = tag_filtering_accuracy(ranked[:10], query.filter_tags)
    chunk_relevance = chunk_relevance_score(ranked[:10], query)
    return {
        "precision_at_5": p5,
        "precision_at_10": p10,
        "tag_filtering_accuracy": tag_accuracy,
        "chunk_relevance": chunk_relevance,
    }


def precision_at_k(results: list[dict[str, Any]], expected: set[str], k: int) -> float:
    if not expected or k <= 0:
        return 0.0
    top = results[:k]
    relevant = sum(1 for item in top if item.get("paper_id") in expected)
    return relevant / k


def tag_filtering_accuracy(results: list[dict[str, Any]], filter_tags: list[str]) -> float:
    if not filter_tags:
        return 1.0
    if not results:
        return 0.0
    passed = 0
    for item in results:
        tags = set(item.get("all_tags") or [])
        if all(tag in tags for tag in filter_tags):
            passed += 1
    return passed / len(results)


def chunk_relevance_score(results: list[dict[str, Any]], query: ValidationQuery) -> float:
    chunks = [item for item in results if item.get("level") == "chunk"]
    if not chunks:
        return 0.0
    expected = set(query.expected_paper_ids)
    relevant = 0
    for item in chunks:
        text = normalize_for_match(item.get("text_preview") or "")
        term_hit = any(normalize_for_match(term) in text for term in query.relevance_terms)
        paper_hit = item.get("paper_id") in expected
        if term_hit and paper_hit:
            relevant += 1
    return relevant / len(chunks)


def aggregate_metrics(query_reports: list[dict[str, Any]], modes: list[str]) -> dict[str, dict[str, float]]:
    aggregates: dict[str, dict[str, float]] = {}
    for mode in modes:
        metrics = [
            query_report["modes"][mode]["metrics"]
            for query_report in query_reports
            if mode in query_report["modes"]
        ]
        if not metrics:
            continue
        aggregates[mode] = {
            "precision_at_5": average(item["precision_at_5"] for item in metrics),
            "precision_at_10": average(item["precision_at_10"] for item in metrics),
            "tag_filtering_accuracy": average(item["tag_filtering_accuracy"] for item in metrics),
            "chunk_relevance": average(item["chunk_relevance"] for item in metrics),
        }
    return aggregates


def average(values: Any) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def write_validation_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Retrieval Validation Report",
        "",
        f"- search_test_version: {payload.get('search_test_version', SEARCH_TEST_VERSION)}",
        f"- LanceDB path: {payload.get('lancedb_path')}",
        f"- elapsed_seconds: {payload.get('elapsed_seconds')}",
        "- API developed: false",
        "",
    ]
    if payload.get("table_counts"):
        lines.extend(["## Table Counts", ""])
        for table_name, count in payload["table_counts"].items():
            lines.append(f"- {table_name}: {count}")
        lines.append("")

    if payload.get("aggregate_metrics"):
        lines.extend(["## Aggregate Metrics", ""])
        for mode, metrics in payload["aggregate_metrics"].items():
            lines.extend(
                [
                    f"### {mode}",
                    "",
                    f"- Precision@5: {metrics['precision_at_5']:.3f}",
                    f"- Precision@10: {metrics['precision_at_10']:.3f}",
                    f"- Tag Filtering Accuracy: {metrics['tag_filtering_accuracy']:.3f}",
                    f"- Chunk Relevance: {metrics['chunk_relevance']:.3f}",
                    "",
                ]
            )

    for query_report in payload.get("queries", []):
        lines.extend(
            [
                f"## Query: {query_report['query_id']}",
                "",
                f"- Text: {query_report['query']}",
                f"- Expected Paper ID: {', '.join(query_report.get('expected_paper_ids') or []) or 'N/A'}",
                f"- Filter Tags: {', '.join(query_report.get('filter_tags') or []) or 'None'}",
                "",
            ]
        )
        for mode, mode_payload in query_report["modes"].items():
            if isinstance(mode_payload, list):
                results = mode_payload
                metrics = None
            else:
                results = mode_payload.get("results", [])
                metrics = mode_payload.get("metrics")
            lines.extend([f"### {mode} Top10", ""])
            if metrics:
                lines.extend(
                    [
                        f"- Precision@5: {metrics['precision_at_5']:.3f}",
                        f"- Precision@10: {metrics['precision_at_10']:.3f}",
                        f"- Tag Filtering Accuracy: {metrics['tag_filtering_accuracy']:.3f}",
                        f"- Chunk Relevance: {metrics['chunk_relevance']:.3f}",
                        "",
                    ]
                )
            lines.append("| Rank | Similarity Score | Paper ID | Chunk ID | Level | Matched Tags | Preview |")
            lines.append("|---:|---:|---|---|---|---|---|")
            for index, item in enumerate(results[:10], start=1):
                chunk_id = item.get("chunk_id") or item.get("source_id") or ""
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(index),
                            f"{float(item.get('similarity_score') or 0.0):.6f}",
                            escape_md(str(item.get("paper_id") or "")),
                            escape_md(str(chunk_id)),
                            escape_md(str(item.get("level") or "")),
                            escape_md(", ".join(item.get("matched_tags") or [])),
                            escape_md(str(item.get("text_preview") or "")),
                        ]
                    )
                    + " |"
                )
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def resolve_lancedb_path(root: Path, config: dict[str, Any]) -> Path:
    raw_path = Path(str(config.get("lancedb", {}).get("path") or "04_VectorDB/lancedb"))
    return raw_path if raw_path.is_absolute() else root / raw_path


def preview_text(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def escape_md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
