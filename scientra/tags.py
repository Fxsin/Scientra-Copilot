from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


TAG_ENGINE_VERSION = "0.2.0"
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_ONTOLOGY_PATH = PROJECT_ROOT / "Config" / "tag_ontology.yaml"
DEFAULT_DICTIONARY_PATH = PROJECT_ROOT / "Config" / "tag_dictionary.yaml"
DEFAULT_TAG_OUTPUT_DIR = PROJECT_ROOT / "05_Index" / "tags"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "07_Workflows" / "reports"
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "02_Metadata" / "scientra.db"
DEFAULT_LANCEDB_DIR = PROJECT_ROOT / "04_VectorDB"

SOURCE_PRIORITY = [
    "title",
    "abstract",
    "summary",
    "summary.md",
    "raw_text",
    "chunks",
]

SECTION_WEIGHTS = {
    "title": 3.0,
    "abstract": 2.5,
    "summary": 2.5,
    "results": 2.0,
    "discussion": 2.0,
    "introduction": 1.0,
    "methods": 0.5,
    "references": 0.0,
    "raw_text": 1.0,
    "chunks": 0.75,
    "unknown": 1.0,
}

SYSTEM_METADATA_KEYS = {
    "version",
    "schema_version",
    "tag_schema_version",
    "dictionary_version",
    "tag_dictionary_version",
    "description",
    "defaults",
    "categories",
    "tags",
    "ontology",
    "dictionary",
}


@dataclass(frozen=True)
class PaperInput:
    key: str
    paper_id: str
    text_sources: dict[str, str]
    metadata: dict[str, Any]
    source_files: dict[str, str]


@dataclass(frozen=True)
class RetagOptions:
    root: Path = PROJECT_ROOT
    ontology_path: Path = DEFAULT_ONTOLOGY_PATH
    dictionary_path: Path = DEFAULT_DICTIONARY_PATH
    output_dir: Path = DEFAULT_TAG_OUTPUT_DIR
    report_dir: Path = DEFAULT_REPORT_DIR
    changed_only: bool = False
    category: str | None = None
    tag: str | None = None
    update_sqlite: bool = True
    update_lancedb: bool = True
    sqlite_path: Path | None = DEFAULT_SQLITE_PATH
    lancedb_dir: Path | None = DEFAULT_LANCEDB_DIR


def load_ontology(path: str | Path = DEFAULT_ONTOLOGY_PATH) -> dict[str, Any]:
    """Load and normalize the tag ontology from YAML."""
    payload = read_yaml(path)
    categories = payload.get("categories")
    if categories is None:
        categories = {
            key: value
            for key, value in payload.items()
            if key not in SYSTEM_METADATA_KEYS and isinstance(value, list)
        }

    ontology = {
        "schema_version": str(
            payload.get("schema_version")
            or payload.get("tag_schema_version")
            or payload.get("version")
            or "unversioned"
        ),
        "description": payload.get("description"),
        "categories": {
            str(category): [str(tag) for tag in tags]
            for category, tags in (categories or {}).items()
        },
        "_config_hash": file_sha256(Path(path)),
    }
    validate_ontology(ontology)
    return ontology


def load_dictionary(path: str | Path = DEFAULT_DICTIONARY_PATH) -> dict[str, Any]:
    """Load and normalize the tag dictionary from YAML."""
    payload = read_yaml(path)
    raw_tags = payload.get("tags") or payload.get("dictionary")
    if raw_tags is None:
        raw_tags = {
            key: value
            for key, value in payload.items()
            if key not in SYSTEM_METADATA_KEYS and isinstance(value, dict)
        }

    defaults = payload.get("defaults") or {}
    default_weight = as_float(defaults.get("weight"), 1.0)
    default_min_score = as_float(defaults.get("min_score"), 1.0)

    tags: dict[str, dict[str, Any]] = {}
    for tag_name, spec in (raw_tags or {}).items():
        spec = spec or {}
        tags[str(tag_name)] = {
            "synonyms": normalize_string_list(spec.get("synonyms")),
            "include_patterns": normalize_string_list(spec.get("include_patterns")),
            "exclude_patterns": normalize_string_list(spec.get("exclude_patterns")),
            "weight": as_float(spec.get("weight"), default_weight),
            "min_score": as_float(spec.get("min_score"), default_min_score),
            "assignment_requires_sections": normalize_section_list(
                spec.get("assignment_requires_sections")
            ),
            "candidate_only_sections": normalize_section_list(
                spec.get("candidate_only_sections")
            ),
        }

    dictionary = {
        "dictionary_version": str(
            payload.get("dictionary_version")
            or payload.get("tag_dictionary_version")
            or payload.get("version")
            or "unversioned"
        ),
        "description": payload.get("description"),
        "defaults": {
            "weight": default_weight,
            "min_score": default_min_score,
        },
        "tags": tags,
        "_config_hash": file_sha256(Path(path)),
    }
    validate_dictionary(dictionary)
    return dictionary


def validate_ontology(ontology: dict[str, Any]) -> bool:
    errors: list[str] = []
    categories = ontology.get("categories")
    if not isinstance(categories, dict) or not categories:
        errors.append("ontology.categories must be a non-empty mapping")
    else:
        for category, tags in categories.items():
            if not isinstance(category, str) or not category.strip():
                errors.append("ontology category names must be non-empty strings")
            if not isinstance(tags, list) or not tags:
                errors.append(f"ontology category {category!r} must contain at least one tag")
                continue
            seen: set[str] = set()
            for tag in tags:
                if not isinstance(tag, str) or not tag.strip():
                    errors.append(f"ontology category {category!r} contains an invalid tag")
                    continue
                if tag in seen:
                    errors.append(f"ontology category {category!r} repeats tag {tag!r}")
                seen.add(tag)

    if not ontology.get("schema_version"):
        errors.append("ontology.schema_version is required")

    if errors:
        raise ValueError("; ".join(errors))
    return True


