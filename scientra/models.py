from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    search_by_keyword = "search_by_keyword"
    search_by_species = "search_by_species"
    search_by_toxin = "search_by_toxin"
    search_by_method = "search_by_method"
    search_by_mechanism = "search_by_mechanism"
    search_by_year = "search_by_year"
    hybrid_search = "hybrid_search"


class QueryFilters(BaseModel):
    species: list[str] = Field(default_factory=list)
    toxin: list[str] = Field(default_factory=list)
    method: list[str] = Field(default_factory=list)
    mechanism: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    year: int | None = None
    year_gte: int | None = None
    year_lte: int | None = None
    doi: str | None = None
    paper_id: str | None = None


class LiteratureQueryRequest(BaseModel):
    query_type: QueryType = QueryType.search_by_keyword
    query: str | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    filters: QueryFilters = Field(default_factory=QueryFilters)
    include_summaries: bool = True
    include_evidence: bool = True
    include_citations: bool = True
    use_vector: bool = True


class PaperResult(BaseModel):
    paper_id: str
    title: str | None = None
    journal: str | None = None
    year: int | None = None
    doi: str | None = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    species: list[str] = Field(default_factory=list)
    toxin: list[str] = Field(default_factory=list)
    method: list[str] = Field(default_factory=list)
    mechanism: list[str] = Field(default_factory=list)


class SummaryResult(BaseModel):
    paper_id: str
    summary_path: str | None = None
    text: str | None = None
    sections: dict[str, list[str]] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    paper_id: str
    source: str
    matched_terms: list[str] = Field(default_factory=list)
    excerpt: str | None = None
    page: str | None = None
    paragraph: int | None = None
    section: str | None = None
    score: float | None = None


class CitationItem(BaseModel):
    paper_id: str
    citation_id: str
    title: str | None = None
    doi: str | None = None
    year: int | None = None
    source: str | None = None
    page: str | None = None
    paragraph: int | None = None
    section: str | None = None
    excerpt: str | None = None


class ScoreItem(BaseModel):
    paper_id: str
    score: float
    keyword_score: float = 0.0
    filter_score: float = 0.0
    vector_score: float | None = None
    reasons: list[str] = Field(default_factory=list)


class LiteratureQueryResponse(BaseModel):
    query_type: QueryType
    query: str | None = None
    papers: list[PaperResult] = Field(default_factory=list)
    summaries: list[SummaryResult] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[CitationItem] = Field(default_factory=list)
    scores: list[ScoreItem] = Field(default_factory=list)
    total: int = 0
    vector_used: bool = False
    warnings: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(
        default_factory=lambda: {
            "agent_entrypoint": "literature_query",
            "pdf_access": "forbidden",
            "direct_lancedb_access": "forbidden",
        }
    )

