from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from scientra.models import (
        CitationItem,
        EvidenceItem,
        LiteratureQueryRequest,
        LiteratureQueryResponse,
        PaperResult,
        QueryFilters,
        QueryType,
        ScoreItem,
        SummaryResult,
    )
except ModuleNotFoundError:
    from scientra.models import (
        CitationItem,
        EvidenceItem,
        LiteratureQueryRequest,
        LiteratureQueryResponse,
        PaperResult,
        QueryFilters,
        QueryType,
        ScoreItem,
        SummaryResult,
    )


def _detect_project_root() -> Path:
    """Walk up from this file until a 'Config/workflow_config.yaml' is found."""
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / "Config" / "workflow_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
SUMMARY_SECTION_NAMES = {
    "Core Finding",
    "Evidence",
    "Methods",
    "Key Results",
    "Limitations",
    "Future Work",
}


@dataclass(frozen=True)
class LiteraturePaper:
    paper_id: str
    key: str
    title: str | None
    journal: str | None
    year: int | None
    doi: str | None
    authors: list[str]
    abstract: str | None
    tags: list[str]
    assigned_tags: dict[str, list[str]]
    species: list[str]
    toxin: list[str]
    method: list[str]
    mechanism: list[str]
    metadata: dict[str, Any]
    summary_path: Path | None
    summary_text: str
    summary_sections: dict[str, list[str]]
    evidence_from_tags: dict[str, Any]
    citations: list[dict[str, Any]]


def literature_query(
    request: LiteratureQueryRequest | dict[str, Any] | str | None = None,
    **kwargs: Any,
) -> LiteratureQueryResponse:
    """Unified Scientra Copilot query entrypoint for every Agent."""
    parsed_request = coerce_request(request, kwargs)
    service = LiteratureQueryService(PROJECT_ROOT)
    return service.query(parsed_request)