def validate_dictionary(
    dictionary: dict[str, Any],
    ontology: dict[str, Any] | None = None,
) -> bool:
    errors: list[str] = []
    tags = dictionary.get("tags")
    if not isinstance(tags, dict) or not tags:
        errors.append("dictionary.tags must be a non-empty mapping")
    else:
        for tag_name, spec in tags.items():
            if not isinstance(tag_name, str) or not tag_name.strip():
                errors.append("dictionary tag names must be non-empty strings")
            if not isinstance(spec, dict):
                errors.append(f"dictionary entry {tag_name!r} must be a mapping")
                continue
            for field in ["synonyms", "include_patterns", "exclude_patterns"]:
                if not isinstance(spec.get(field), list):
                    errors.append(f"dictionary entry {tag_name!r}.{field} must be a list")
            for optional_field in ["assignment_requires_sections", "candidate_only_sections"]:
                if optional_field in spec and not isinstance(spec.get(optional_field), list):
                    errors.append(f"dictionary entry {tag_name!r}.{optional_field} must be a list")
            for pattern_field in ["include_patterns", "exclude_patterns"]:
                for pattern in spec.get(pattern_field, []):
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        errors.append(
                            f"dictionary entry {tag_name!r}.{pattern_field} has invalid regex {pattern!r}: {exc}"
                        )
            if as_float(spec.get("weight"), None) is None:
                errors.append(f"dictionary entry {tag_name!r}.weight must be numeric")
            if as_float(spec.get("min_score"), None) is None:
                errors.append(f"dictionary entry {tag_name!r}.min_score must be numeric")

    if not dictionary.get("dictionary_version"):
        errors.append("dictionary.dictionary_version is required")

    if ontology is not None:
        allowed_tags = ontology_tags(ontology)
        dictionary_tags = set(tags or {})
        missing = sorted(allowed_tags - dictionary_tags)
        unknown = sorted(dictionary_tags - allowed_tags)
        if missing:
            errors.append("dictionary is missing ontology tags: " + ", ".join(missing))
        if unknown:
            errors.append("dictionary contains tags outside ontology: " + ", ".join(unknown))

    if errors:
        raise ValueError("; ".join(errors))
    return True


