"""Tests for paper lookup."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scientra.papers.paper_lookup import (
    find_paper_by_id,
    find_paper_by_doi,
    find_paper_by_title,
    search_papers,
    find_paper,
)


SAMPLE_REG = {
    "papers": {
        "paper_aaa": {
            "paper_id": "paper_aaa",
            "title": "Vip3Aa Resistance Mechanisms in Helicoverpa",
            "year": "2023",
            "doi": "10.1000/vip.2023",
            "display_name": "2023_Vip3Aa_Resistance_Mechanisms",
            "source_dir": "01_Sources/papers/2023_Vip3Aa_Resistance_Mechanisms",
        },
        "paper_bbb": {
            "paper_id": "paper_bbb",
            "title": "Cry1Ac Binding Studies in Lepidoptera",
            "year": "2021",
            "doi": "10.2000/cry.2021",
            "display_name": "2021_Cry1Ac_Binding_Studies",
            "source_dir": "01_Sources/papers/2021_Cry1Ac_Binding_Studies",
        },
        "paper_ccc": {
            "paper_id": "paper_ccc",
            "title": "Transgenic Cotton Expressing Vip3A",
            "year": "2022",
            "doi": "10.3000/trans.2022",
            "display_name": "2022_Transgenic_Cotton_Expressing_Vip3A",
            "source_dir": "01_Sources/papers/2022_Transgenic_Cotton_Expressing_Vip3A",
        },
    },
    "title_index": {
        "vip3aaresistancemechanismsinhelicoverpa": "paper_aaa",
        "cry1acbindingstudiesinlepidoptera": "paper_bbb",
        "transgeniccottonexpressingvip3a": "paper_ccc",
    },
    "doi_index": {
        "10.1000/vip.2023": "paper_aaa",
        "10.2000/cry.2021": "paper_bbb",
        "10.3000/trans.2022": "paper_ccc",
    },
    "total_papers": 3,
}


@pytest.fixture(autouse=True)
def mock_registry():
    with patch("scientra.papers.paper_lookup.load_paper_registry", return_value=SAMPLE_REG):
        yield


class TestFindById:
    def test_exact_match(self):
        r = find_paper_by_id("paper_aaa")
        assert r is not None
        assert r["title"].startswith("Vip3Aa")

    def test_not_found(self):
        r = find_paper_by_id("paper_nonexistent")
        assert r is None


class TestFindByDOI:
    def test_exact(self):
        r = find_paper_by_doi("10.1000/vip.2023")
        assert r is not None
        assert r["paper_id"] == "paper_aaa"

    def test_not_found(self):
        r = find_paper_by_doi("10.9999/nope")
        assert r is None


class TestFindByTitle:
    def test_exact_normalized(self):
        r = find_paper_by_title("Vip3Aa Resistance Mechanisms in Helicoverpa", fuzzy=False)
        assert r is not None

    def test_fuzzy_substring(self):
        r = find_paper_by_title("Vip3Aa Resistance", fuzzy=True)
        assert r is not None
        assert r["paper_id"] == "paper_aaa"

    def test_fuzzy_not_found(self):
        r = find_paper_by_title("Completely Different Topic", fuzzy=True)
        assert r is None


class TestSearchPapers:
    def test_search_by_keyword(self):
        results = search_papers("Vip3A")
        assert len(results) >= 2  # paper_aaa and paper_ccc

    def test_search_by_doi(self):
        results = search_papers("10.1000")
        assert len(results) >= 1

    def test_search_no_match(self):
        results = search_papers("zzz_nonexistent_zzz")
        assert len(results) == 0


class TestFindPaper:
    def test_find_by_id(self):
        r = find_paper("paper_aaa")
        assert r is not None

    def test_find_by_doi(self):
        r = find_paper("10.1000/vip.2023")
        assert r is not None

    def test_find_by_title_keyword(self):
        r = find_paper("Vip3Aa Resistance")
        assert r is not None