class LiteratureQueryService:
    def __init__(self, root: str | Path = PROJECT_ROOT) -> None:
        self.root = Path(root).resolve()
        self._papers: list[LiteraturePaper] | None = None

    def query(self, request: LiteratureQueryRequest) -> LiteratureQueryResponse:
        if request.query_type == QueryType.search_by_keyword:
            ranked, warnings, vector_used = self.search_by_keyword(request)
        elif request.query_type == QueryType.search_by_species:
            ranked, warnings, vector_used = self.search_by_field(request, "species")
        elif request.query_type == QueryType.search_by_toxin:
            ranked, warnings, vector_used = self.search_by_field(request, "toxin")
        elif request.query_type == QueryType.search_by_method:
            ranked, warnings, vector_used = self.search_by_field(request, "method")
        elif request.query_type == QueryType.search_by_mechanism:
            ranked, warnings, vector_used = self.search_by_field(request, "mechanism")
        elif request.query_type == QueryType.search_by_year:
            ranked, warnings, vector_used = self.search_by_year(request)
        elif request.query_type == QueryType.hybrid_search:
            ranked, warnings, vector_used = self.hybrid_search(request)
        else:
            ranked, warnings, vector_used = [], [f"unsupported query_type: {request.query_type}"], False

        ranked = ranked[: request.top_k]
        papers = [paper_to_result(item["paper"]) for item in ranked]
        summaries = (
            [paper_to_summary(item["paper"]) for item in ranked]
            if request.include_summaries
            else []
        )
        evidence = (
            collect_response_evidence(ranked)
            if request.include_evidence
            else []
        )
        citations = (
            collect_response_citations(ranked)
            if request.include_citations
            else []
        )
        scores = [
            ScoreItem(
                paper_id=item["paper"].paper_id,
                score=round(item["score"], 4),
                keyword_score=round(item.get("keyword_score", 0.0), 4),
                filter_score=round(item.get("filter_score", 0.0), 4),
                vector_score=item.get("vector_score"),
                reasons=item.get("reasons", []),
            )
            for item in ranked
        ]
        return LiteratureQueryResponse(
            query_type=request.query_type,
            query=request.query,
            papers=papers,
            summaries=summaries,
            evidence=evidence,
            citations=citations,
            scores=scores,
            total=len(ranked),
            vector_used=vector_used,
            warnings=warnings,
        )

    def search_by_keyword(self, request: LiteratureQueryRequest) -> tuple[list[dict[str, Any]], list[str], bool]:
        query = request.query or ""
        warnings: list[str] = []
        ranked: list[dict[str, Any]] = []
        for paper in self.papers:
            if not passes_filters(paper, request.filters):
                continue
            keyword_score, reasons, matched_terms = score_keyword(paper, query)
            filter_score, filter_reasons = score_filters(paper, request.filters)
            score = keyword_score + filter_score
            if query and keyword_score <= 0:
                continue
            if score <= 0 and has_any_filter(request.filters):
                continue
            ranked.append(
                {
                    "paper": paper,
                    "score": score,
                    "keyword_score": keyword_score,
                    "filter_score": filter_score,
                    "vector_score": None,
                    "reasons": reasons + filter_reasons,
                    "matched_terms": matched_terms,
                }
            )
        return sort_ranked(ranked), warnings, False

    def search_by_field(
        self,
        request: LiteratureQueryRequest,
        field_name: str,
    ) -> tuple[list[dict[str, Any]], list[str], bool]:
        value = request.query or " ".join(getattr(request.filters, field_name, []))
        filters = merge_field_filter(request.filters, field_name, value)
        ranked: list[dict[str, Any]] = []
        for paper in self.papers:
            if not passes_filters(paper, filters):
                continue
            field_score, matched = score_field_match(getattr(paper, field_name), value)
            filter_score, filter_reasons = score_filters(paper, filters)
            score = field_score + filter_score
            if score <= 0:
                continue
            ranked.append(
                {
                    "paper": paper,
                    "score": score,
                    "keyword_score": field_score,
                    "filter_score": filter_score,
                    "vector_score": None,
                    "reasons": [f"{field_name}: {term}" for term in matched] + filter_reasons,
                    "matched_terms": matched,
                }
            )
        return sort_ranked(ranked), [], False

    def search_by_year(self, request: LiteratureQueryRequest) -> tuple[list[dict[str, Any]], list[str], bool]:
        filters = request.filters
        if request.query and not filters.year:
            year = normalize_year(request.query)
            if year:
                filters = copy_filters_with(filters, year=year)
        ranked: list[dict[str, Any]] = []
        for paper in self.papers:
            if not passes_filters(paper, filters):
                continue
            filter_score, reasons = score_filters(paper, filters)
            year_score = 2.0 if paper.year else 0.5
            ranked.append(
                {
                    "paper": paper,
                    "score": year_score + filter_score,
                    "keyword_score": 0.0,
                    "filter_score": filter_score,
                    "vector_score": None,
                    "reasons": reasons,
                    "matched_terms": [str(paper.year)] if paper.year else [],
                }
            )
        return sort_ranked(ranked), [], False

    def hybrid_search(self, request: LiteratureQueryRequest) -> tuple[list[dict[str, Any]], list[str], bool]:
        keyword_ranked, warnings, _ = self.search_by_keyword(request)
        combined: dict[str, dict[str, Any]] = {item["paper"].paper_id: dict(item) for item in keyword_ranked}
        vector_used = False

        if request.use_vector and request.query:
            try:
                vector_results = self.vector_search(request)
                vector_used = True
                for index, vector_result in enumerate(vector_results):
                    paper = self.paper_by_id(vector_result.get("paper_id"))
                    if paper is None or not passes_filters(paper, request.filters):
                        continue
                    vector_score = vector_to_score(vector_result.get("score"), rank=index)
                    item = combined.setdefault(
                        paper.paper_id,
                        {
                            "paper": paper,
                            "score": 0.0,
                            "keyword_score": 0.0,
                            "filter_score": 0.0,
                            "vector_score": None,
                            "reasons": [],
                            "matched_terms": [],
                        },
                    )
                    item["vector_score"] = vector_score
                    item["score"] += vector_score
                    item["reasons"].append("vector")
            except Exception as exc:
                warnings.append(f"vector search unavailable: {type(exc).__name__}: {exc}")

        return sort_ranked(list(combined.values())), warnings, vector_used

    def vector_search(self, request: LiteratureQueryRequest) -> list[dict[str, Any]]:
        try:
            from scientra.embedding import EmbeddingEngine, options_from_args
        except ModuleNotFoundError:
            from scientra.embedding import EmbeddingEngine, options_from_args

        class Args:
            root = self.root
            model_name = "BAAI/bge-m3"
            db_dir = self.root / "04_VectorDB" / "lancedb"
            table_name = "literature_vectors"
            device = None
            no_normalize = False

        options = options_from_args(Args())
        engine = EmbeddingEngine(options)
        return engine.search(
            query=request.query or "",
            top_k=request.top_k,
            level=None,
            tags=request.filters.tags or None,
            year=request.filters.year,
            year_gte=request.filters.year_gte,
            year_lte=request.filters.year_lte,
            doi=request.filters.doi,
        )

    @property
    def papers(self) -> list[LiteraturePaper]:
        if self._papers is None:
            self._papers = load_literature_papers(self.root)
        return self._papers

    def paper_by_id(self, paper_id: str | None) -> LiteraturePaper | None:
        if not paper_id:
            return None
        for paper in self.papers:
            if paper.paper_id == paper_id or paper.key == paper_id:
                return paper
        return None