def assign_tags(
    text_sources: dict[str, str],
    ontology: dict[str, Any],
    dictionary: dict[str, Any],
    category: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Assign configured tags from configured rules only."""
    validate_ontology(ontology)
    validate_dictionary(dictionary, ontology)

    assigned_tags: dict[str, list[str]] = {}
    candidate_tags: dict[str, list[str]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    target_tags = {tag} if tag else None

    for category_name, category_tags in ontology.get("categories", {}).items():
        if category is not None and category_name != category:
            continue
        assigned_tags.setdefault(category_name, [])
        candidate_tags.setdefault(category_name, [])

        for tag_name in category_tags:
            if target_tags is not None and tag_name not in target_tags:
                continue
            spec = dictionary["tags"][tag_name]
            tag_evidence = score_tag(tag_name, spec, text_sources)
            score = tag_evidence["score"]
            if score <= 0:
                continue

            min_score = as_float(spec.get("min_score"), 1.0) or 1.0
            assignable_score = tag_evidence.get("assignable_score", 0.0)
            confidence = confidence_for_score(score, min_score, assignable_score)
            assigned = score >= min_score and assignable_score >= min_score and confidence in {
                "high",
                "medium",
            }
            evidence[tag_name] = {
                "category": category_name,
                "matched_terms": tag_evidence["matched_terms"],
                "source": tag_evidence["source"],
                "source_section": tag_evidence["source_section"],
                "score": round(score, 3),
                "assignable_score": round(assignable_score, 3),
                "confidence": confidence,
                "reason": tag_evidence["reason"],
            }
            if assigned:
                assigned_tags[category_name].append(tag_name)
            else:
                candidate_tags[category_name].append(tag_name)

    return {
        "assigned_tags": {
            category_name: tags
            for category_name, tags in assigned_tags.items()
            if tags or category is not None
        },
        "candidate_tags": {
            category_name: tags
            for category_name, tags in candidate_tags.items()
            if tags or category is not None
        },
        "evidence": evidence,
    }


def assign_tags_for_paper(
    paper: PaperInput | dict[str, Any],
    ontology: dict[str, Any],
    dictionary: dict[str, Any],
    category: str | None = None,
    tag: str | None = None,
    previous_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paper_input = coerce_paper_input(paper)
    partial = assign_tags(
        paper_input.text_sources,
        ontology,
        dictionary,
        category=category,
        tag=tag,
    )
    result = {
        "paper_id": paper_input.paper_id,
        "paper_key": paper_input.key,
        "tag_schema_version": ontology["schema_version"],
        "tag_dictionary_version": dictionary["dictionary_version"],
        "tag_engine_version": TAG_ENGINE_VERSION,
        "tag_schema_hash": ontology["_config_hash"],
        "tag_dictionary_hash": dictionary["_config_hash"],
        "source_hash": hash_text_sources(paper_input.text_sources),
        "llm_used": False,
        "summary_regenerated": False,
        "embedding_regenerated": False,
        "assigned_tags": partial["assigned_tags"],
        "candidate_tags": partial["candidate_tags"],
        "evidence": partial["evidence"],
        "source_files": paper_input.source_files,
        "generated_at": utc_now(),
    }
    return merge_filtered_result(result, previous_result, ontology, category, tag)


def retag_all(
    root: str | Path = PROJECT_ROOT,
    changed_only: bool = False,
    ontology_path: str | Path | None = None,
    dictionary_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    report_dir: str | Path | None = None,
    update_sqlite: bool = True,
    update_lancedb: bool = True,
    sqlite_path: str | Path | None = None,
    lancedb_dir: str | Path | None = None,
) -> dict[str, Any]:
    options = build_options(
        root=root,
        changed_only=changed_only,
        ontology_path=ontology_path,
        dictionary_path=dictionary_path,
        output_dir=output_dir,
        report_dir=report_dir,
        update_sqlite=update_sqlite,
        update_lancedb=update_lancedb,
        sqlite_path=sqlite_path,
        lancedb_dir=lancedb_dir,
    )
    return run_retag(options)


def retag_by_category(
    category: str,
    root: str | Path = PROJECT_ROOT,
    changed_only: bool = False,
    ontology_path: str | Path | None = None,
    dictionary_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    report_dir: str | Path | None = None,
    update_sqlite: bool = True,
    update_lancedb: bool = True,
    sqlite_path: str | Path | None = None,
    lancedb_dir: str | Path | None = None,
) -> dict[str, Any]:
    options = build_options(
        root=root,
        changed_only=changed_only,
        category=category,
        ontology_path=ontology_path,
        dictionary_path=dictionary_path,
        output_dir=output_dir,
        report_dir=report_dir,
        update_sqlite=update_sqlite,
        update_lancedb=update_lancedb,
        sqlite_path=sqlite_path,
        lancedb_dir=lancedb_dir,
    )
    return run_retag(options)


def retag_by_tag(
    tag: str,
    root: str | Path = PROJECT_ROOT,
    changed_only: bool = False,
    ontology_path: str | Path | None = None,
    dictionary_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    report_dir: str | Path | None = None,
    update_sqlite: bool = True,
    update_lancedb: bool = True,
    sqlite_path: str | Path | None = None,
    lancedb_dir: str | Path | None = None,
) -> dict[str, Any]:
    options = build_options(
        root=root,
        changed_only=changed_only,
        tag=tag,
        ontology_path=ontology_path,
        dictionary_path=dictionary_path,
        output_dir=output_dir,
        report_dir=report_dir,
        update_sqlite=update_sqlite,
        update_lancedb=update_lancedb,
        sqlite_path=sqlite_path,
        lancedb_dir=lancedb_dir,
    )
    return run_retag(options)


def run_retag(options: RetagOptions) -> dict[str, Any]:
    ontology = load_ontology(options.ontology_path)
    dictionary = load_dictionary(options.dictionary_path)
    validate_dictionary(dictionary, ontology)
    validate_selector(ontology, options.category, options.tag)

    papers = discover_papers(options.root)
    results: list[dict[str, Any]] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []

    options.output_dir.mkdir(parents=True, exist_ok=True)

    for paper in papers:
        try:
            previous = read_existing_tags(options.output_dir, paper.paper_id)
            if options.changed_only and previous and not retag_needed(
                previous,
                ontology,
                dictionary,
                paper,
            ):
                skipped.append(paper.paper_id)
                continue

            next_result = assign_tags_for_paper(
                paper,
                ontology,
                dictionary,
                category=options.category,
                tag=options.tag,
                previous_result=previous,
            )
            next_result["changes"] = diff_tag_results(previous, next_result)
            write_tags_yaml(options.output_dir, next_result)
            results.append(next_result)
        except Exception as exc:
            errors.append(
                {
                    "paper_id": paper.paper_id,
                    "paper_key": paper.key,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    sqlite_status = (
        update_sqlite_tags(results, options.sqlite_path)
        if options.update_sqlite
        else {"status": "disabled"}
    )
    lancedb_status = (
        update_lancedb_metadata(results, options.lancedb_dir)
        if options.update_lancedb
        else {"status": "disabled"}
    )

    report_path = export_tag_report(
        results=results,
        ontology=ontology,
        dictionary=dictionary,
        report_dir=options.report_dir,
        total_papers=len(papers),
        skipped_paper_ids=skipped,
        errors=errors,
        sqlite_status=sqlite_status,
        lancedb_status=lancedb_status,
        selector={"category": options.category, "tag": options.tag},
    )

    return {
        "tag_schema_version": ontology["schema_version"],
        "tag_dictionary_version": dictionary["dictionary_version"],
        "tag_engine_version": TAG_ENGINE_VERSION,
        "total_papers": len(papers),
        "processed_papers": len(results),
        "skipped_papers": len(skipped),
        "error_papers": len(errors),
        "report_path": str(report_path),
        "sqlite_status": sqlite_status,
        "lancedb_status": lancedb_status,
        "errors": errors,
    }


def export_tag_report(
    results: list[dict[str, Any]],
    ontology: dict[str, Any],
    dictionary: dict[str, Any],
    report_dir: str | Path = DEFAULT_REPORT_DIR,
    total_papers: int | None = None,
    skipped_paper_ids: list[str] | None = None,
    errors: list[dict[str, str]] | None = None,
    sqlite_status: dict[str, Any] | None = None,
    lancedb_status: dict[str, Any] | None = None,
    selector: dict[str, str | None] | None = None,
) -> Path:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "retag_report.md"
    skipped_paper_ids = skipped_paper_ids or []
    errors = errors or []
    selector = selector or {}

    tag_counts = count_tags(results)
    newly_hit = collect_new_hits(results)
    change_stats = summarize_changes(results)
    unmatched = [
        result["paper_id"]
        for result in results
        if not flatten_assigned_tags(result.get("assigned_tags", {}))
    ]

    lines = [
        "# Retag Report",
        "",
        f"Generated at: {utc_now()}",
        f"Ontology version: {ontology['schema_version']}",
        f"Dictionary version: {dictionary['dictionary_version']}",
        f"Tag engine version: {TAG_ENGINE_VERSION}",
        f"Selector category: {selector.get('category') or 'ALL'}",
        f"Selector tag: {selector.get('tag') or 'ALL'}",
        f"Processed documents: {len(results)}",
        f"Total discovered documents: {total_papers if total_papers is not None else len(results)}",
        f"Skipped documents: {len(skipped_paper_ids)}",
        f"Error documents: {len(errors)}",
        "",
        "## Tag Hit Counts",
        "",
    ]
    if tag_counts:
        for tag_name, count in sorted(tag_counts.items()):
            lines.append(f"- {tag_name}: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Newly Hit Tags", ""])
    if newly_hit:
        for tag_name, paper_ids in sorted(newly_hit.items()):
            lines.append(f"- {tag_name}: {', '.join(sorted(paper_ids))}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Tag Change Statistics",
            "",
            f"- Papers changed: {change_stats['papers_changed']}",
            f"- Tags added: {change_stats['tags_added']}",
            f"- Tags removed: {change_stats['tags_removed']}",
            f"- Tags unchanged: {change_stats['tags_unchanged']}",
            "",
            "## Unmatched Documents",
            "",
        ]
    )
    if unmatched:
        for paper_id in unmatched:
            lines.append(f"- {paper_id}")
    else:
        lines.append("- None")

    lines.extend(["", "## Error Documents", ""])
    if errors:
        for error in errors:
            lines.append(f"- {error.get('paper_id')}: {error.get('error')}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Update Status",
            "",
            f"- SQLite: {json.dumps(sqlite_status or {}, ensure_ascii=False)}",
            f"- LanceDB metadata: {json.dumps(lancedb_status or {}, ensure_ascii=False)}",
            "- PDF parsing regenerated: false",
            "- Summary regenerated: false",
            "- Chunking regenerated: false",
            "- Embedding regenerated: false",
            "- LLM used: false",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def update_sqlite_tags(
    tag_results: list[dict[str, Any]],
    sqlite_path: str | Path | None = DEFAULT_SQLITE_PATH,
) -> dict[str, Any]:
    if sqlite_path is None:
        return {"status": "skipped", "reason": "sqlite_path is not configured"}
    sqlite_path = Path(sqlite_path)
    if not sqlite_path.exists():
        return {"status": "skipped", "reason": f"sqlite database not found: {sqlite_path}"}

    with sqlite3.connect(sqlite_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_tags (
                paper_id TEXT NOT NULL,
                category TEXT NOT NULL,
                tag TEXT NOT NULL,
                score REAL,
                matched_terms TEXT,
                sources TEXT,
                tag_schema_version TEXT,
                tag_dictionary_version TEXT,
                tag_engine_version TEXT,
                updated_at TEXT,
                PRIMARY KEY (paper_id, category, tag)
            )
            """
        )
        for result in tag_results:
            paper_id = result["paper_id"]
            connection.execute("DELETE FROM paper_tags WHERE paper_id = ?", (paper_id,))
            for category, tags in result.get("assigned_tags", {}).items():
                for tag_name in tags:
                    evidence = result.get("evidence", {}).get(tag_name, {})
                    connection.execute(
                        """
                        INSERT INTO paper_tags (
                            paper_id, category, tag, score, matched_terms, sources,
                            tag_schema_version, tag_dictionary_version, tag_engine_version, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            paper_id,
                            category,
                            tag_name,
                            evidence.get("score"),
                            json.dumps(evidence.get("matched_terms", []), ensure_ascii=False),
                            json.dumps(evidence.get("source", []), ensure_ascii=False),
                            result.get("tag_schema_version"),
                            result.get("tag_dictionary_version"),
                            result.get("tag_engine_version"),
                            utc_now(),
                        ),
                    )
    return {"status": "updated", "papers": len(tag_results), "sqlite_path": str(sqlite_path)}


def update_lancedb_metadata(
    tag_results: list[dict[str, Any]],
    lancedb_dir: str | Path | None = DEFAULT_LANCEDB_DIR,
    table_name: str = "summary_chunks",
) -> dict[str, Any]:
    if lancedb_dir is None:
        return {"status": "skipped", "reason": "lancedb_dir is not configured"}
    lancedb_dir = Path(lancedb_dir)
    if not lancedb_dir.exists():
        return {"status": "skipped", "reason": f"LanceDB directory not found: {lancedb_dir}"}

    try:
        import lancedb
    except Exception as exc:
        return {"status": "skipped", "reason": f"lancedb import failed: {exc}"}

    try:
        db = lancedb.connect(str(lancedb_dir))
        table_names = set(db.table_names())
        if table_name not in table_names:
            return {"status": "skipped", "reason": f"LanceDB table not found: {table_name}"}
        table = db.open_table(table_name)
        updated = 0
        for result in tag_results:
            flat_tags = sorted(flatten_assigned_tags(result.get("assigned_tags", {})))
            values = {
                "tags": flat_tags,
                "tag_schema_version": result.get("tag_schema_version"),
                "tag_dictionary_version": result.get("tag_dictionary_version"),
                "tag_engine_version": result.get("tag_engine_version"),
            }
            escaped_paper_id = str(result["paper_id"]).replace("'", "''")
            try:
                table.update(where=f"paper_id = '{escaped_paper_id}'", values=values)
                updated += 1
            except Exception:
                continue
        return {"status": "updated", "papers": updated, "lancedb_dir": str(lancedb_dir)}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "lancedb_dir": str(lancedb_dir)}


def score_tag(tag_name: str, spec: dict[str, Any], text_sources: dict[str, str]) -> dict[str, Any]:
    matched_terms: list[str] = []
    matched_sources: list[str] = []
    matched_sections: list[str] = []
    hit_records: list[dict[str, Any]] = []
    score = 0.0
    weight = as_float(spec.get("weight"), 1.0) or 1.0

    for source_name in source_priority_order(text_sources):
        text = text_sources.get(source_name) or ""
        if not text.strip():
            continue
        source_hits = collect_source_hits(tag_name, spec, text, source_name)
        if not source_hits:
            continue
        for hit in source_hits:
            section_role = section_role_for(source_name, hit["source_section"])
            section_weight = SECTION_WEIGHTS.get(section_role, SECTION_WEIGHTS["unknown"])
            contribution = weight * section_weight
            enriched_hit = {
                "term": hit["term"],
                "source": source_name,
                "source_section": hit["source_section"],
                "section_role": section_role,
                "section_weight": section_weight,
                "score_contribution": contribution,
            }
            hit_records.append(enriched_hit)
            score += contribution
            matched_terms.append(enriched_hit["term"])
            matched_sections.append(enriched_hit["source_section"])
            matched_sources.append(source_name)

    assignable_hits = [hit for hit in hit_records if is_assignable_hit(spec, hit)]
    candidate_only_hits = [hit for hit in hit_records if is_candidate_only_hit(spec, hit)]
    assignable_score = sum(float(hit["score_contribution"]) for hit in assignable_hits)
    candidate_only_score = sum(float(hit["score_contribution"]) for hit in candidate_only_hits)

    return {
        "matched_terms": unique_preserve_order(matched_terms),
        "source": unique_preserve_order(matched_sources),
        "source_section": unique_preserve_order(matched_sections),
        "section_role": unique_preserve_order([hit["section_role"] for hit in hit_records]),
        "assignable_section": unique_preserve_order(
            [hit["section_role"] for hit in assignable_hits]
        ),
        "score": score,
        "assignable_score": assignable_score,
        "candidate_only_score": candidate_only_score,
        "hit_records": hit_records,
        "reason": build_tag_reason(spec, score, assignable_score, hit_records),
    }


def collect_source_hits(
    tag_name: str,
    spec: dict[str, Any],
    text: str,
    source_name: str,
) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for synonym in spec.get("synonyms", []):
        for match in find_synonym_matches(synonym, text):
            if hit_has_exclusion(text, match.start(), match.end(), spec.get("exclude_patterns", [])):
                continue
            hits.append(
                {
                    "term": synonym,
                    "source_section": source_section_for_match(source_name, text, match.start()),
                }
            )
    for pattern in spec.get("include_patterns", []):
        try:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                if hit_has_exclusion(text, match.start(), match.end(), spec.get("exclude_patterns", [])):
                    continue
                value = match.group(0).strip()
                hits.append(
                    {
                        "term": value or pattern,
                        "source_section": source_section_for_match(source_name, text, match.start()),
                    }
                )
        except re.error:
            continue
    return unique_hit_records(hits)


def is_assignable_hit(spec: dict[str, Any], hit: dict[str, Any]) -> bool:
    if float(hit.get("score_contribution") or 0.0) <= 0:
        return False
    if is_candidate_only_hit(spec, hit):
        return False
    required_sections = set(spec.get("assignment_requires_sections") or [])
    if required_sections and hit.get("section_role") not in required_sections:
        return False
    return True


def is_candidate_only_hit(spec: dict[str, Any], hit: dict[str, Any]) -> bool:
    section_role = str(hit.get("section_role") or "unknown")
    candidate_only_sections = set(spec.get("candidate_only_sections") or [])
    return section_role in {"methods", "references"} or section_role in candidate_only_sections


def build_tag_reason(
    spec: dict[str, Any],
    score: float,
    assignable_score: float,
    hit_records: list[dict[str, Any]],
) -> str:
    min_score = as_float(spec.get("min_score"), 1.0) or 1.0
    roles = unique_preserve_order([str(hit.get("section_role") or "unknown") for hit in hit_records])
    assignable_roles = unique_preserve_order(
        [
            str(hit.get("section_role") or "unknown")
            for hit in hit_records
            if is_assignable_hit(spec, hit)
        ]
    )
    required_sections = spec.get("assignment_requires_sections") or []
    candidate_only_sections = sorted(
        set(["methods", "references", *list(spec.get("candidate_only_sections") or [])])
    )

    if not hit_records:
        return "no configured dictionary terms were matched"
    if score < min_score:
        return (
            f"candidate only: score {score:.2f} is below min_score {min_score:.2f}; "
            f"matched sections: {', '.join(roles)}"
        )
    if assignable_score < min_score:
        required_text = ", ".join(required_sections) if required_sections else "non-weak sections"
        return (
            f"candidate only: assignable_score {assignable_score:.2f} is below min_score "
            f"{min_score:.2f}; required sections: {required_text}; candidate-only sections: "
            f"{', '.join(candidate_only_sections)}; matched sections: {', '.join(roles)}"
        )
    return (
        f"assigned-ready: assignable_score {assignable_score:.2f} meets min_score "
        f"{min_score:.2f}; assignable sections: {', '.join(assignable_roles)}"
    )


def find_synonym(synonym: str, text: str) -> bool:
    return next(find_synonym_matches(synonym, text), None) is not None


def find_synonym_matches(synonym: str, text: str) -> Any:
    escaped = re.escape(synonym.strip())
    if not escaped:
        return iter(())
    escaped = re.sub(r"\\\s+", r"\\s+", escaped)
    pattern = rf"(?<!\w){escaped}(?!\w)"
    return re.finditer(pattern, text, flags=re.IGNORECASE)


def hit_has_exclusion(
    text: str,
    start: int,
    end: int,
    exclude_patterns: list[str],
    context_chars: int = 80,
) -> bool:
    hit_text = text[start:end]
    context = text[max(0, start - context_chars) : min(len(text), end + context_chars)]
    for pattern in exclude_patterns:
        if re.search(pattern, hit_text, flags=re.IGNORECASE):
            return True
        if re.search(pattern, context, flags=re.IGNORECASE):
            return True
    return False


def confidence_for_score(
    score: float,
    min_score: float,
    assignable_score: float | None = None,
) -> str:
    if assignable_score is None:
        assignable_score = score
    if score < min_score or assignable_score < min_score:
        return "low"
    if assignable_score >= min_score * 2:
        return "high"
    return "medium"


def source_section_for_match(source_name: str, text: str, start: int) -> str:
    if source_name in {"title", "abstract", "summary", "summary.md"}:
        return source_name
    prefix = text[:start]
    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", prefix)
    if headings:
        return f"{source_name}:{headings[-1]}"
    return source_name


def section_role_for(source_name: str, source_section: str) -> str:
    source = source_name.casefold()
    if source == "title":
        return "title"
    if source == "abstract":
        return "abstract"
    if source in {"summary", "summary.md"}:
        return "summary"
    if source == "chunks":
        return "chunks"

    heading = source_section.split(":", 1)[-1]
    heading = re.sub(r"<[^>]+>", " ", heading)
    heading = re.sub(r"\s+", " ", heading).strip().casefold()
    if not heading:
        return "unknown"

    if re.search(r"\b(reference|references|bibliography|literature cited)\b", heading):
        return "references"
    if re.search(r"\b(result|results)\b", heading):
        return "results"
    if re.search(r"\b(discussion|conclusion|conclusions|summary)\b", heading):
        return "discussion"
    if any(
        marker in heading
        for marker in [
            "analysis of binding",
            "binding to pm proteins",
            "homologous competition",
            "heterologous competition",
        ]
    ):
        return "results"
    if any(
        marker in heading
        for marker in [
            "method",
            "methods",
            "material",
            "materials",
            "preparation",
            "purification",
            "expression",
            "cloning",
            "assay",
            "assays",
            "radiolabeling",
            "immunohistochemical",
            "source of",
            "bbmv preparation",
            "rearing",
            "strain",
            "culture",
            "sample",
            "protocol",
        ]
    ):
        return "methods"
    if any(marker in heading for marker in ["introduction", "background", "untitled"]):
        return "introduction"
    if re.fullmatch(r"page\s+\d+", heading):
        return "raw_text"
    return "raw_text"


def unique_hit_records(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    values: list[dict[str, str]] = []
    for hit in hits:
        key = (hit.get("term", ""), hit.get("source_section", ""))
        if key in seen:
            continue
        seen.add(key)
        values.append(hit)
    return values


def discover_papers(root: str | Path = PROJECT_ROOT) -> list[PaperInput]:
    root = Path(root)
    metadata_yaml_dir = root / "02_Metadata" / "yaml"
    metadata_json_dir = root / "02_Metadata" / "papers"
    raw_text_dir = root / "03_Summary" / "raw_text"

    records: dict[str, dict[str, Path | None]] = {}
    if metadata_yaml_dir.exists():
        for path in sorted(metadata_yaml_dir.glob("*.metadata.yaml")):
            key = path.name[: -len(".metadata.yaml")]
            records.setdefault(key, {})["metadata_yaml"] = path
    if metadata_json_dir.exists():
        for path in sorted(metadata_json_dir.glob("*.metadata.json")):
            key = path.name[: -len(".metadata.json")]
            records.setdefault(key, {})["metadata_json"] = path
    if raw_text_dir.exists():
        for path in sorted(raw_text_dir.glob("*.txt")):
            key = path.stem
            records.setdefault(key, {})["raw_text"] = path

    papers: list[PaperInput] = []
    for key, paths in sorted(records.items()):
        metadata = load_paper_metadata(paths.get("metadata_yaml"), paths.get("metadata_json"))
        paper_id = str(metadata.get("paper_id") or key)
        source_files: dict[str, str] = {
            name: str(path)
            for name, path in paths.items()
            if path is not None
        }
        raw_text_path = find_raw_text_path(root, key, paper_id, paths.get("raw_text"), metadata)
        if raw_text_path:
            source_files["raw_text"] = str(raw_text_path)
        summary_path = find_summary_path(root, key, paper_id)
        if summary_path:
            source_files["summary"] = str(summary_path)
        chunk_paths = find_chunk_paths(root, key, paper_id)
        if chunk_paths:
            source_files["chunks"] = ";".join(str(path) for path in chunk_paths)

        text_sources = {
            "title": as_text(metadata.get("title") or metadata.get("metadata", {}).get("title")),
            "abstract": as_text(metadata.get("abstract")),
            "summary": read_text_if_exists(summary_path),
            "raw_text": read_text_if_exists(raw_text_path),
            "chunks": read_chunks(chunk_paths),
        }
        papers.append(
            PaperInput(
                key=key,
                paper_id=paper_id,
                text_sources=text_sources,
                metadata=metadata,
                source_files=source_files,
            )
        )
    return papers


def load_paper_metadata(
    metadata_yaml_path: Path | None,
    metadata_json_path: Path | None,
) -> dict[str, Any]:
    if metadata_yaml_path and metadata_yaml_path.exists():
        return read_yaml(metadata_yaml_path)
    if metadata_json_path and metadata_json_path.exists():
        payload = json.loads(metadata_json_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        return {
            "paper_id": payload.get("paper_id"),
            "title": metadata.get("title"),
            "journal": metadata.get("journal"),
            "year": metadata.get("year"),
            "doi": metadata.get("doi"),
            "authors": metadata.get("authors"),
            "abstract": payload.get("abstract"),
            "metadata": metadata,
            "outputs": payload.get("outputs", {}),
        }
    return {}


def find_raw_text_path(
    root: Path,
    key: str,
    paper_id: str,
    explicit_path: Path | None,
    metadata: dict[str, Any],
) -> Path | None:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(explicit_path)
    output_path = metadata.get("outputs", {}).get("raw_text_path")
    if output_path:
        candidates.append(Path(output_path))
    candidates.extend(
        [
            root / "03_Summary" / "raw_text" / f"{key}.txt",
            root / "03_Summary" / "raw_text" / f"{paper_id}.txt",
        ]
    )
    return first_existing_path(candidates)


def find_summary_path(root: Path, key: str, paper_id: str) -> Path | None:
    candidates = [
        root / "03_Summary" / key / "summary.md",
        root / "03_Summary" / paper_id / "summary.md",
        root / "03_Summary" / "summary" / f"{key}.md",
        root / "03_Summary" / "summary" / f"{paper_id}.md",
        root / "03_Summary" / "summaries" / f"{key}.md",
        root / "03_Summary" / "summaries" / f"{paper_id}.md",
        root / "03_Summary" / f"{key}.summary.md",
        root / "03_Summary" / f"{paper_id}.summary.md",
    ]
    return first_existing_path(candidates)


def find_chunk_paths(root: Path, key: str, paper_id: str) -> list[Path]:
    candidates: list[Path] = []
    for identifier in [key, paper_id]:
        chunk_dir = root / "03_Summary" / "chunks" / identifier
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


def read_chunks(paths: list[Path]) -> str:
    parts: list[str] = []
    for path in paths:
        if path.suffix.lower() == ".json":
            parts.append(read_json_text_payload(path))
        else:
            parts.append(read_text_if_exists(path))
    return "\n\n".join(part for part in parts if part)


def read_json_text_payload(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if isinstance(payload, list):
        return "\n\n".join(as_text(item.get("text") or item.get("content")) for item in payload if isinstance(item, dict))
    if isinstance(payload, dict):
        chunks = payload.get("chunks")
        if isinstance(chunks, list):
            return "\n\n".join(as_text(item.get("text") or item.get("content")) for item in chunks if isinstance(item, dict))
        return as_text(payload.get("text") or payload.get("content"))
    return ""


def merge_filtered_result(
    fresh: dict[str, Any],
    previous: dict[str, Any] | None,
    ontology: dict[str, Any],
    category: str | None,
    tag: str | None,
) -> dict[str, Any]:
    if previous is None or (category is None and tag is None):
        return fresh

    merged = dict(previous)
    for key in [
        "paper_id",
        "paper_key",
        "tag_schema_version",
        "tag_dictionary_version",
        "tag_engine_version",
        "tag_schema_hash",
        "tag_dictionary_hash",
        "source_hash",
        "llm_used",
        "summary_regenerated",
        "embedding_regenerated",
        "source_files",
        "generated_at",
    ]:
        merged[key] = fresh.get(key)

    merged_tags = {
        category_name: list(tags)
        for category_name, tags in (previous.get("assigned_tags") or {}).items()
    }
    merged_candidates = {
        category_name: list(tags)
        for category_name, tags in (previous.get("candidate_tags") or {}).items()
    }
    merged_evidence = dict(previous.get("evidence") or {})

    if category is not None:
        merged_tags[category] = list(fresh.get("assigned_tags", {}).get(category, []))
        merged_candidates[category] = list(fresh.get("candidate_tags", {}).get(category, []))
        for tag_name in ontology.get("categories", {}).get(category, []):
            merged_evidence.pop(tag_name, None)
        merged_evidence.update(fresh.get("evidence", {}))
    elif tag is not None:
        tag_category = category_for_tag(ontology, tag)
        if tag_category is not None:
            existing = [value for value in merged_tags.get(tag_category, []) if value != tag]
            fresh_hits = fresh.get("assigned_tags", {}).get(tag_category, [])
            if tag in fresh_hits:
                existing.append(tag)
            merged_tags[tag_category] = unique_preserve_order(existing)
            existing_candidates = [
                value for value in merged_candidates.get(tag_category, []) if value != tag
            ]
            fresh_candidate_hits = fresh.get("candidate_tags", {}).get(tag_category, [])
            if tag in fresh_candidate_hits:
                existing_candidates.append(tag)
            merged_candidates[tag_category] = unique_preserve_order(existing_candidates)
        merged_evidence.pop(tag, None)
        if tag in fresh.get("evidence", {}):
            merged_evidence[tag] = fresh["evidence"][tag]

    merged["assigned_tags"] = {key: value for key, value in merged_tags.items() if value}
    merged["candidate_tags"] = {
        key: value for key, value in merged_candidates.items() if value
    }
    merged["evidence"] = merged_evidence
    return merged


def retag_needed(
    previous: dict[str, Any],
    ontology: dict[str, Any],
    dictionary: dict[str, Any],
    paper: PaperInput,
) -> bool:
    expected = {
        "tag_schema_version": ontology["schema_version"],
        "tag_dictionary_version": dictionary["dictionary_version"],
        "tag_engine_version": TAG_ENGINE_VERSION,
        "tag_schema_hash": ontology["_config_hash"],
        "tag_dictionary_hash": dictionary["_config_hash"],
        "source_hash": hash_text_sources(paper.text_sources),
    }
    return any(previous.get(key) != value for key, value in expected.items())


def write_tags_yaml(output_dir: Path, result: dict[str, Any]) -> Path:
    paper_dir = output_dir / safe_path_name(result["paper_id"])
    paper_dir.mkdir(parents=True, exist_ok=True)
    path = paper_dir / "tags.yaml"
    write_yaml(path, result)
    return path


def read_existing_tags(output_dir: Path, paper_id: str) -> dict[str, Any] | None:
    path = output_dir / safe_path_name(paper_id) / "tags.yaml"
    if not path.exists():
        return None
    return read_yaml(path)


def build_options(
    root: str | Path = PROJECT_ROOT,
    changed_only: bool = False,
    category: str | None = None,
    tag: str | None = None,
    ontology_path: str | Path | None = None,
    dictionary_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    report_dir: str | Path | None = None,
    update_sqlite: bool = True,
    update_lancedb: bool = True,
    sqlite_path: str | Path | None = None,
    lancedb_dir: str | Path | None = None,
) -> RetagOptions:
    root_path = Path(root).resolve()
    return RetagOptions(
        root=root_path,
        ontology_path=Path(ontology_path).resolve() if ontology_path else root_path / "Config" / "tag_ontology.yaml",
        dictionary_path=Path(dictionary_path).resolve() if dictionary_path else root_path / "Config" / "tag_dictionary.yaml",
        output_dir=Path(output_dir).resolve() if output_dir else root_path / "05_Index" / "tags",
        report_dir=Path(report_dir).resolve() if report_dir else root_path / "07_Workflows" / "reports",
        changed_only=changed_only,
        category=category,
        tag=tag,
        update_sqlite=update_sqlite,
        update_lancedb=update_lancedb,
        sqlite_path=Path(sqlite_path).resolve() if sqlite_path else root_path / "02_Metadata" / "scientra.db",
        lancedb_dir=Path(lancedb_dir).resolve() if lancedb_dir else root_path / "04_VectorDB",
    )


def validate_selector(ontology: dict[str, Any], category: str | None, tag: str | None) -> None:
    if category is not None and category not in ontology.get("categories", {}):
        raise ValueError(f"unknown tag category: {category}")
    if tag is not None and tag not in ontology_tags(ontology):
        raise ValueError(f"unknown tag: {tag}")


def diff_tag_results(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, list[str]]:
    previous_tags = flatten_assigned_tags(previous.get("assigned_tags", {})) if previous else set()
    current_tags = flatten_assigned_tags(current.get("assigned_tags", {}))
    return {
        "added": sorted(current_tags - previous_tags),
        "removed": sorted(previous_tags - current_tags),
        "unchanged": sorted(current_tags & previous_tags),
    }


def count_tags(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        for tag_name in flatten_assigned_tags(result.get("assigned_tags", {}), include_category=False):
            counts[tag_name] = counts.get(tag_name, 0) + 1
    return counts


def collect_new_hits(results: list[dict[str, Any]]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for result in results:
        for added in result.get("changes", {}).get("added", []):
            tag_name = added.split(":", 1)[-1]
            hits.setdefault(tag_name, []).append(result["paper_id"])
    return hits


def summarize_changes(results: list[dict[str, Any]]) -> dict[str, int]:
    stats = {
        "papers_changed": 0,
        "tags_added": 0,
        "tags_removed": 0,
        "tags_unchanged": 0,
    }
    for result in results:
        changes = result.get("changes", {})
        added = len(changes.get("added", []))
        removed = len(changes.get("removed", []))
        unchanged = len(changes.get("unchanged", []))
        if added or removed:
            stats["papers_changed"] += 1
        stats["tags_added"] += added
        stats["tags_removed"] += removed
        stats["tags_unchanged"] += unchanged
    return stats


def flatten_assigned_tags(
    assigned_tags: dict[str, list[str]],
    include_category: bool = True,
) -> set[str]:
    values: set[str] = set()
    for category, tags in assigned_tags.items():
        for tag_name in tags:
            values.add(f"{category}:{tag_name}" if include_category else tag_name)
    return values


def ontology_tags(ontology: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for category_tags in ontology.get("categories", {}).values():
        tags.update(category_tags)
    return tags


def category_for_tag(ontology: dict[str, Any], tag: str) -> str | None:
    for category, tags in ontology.get("categories", {}).items():
        if tag in tags:
            return category
    return None


def coerce_paper_input(paper: PaperInput | dict[str, Any]) -> PaperInput:
    if isinstance(paper, PaperInput):
        return paper
    text_sources = paper.get("text_sources") or {
        "title": as_text(paper.get("title")),
        "abstract": as_text(paper.get("abstract")),
        "summary": as_text(paper.get("summary")),
        "raw_text": as_text(paper.get("raw_text")),
        "chunks": as_text(paper.get("chunks")),
    }
    paper_key = str(paper.get("key") or paper.get("paper_key") or paper.get("paper_id") or "unknown")
    return PaperInput(
        key=paper_key,
        paper_id=str(paper.get("paper_id") or paper_key),
        text_sources={str(key): as_text(value) for key, value in text_sources.items()},
        metadata=paper.get("metadata") or {},
        source_files=paper.get("source_files") or {},
    )


def source_priority_order(text_sources: dict[str, str]) -> list[str]:
    known = [name for name in SOURCE_PRIORITY if name in text_sources]
    extra = sorted(name for name in text_sources if name not in SOURCE_PRIORITY)
    return known + extra


def hash_text_sources(text_sources: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for source_name in source_priority_order(text_sources):
        digest.update(source_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update((text_sources.get(source_name) or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def read_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return payload or {}


def write_yaml(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    temp_path.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path and path.exists():
            return path
    return None


def read_text_if_exists(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        values = [str(value)]
    return unique_preserve_order([as_text(item).strip() for item in values if as_text(item).strip()])


def normalize_section_list(value: Any) -> list[str]:
    return unique_preserve_order(
        [section_name.strip().casefold() for section_name in normalize_string_list(value)]
    )


def unique_preserve_order(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = str(value).casefold()
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


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(as_text(item) for item in value if as_text(item))
    if isinstance(value, dict):
        for key in ["name", "title", "text", "content"]:
            if key in value:
                return as_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def as_float(value: Any, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe or "paper"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
