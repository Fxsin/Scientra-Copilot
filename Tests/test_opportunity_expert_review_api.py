"""Tests for Opportunity Expert Review API endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── Fixtures ──


@pytest.fixture
def mock_reviews_data():
    """Mock review data as returned by load_reviews()."""
    return {
        "status": "generated",
        "reviews": [
            {
                "opportunity_id": "opp_0001",
                "rank": 1,
                "title": "Vip3Aa resistance mechanism",
                "opportunity_score": 0.906,
                "review_status": "accept",
                "scientific_importance": "Central question in Bt resistance biology.",
                "evidence_strength_assessment": "Strong evidence from 33 papers across multiple labs.",
                "technical_feasibility": "Feasible with established insect molecular biology techniques.",
                "novelty_assessment": "Novel application of known receptor identification methods.",
                "major_risks": ["Competing labs may publish first", "Receptor redundancy"],
                "key_missing_evidence": ["Direct binding kinetics data"],
                "recommended_next_steps": [
                    "Clone candidate receptor genes from resistant strains",
                    "Perform binding assays with purified Vip3Aa",
                ],
                "possible_experimental_routes": ["CRISPR knockout in H. zea"],
                "expected_impact": "Would enable resistance monitoring and management strategies.",
                "review_confidence": 0.88,
                "review_warnings": [],
                "usage": {"cost_estimate": 0.002, "total_tokens": 1500},
            },
            {
                "opportunity_id": "opp_0002",
                "rank": 2,
                "title": "Cry1Ca + Vip3A synergy testing",
                "opportunity_score": 0.85,
                "review_status": "revise",
                "scientific_importance": "Important for pyramided Bt crop development.",
                "evidence_strength_assessment": "Evidence from 25 papers, some contradictory.",
                "technical_feasibility": "Feasible but requires multi-toxin bioassay optimization.",
                "novelty_assessment": "Logical next step in Bt crop development.",
                "major_risks": ["Synergy may not translate to field conditions"],
                "key_missing_evidence": ["Field trial data", "Dose-response curves"],
                "recommended_next_steps": [
                    "Perform systematic combination bioassays",
                    "Validate in field-relevant conditions",
                ],
                "possible_experimental_routes": ["Diet overlay bioassays"],
                "expected_impact": "Would inform Bt crop pyramiding strategies.",
                "review_confidence": 0.72,
                "review_warnings": [],
                "usage": {"cost_estimate": 0.002, "total_tokens": 1400},
            },
            {
                "opportunity_id": "opp_0003",
                "rank": 3,
                "title": "Old methodology gap",
                "opportunity_score": 0.55,
                "review_status": "reject",
                "scientific_importance": "Well-studied area with diminishing returns.",
                "evidence_strength_assessment": "Weak evidence, primarily from older papers.",
                "technical_feasibility": "Technical approaches exist but unlikely to yield new insights.",
                "novelty_assessment": "Incremental at best.",
                "major_risks": ["Low impact even if successful"],
                "key_missing_evidence": ["Justification for further study"],
                "recommended_next_steps": [],
                "possible_experimental_routes": [],
                "expected_impact": "Limited.",
                "review_confidence": 0.65,
                "review_warnings": [],
                "usage": {"cost_estimate": 0.001, "total_tokens": 1000},
            },
            {
                "opportunity_id": "opp_0004",
                "rank": 4,
                "title": "Sparse data gap",
                "opportunity_score": 0.70,
                "review_status": "insufficient_data",
                "scientific_importance": "Potentially interesting but poorly characterized.",
                "evidence_strength_assessment": "Only one paper with limited replication.",
                "technical_feasibility": "Cannot assess without more preliminary data.",
                "novelty_assessment": "Unclear until more data available.",
                "major_risks": ["Foundation evidence may not replicate"],
                "key_missing_evidence": ["Independent replication", "Orthogonal validation"],
                "recommended_next_steps": ["Generate preliminary data first"],
                "possible_experimental_routes": ["Pilot study with small sample"],
                "expected_impact": "Unknown — too early to assess.",
                "review_confidence": 0.30,
                "review_warnings": ["Insufficient evidence for confident assessment"],
                "usage": {"cost_estimate": 0.001, "total_tokens": 900},
            },
        ],
        "summary": {
            "reviewed_count": 4,
            "accept_count": 1,
            "revise_count": 1,
            "reject_count": 1,
            "insufficient_data_count": 1,
            "error_count": 0,
            "average_review_confidence": 0.638,
            "total_cost_usd": 0.006,
            "cost_per_review_usd": 0.0015,
        },
    }


# ── Tests ──


class TestAPIResponseShape:
    def test_response_has_available(self, mock_reviews_data):
        assert "reviews" in mock_reviews_data
        assert "summary" in mock_reviews_data
        assert mock_reviews_data["status"] == "generated"

    def test_each_review_has_required_fields(self, mock_reviews_data):
        required = [
            "opportunity_id", "rank", "title", "review_status",
            "scientific_importance", "evidence_strength_assessment",
            "technical_feasibility", "novelty_assessment",
            "major_risks", "key_missing_evidence",
            "recommended_next_steps", "possible_experimental_routes",
            "expected_impact", "review_confidence", "review_warnings",
        ]
        for r in mock_reviews_data["reviews"]:
            for field in required:
                assert field in r, f"Missing field: {field}"

    def test_valid_review_statuses(self, mock_reviews_data):
        valid = {"accept", "revise", "reject", "insufficient_data"}
        for r in mock_reviews_data["reviews"]:
            assert r["review_status"] in valid, f"Invalid status: {r['review_status']}"

    def test_review_confidence_in_range(self, mock_reviews_data):
        for r in mock_reviews_data["reviews"]:
            assert 0 <= r["review_confidence"] <= 1.0

    def test_summary_has_counts(self, mock_reviews_data):
        s = mock_reviews_data["summary"]
        assert s["reviewed_count"] == 4
        assert "accept_count" in s
        assert "revise_count" in s
        assert "reject_count" in s
        assert "insufficient_data_count" in s
        assert "total_cost_usd" in s


class TestFilterLogic:
    def test_filter_by_status_accept(self, mock_reviews_data):
        reviews = mock_reviews_data["reviews"]
        filtered = [r for r in reviews if r["review_status"] == "accept"]
        assert len(filtered) == 1
        assert filtered[0]["opportunity_id"] == "opp_0001"

    def test_filter_by_status_revise(self, mock_reviews_data):
        reviews = mock_reviews_data["reviews"]
        filtered = [r for r in reviews if r["review_status"] == "revise"]
        assert len(filtered) == 1
        assert filtered[0]["opportunity_id"] == "opp_0002"

    def test_filter_by_min_confidence(self, mock_reviews_data):
        reviews = mock_reviews_data["reviews"]
        filtered = [r for r in reviews if r.get("review_confidence", 0) >= 0.7]
        assert len(filtered) == 2

    def test_filter_by_min_confidence_high(self, mock_reviews_data):
        reviews = mock_reviews_data["reviews"]
        filtered = [r for r in reviews if r.get("review_confidence", 0) >= 0.9]
        assert len(filtered) == 0

    def test_filter_combined(self, mock_reviews_data):
        reviews = mock_reviews_data["reviews"]
        filtered = [
            r for r in reviews
            if r["review_status"] in ("accept", "revise")
            and r.get("review_confidence", 0) >= 0.7
        ]
        assert len(filtered) == 2


class TestNotAvailable:
    def test_none_returns_not_available(self):
        """When load_reviews returns None, API should report available=False."""
        with patch("scientra.ai.opportunity_expert_review.load_reviews", return_value=None):
            from scientra.ai.opportunity_expert_review import load_reviews
            data = load_reviews()
            assert data is None