def load_literature_papers(root: Path) -> list[LiteraturePaper]:
    records: dict[str, dict[str, Path | None]] = {}
    for path in sorted((root / "02_Metadata" / "yaml").glob("*.metadata.yaml")):
        key = path.name[: -len(".metadata.yaml")]
        records.setdefault(key, {})["metadata_yaml"] = path
    for path in sorted((root / "02_Metadata" / "papers").glob("*.metadata.json")):
        key = path.name[: -len(".metadata.json")]
        records.setdefault(key, {})["metadata_json"] = path
    for path in sorted((root / "03_Summary" / "raw_text").glob("*.txt")):
        key = path.stem
        records.setdefault(key, {})["raw_text"] = path

    papers: list[LiteraturePaper] = []
    for key, paths in sorted(records.items()):
        metadata = load_metadata(paths.get("metadata_yaml"), paths.get("metadata_json"))
        paper_id = str(metadata.get("paper_id") or key)
        summary_path = find_summary_path(root, paper_id, key)
        summary_text = read_text_if_exists(summary_path)
        summary_sections = parse_summary_sections(summary_text)
        assigned_tags, tag_evidence = load_tags(root, paper_id)
        citations = parse_summary_citations(summary_text, paper_id)
        papers.append(
            LiteraturePaper(
                paper_id=paper_id,
                key=key,
                title=clean_scalar(metadata.get("title") or dig(metadata, "metadata", "title")),
                journal=clean_scalar(metadata.get("journal") or dig(metadata, "metadata", "journal")),
                year=normalize_year(metadata.get("year") or dig(metadata, "metadata", "year")),
                doi=normalize_doi(metadata.get("doi") or dig(metadata, "metadata", "doi")),
                authors=normalize_authors(metadata.get("authors") or dig(metadata, "metadata", "authors")),
                abstract=clean_scalar(metadata.get("abstract")),
                tags=flatten_tags(assigned_tags),
                assigned_tags=assigned_tags,
                species=normalize_string_list(metadata.get("species")),
                toxin=unique_preserve_order(normalize_string_list(metadata.get("toxin")) + assigned_tags.get("TOXIN", [])),
                method=unique_preserve_order(normalize_string_list(metadata.get("method")) + assigned_tags.get("METHOD", [])),
                mechanism=unique_preserve_order(normalize_string_list(metadata.get("mechanism")) + assigned_tags.get("MECHANISM", [])),
                metadata=metadata,
                summary_path=summary_path,
                summary_text=summary_text,
                summary_sections=summary_sections,
                evidence_from_tags=tag_evidence,
                citations=citations,
            )
        )
    return papers


