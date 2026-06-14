"""Paper Lookup — find papers by ID, DOI, title, or query."""

from __future__ import annotations

import re
from typing import Any

from scientra.papers.paper_registry import load_paper_registry, _normalize


def find_paper_by_id(paper_id: str) -> dict[str, Any] | None:
    """Find a paper by exact paper_id."""
    reg = load_paper_registry()
    if not reg:
        return None
    return reg.get("papers", {}).get(paper_id)


def find_paper_by_doi(doi: str) -> dict[str, Any] | None:
    """Find a paper by DOI."""
    reg = load_paper_registry()
    if not reg:
        return None
    # Try exact match first
    doi_index = reg.get("doi_index", {})
    pid = doi_index.get(doi)
    if pid:
        return reg.get("papers", {}).get(pid)
    # Try normalized match
    norm_doi = doi.strip().lower().replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    for d, p in doi_index.items():
        if d.strip().lower() == norm_doi:
            return reg.get("papers", {}).get(p)
    return None


def find_paper_by_title(title: str, fuzzy: bool = True) -> dict[str, Any] | None:
    """Find a paper by title. If fuzzy=True, uses substring matching."""
    reg = load_paper_registry()
    if not reg:
        return None

    papers = reg.get("papers", {})
    norm_query = _normalize(title)

    if not fuzzy:
        # Exact normalized match
        title_index = reg.get("title_index", {})
        pid = title_index.get(norm_query)
        if pid:
            return papers.get(pid)
        return None

    # Fuzzy: try exact normalized first, then substring
    title_index = reg.get("title_index", {})
    pid = title_index.get(norm_query)
    if pid:
        return papers.get(pid)

    # Substring search
    for pid, entry in papers.items():
        entry_title = entry.get("title", "")
        if norm_query in _normalize(entry_title):
            return entry

    return None


def search_papers(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search papers by query string (match on title, doi, paper_id, display_name).

    Returns a list of matching paper entries, sorted by relevance.
    """
    reg = load_paper_registry()
    if not reg:
        return []

    papers = reg.get("papers", {})
    norm_q = _normalize(query)
    # Also keep original query words for per-word matching
    query_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', query) if len(w) > 2]
    scored: list[tuple[float, dict[str, Any]]] = []

    for pid, entry in papers.items():
        score = 0.0
        title = _normalize(entry.get("title", ""))
        doi = _normalize(entry.get("doi", ""))
        display = _normalize(entry.get("display_name", ""))
        raw_title = entry.get("title", "").lower()

        # Exact match bonus
        if norm_q == title:
            score = 100.0
        elif norm_q in title:
            score = 50.0
        # Per-word matching on normalized title
        elif any(w in title for w in query_words):
            score = 20.0 + len([w for w in query_words if w in title]) * 10.0
        # Per-word matching on raw title (handles partial words like "Vip3Aa")
        elif any(w in raw_title for w in query_words):
            score = 15.0 + len([w for w in query_words if w in raw_title]) * 5.0

        # DOI match
        if norm_q in doi:
            score += 20.0

        # Display name match
        if norm_q in display:
            score += 15.0

        # Paper ID match
        if norm_q in _normalize(pid):
            score += 10.0

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:limit]]


def find_paper(query: str) -> dict[str, Any] | None:
    """Universal paper finder: tries paper_id, DOI, then fuzzy title.

    Returns the best match or None.
    """
    # Try paper_id
    result = find_paper_by_id(query)
    if result:
        return result

    # Try DOI
    if "/" in query or "doi" in query.lower():
        result = find_paper_by_doi(query)
        if result:
            return result

    # Try title
    result = find_paper_by_title(query, fuzzy=True)
    if result:
        return result

    # Fallback: search
    results = search_papers(query, limit=1)
    return results[0] if results else None