def coerce_request(
    request: LiteratureQueryRequest | dict[str, Any] | str | None,
    kwargs: dict[str, Any],
) -> LiteratureQueryRequest:
    if isinstance(request, LiteratureQueryRequest):
        data = model_to_dict(request)
        data.update(kwargs)
        return LiteratureQueryRequest(**data)
    if isinstance(request, str):
        data = {"query": request}
        data.update(kwargs)
        return LiteratureQueryRequest(**data)
    if isinstance(request, dict):
        data = dict(request)
        data.update(kwargs)
        return LiteratureQueryRequest(**data)
    return LiteratureQueryRequest(**kwargs)


def load_metadata(yaml_path: Path | None, json_path: Path | None) -> dict[str, Any]:
    if yaml_path and yaml_path.exists():
        return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if json_path and json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata") or {}
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


def load_tags(root: Path, paper_id: str) -> tuple[dict[str, list[str]], dict[str, Any]]:
    path = root / "05_Index" / "tags" / safe_path_name(paper_id) / "tags.yaml"
    if not path.exists():
        return {}, {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assigned = {
        str(category): [str(tag) for tag in tags]
        for category, tags in (payload.get("assigned_tags") or {}).items()
        if isinstance(tags, list)
    }
    return assigned, payload.get("evidence") or {}


def find_summary_path(root: Path, paper_id: str, key: str) -> Path | None:
    candidates = [
        root / "03_Summary" / safe_path_name(paper_id) / "summary.md",
        root / "03_Summary" / safe_path_name(key) / "summary.md",
        root / "03_Summary" / "summaries" / f"{paper_id}.md",
        root / "03_Summary" / "summaries" / f"{key}.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def parse_summary_sections(summary_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in summary_text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            name = heading.group(1).strip()
            current = name if name in SUMMARY_SECTION_NAMES else None
            if current:
                sections.setdefault(current, [])
            continue
        if current and line.strip().startswith("- "):
            sections[current].append(line.strip()[2:])
    return sections


def parse_summary_citations(summary_text: str, paper_id: str) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    in_sources = False
    for line in summary_text.splitlines():
        if line.strip() == "## Citation Sources":
            in_sources = True
            continue
        if in_sources and line.startswith("## "):
            break
        if not in_sources or not line.strip().startswith("- "):
            continue
        text = line.strip()[2:]
        source_id = text.split(":", 1)[0].strip()
        page = regex_group(text, r"page=([^,;]+)")
        paragraph = normalize_int(regex_group(text, r"paragraph=([^,;]+)"))
        section = regex_group(text, r"section=([^;]+)")
        excerpt = regex_group(text, r'excerpt="(.*?)"$')
        citations.append(
            {
                "paper_id": paper_id,
                "citation_id": source_id,
                "source": "summary",
                "page": clean_scalar(page),
                "paragraph": paragraph,
                "section": clean_scalar(section),
                "excerpt": clean_scalar(excerpt),
            }
        )
    return citations


def passes_filters(paper: LiteraturePaper, filters: QueryFilters) -> bool:
    if filters.paper_id and filters.paper_id not in {paper.paper_id, paper.key}:
        return False
    if filters.doi and normalize_doi(filters.doi) != paper.doi:
        return False
    if filters.year is not None and paper.year != filters.year:
        return False
    if filters.year_gte is not None and (paper.year is None or paper.year < filters.year_gte):
        return False
    if filters.year_lte is not None and (paper.year is None or paper.year > filters.year_lte):
        return False
    for field_name in ["species", "toxin", "method", "mechanism", "tags"]:
        wanted = getattr(filters, field_name)
        if wanted and not list_matches(getattr(paper, field_name), wanted):
            return False
    return True


def score_keyword(paper: LiteraturePaper, query: str) -> tuple[float, list[str], list[str]]:
    terms = tokenize_query(query)
    if not terms:
        return 0.0, [], []
    fields = [
        ("title", paper.title or "", 5.0),
        ("abstract", paper.abstract or "", 3.0),
        ("summary", paper.summary_text or "", 4.0),
        ("tags", " ".join(paper.tags), 2.5),
        ("metadata", json.dumps(paper.metadata, ensure_ascii=False), 1.0),
    ]
    score = 0.0
    reasons: list[str] = []
    matched: list[str] = []
    for term in terms:
        pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
        for field_name, text, weight in fields:
            count = len(pattern.findall(text))
            if count:
                score += min(count, 5) * weight
                reasons.append(f"{field_name}:{term}")
                matched.append(term)
    return score, unique_preserve_order(reasons), unique_preserve_order(matched)


def score_filters(paper: LiteraturePaper, filters: QueryFilters) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    for field_name in ["species", "toxin", "method", "mechanism", "tags"]:
        wanted = getattr(filters, field_name)
        if wanted and list_matches(getattr(paper, field_name), wanted):
            score += 3.0
            reasons.append(f"filter:{field_name}")
    if filters.year is not None and paper.year == filters.year:
        score += 2.0
        reasons.append("filter:year")
    if filters.year_gte is not None or filters.year_lte is not None:
        score += 1.0
        reasons.append("filter:year_range")
    if filters.doi and normalize_doi(filters.doi) == paper.doi:
        score += 4.0
        reasons.append("filter:doi")
    if filters.paper_id and filters.paper_id in {paper.paper_id, paper.key}:
        score += 4.0
        reasons.append("filter:paper_id")
    return score, reasons


def score_field_match(values: list[str], query: str) -> tuple[float, list[str]]:
    wanted = tokenize_query(query)
    if not wanted:
        return (2.0 if values else 0.0), values
    matched: list[str] = []
    for value in values:
        for term in wanted:
            if term.casefold() in value.casefold():
                matched.append(value)
    return len(unique_preserve_order(matched)) * 5.0, unique_preserve_order(matched)


def collect_response_evidence(ranked: list[dict[str, Any]]) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for item in ranked:
        paper = item["paper"]
        matched_terms = item.get("matched_terms", [])
        if matched_terms:
            evidence.append(
                EvidenceItem(
                    paper_id=paper.paper_id,
                    source="query_match",
                    matched_terms=matched_terms,
                    excerpt=best_excerpt(paper, matched_terms),
                    score=item["score"],
                )
            )
        for tag, payload in paper.evidence_from_tags.items():
            evidence.append(
                EvidenceItem(
                    paper_id=paper.paper_id,
                    source=f"tag:{tag}",
                    matched_terms=normalize_string_list(payload.get("matched_terms")),
                    excerpt=None,
                    page=None,
                    paragraph=None,
                    section=payload.get("category"),
                    score=payload.get("score"),
                )
            )
    return evidence


def collect_response_citations(ranked: list[dict[str, Any]]) -> list[CitationItem]:
    citations: list[CitationItem] = []
    for item in ranked:
        paper = item["paper"]
        if paper.citations:
            for citation in paper.citations:
                citations.append(
                    CitationItem(
                        paper_id=paper.paper_id,
                        citation_id=citation.get("citation_id") or "",
                        title=paper.title,
                        doi=paper.doi,
                        year=paper.year,
                        source=citation.get("source"),
                        page=citation.get("page"),
                        paragraph=citation.get("paragraph"),
                        section=citation.get("section"),
                        excerpt=citation.get("excerpt"),
                    )
                )
        else:
            citations.append(
                CitationItem(
                    paper_id=paper.paper_id,
                    citation_id="metadata",
                    title=paper.title,
                    doi=paper.doi,
                    year=paper.year,
                    source="metadata",
                    excerpt=paper.abstract,
                )
            )
    return citations


def paper_to_result(paper: LiteraturePaper) -> PaperResult:
    return PaperResult(
        paper_id=paper.paper_id,
        title=paper.title,
        journal=paper.journal,
        year=paper.year,
        doi=paper.doi,
        authors=paper.authors,
        tags=paper.tags,
        species=paper.species,
        toxin=paper.toxin,
        method=paper.method,
        mechanism=paper.mechanism,
    )


def paper_to_summary(paper: LiteraturePaper) -> SummaryResult:
    return SummaryResult(
        paper_id=paper.paper_id,
        summary_path=str(paper.summary_path) if paper.summary_path else None,
        text=paper.summary_text or paper.abstract,
        sections=paper.summary_sections,
    )


def merge_field_filter(filters: QueryFilters, field_name: str, value: str) -> QueryFilters:
    values = normalize_string_list(value)
    data = model_to_dict(filters)
    if values:
        data[field_name] = unique_preserve_order(data.get(field_name, []) + values)
    return QueryFilters(**data)


def copy_filters_with(filters: QueryFilters, **updates: Any) -> QueryFilters:
    data = model_to_dict(filters)
    data.update(updates)
    return QueryFilters(**data)


def has_any_filter(filters: QueryFilters) -> bool:
    data = model_to_dict(filters)
    return any(value for value in data.values())


def list_matches(values: list[str], wanted: list[str]) -> bool:
    haystack = " | ".join(values).casefold()
    return all(str(item).casefold() in haystack for item in wanted)


def tokenize_query(query: str | None) -> list[str]:
    if not query:
        return []
    terms = re.findall(r"[A-Za-z0-9_.+-]+|[\u4e00-\u9fff]+", query)
    return unique_preserve_order([term for term in terms if len(term.strip()) >= 2])


def best_excerpt(paper: LiteraturePaper, terms: list[str]) -> str | None:
    text = paper.summary_text or paper.abstract or ""
    if not text:
        return None
    lower = text.casefold()
    indexes = [lower.find(term.casefold()) for term in terms if lower.find(term.casefold()) >= 0]
    index = min(indexes) if indexes else 0
    start = max(0, index - 160)
    end = min(len(text), index + 260)
    return text[start:end].strip()


def sort_ranked(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        ranked,
        key=lambda item: (
            -item["score"],
            -(item["paper"].year or 0),
            item["paper"].title or "",
        ),
    )


def vector_to_score(distance_or_score: Any, rank: int) -> float:
    if distance_or_score is None:
        return max(1.0, 10.0 - rank)
    try:
        value = float(distance_or_score)
    except (TypeError, ValueError):
        return max(1.0, 10.0 - rank)
    if value < 0:
        return 0.0
    return 1.0 / (1.0 + value)


def read_text_if_exists(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def flatten_tags(assigned_tags: dict[str, list[str]]) -> list[str]:
    tags: list[str] = []
    for values in assigned_tags.values():
        tags.extend(values)
    return unique_preserve_order(tags)


def normalize_authors(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        authors: list[str] = []
        for item in value:
            if isinstance(item, dict) and item.get("name"):
                authors.append(str(item["name"]))
            elif item:
                authors.append(str(item))
        return unique_preserve_order(authors)
    return []


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        return [value.strip()]
    if isinstance(value, list):
        return unique_preserve_order([str(item).strip() for item in value if str(item).strip()])
    return [str(value)]


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


def normalize_doi(value: Any) -> str | None:
    text = clean_scalar(value)
    if not text:
        return None
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).strip().rstrip(".,;:)])").lower()
    return text.lower()


def clean_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value.replace("\x00", "")).strip()
    return cleaned or None


def dig(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def regex_group(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe or "paper"


def unique_preserve_order(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)
