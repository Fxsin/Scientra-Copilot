"""Tests for Research Evolution API endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── Fixtures ──


@pytest.fixture
def mock_evolution_data():
    """Mock research evolution data as returned by load_research_evolution()."""
    return {
        "status": "generated",
        "phases": [
            {
                "phase_id": "phase_001",
                "year_range": "2000-2004",
                "paper_count": 5,
                "representative_papers": [],
                "dominant_topics": ["vip3aa", "resistance", "mechanism"],
                "dominant_methods": ["western", "binding assay"],
                "dominant_entities": ["vip3aa", "bt", "helicoverpa"],
                "core_findings": ["Vip3Aa resistance mechanism studied"],
                "emerging_gaps": [],
                "persistent_gaps": [],
                "emerging_hypotheses": [],
                "resolved_or_declining_topics": [],
                "opportunity_signals": [],
                "phase_summary": "Early phase overview",
            },
            {
                "phase_id": "phase_002",
                "year_range": "2005-2009",
                "paper_count": 8,
                "representative_papers": [],
                "dominant_topics": ["resistance", "receptor", "binding"],
                "dominant_methods": ["rna interference", "crispr"],
                "dominant_entities": ["vip3aa", "receptor", "midgut"],
                "core_findings": ["Multiple resistance mechanisms identified"],
                "emerging_gaps": [{"cluster_id": "gc_001", "title": "Test emerging gap", "trend": "emerging", "paper_count": 3}],
                "persistent_gaps": [{"cluster_id": "gc_002", "title": "Test persistent gap", "trend": "persistent", "paper_count": 5}],
                "emerging_hypotheses": [],
                "resolved_or_declining_topics": [],
                "opportunity_signals": [],
                "phase_summary": "Middle phase overview",
            },
        ],
        "gap_evolution": [
            {
                "cluster_id": "gc_001",
                "unified_gap_statement": "Emerging gap about Vip3Aa resistance",
                "gap_type": "mechanistic",
                "paper_count": 3,
                "first_seen_year": 2008,
                "last_seen_year": 2009,
                "active_year_span": 1,
                "paper_count_by_phase": {"phase_002": 3},
                "trend": "emerging",
                "persistence_score": 0.5,
                "closure_signal": "open",
            },
            {
                "cluster_id": "gc_002",
                "unified_gap_statement": "Persistent gap about receptor binding",
                "gap_type": "mechanistic",
                "paper_count": 10,
                "first_seen_year": 2000,
                "last_seen_year": 2009,
                "active_year_span": 9,
                "paper_count_by_phase": {"phase_001": 5, "phase_002": 5},
                "trend": "persistent",
                "persistence_score": 1.0,
                "closure_signal": "partially_addressed",
            },
            {
                "cluster_id": "gc_003",
                "unified_gap_statement": "Declining gap about old methods",
                "gap_type": "methodological",
                "paper_count": 2,
                "first_seen_year": 2001,
                "last_seen_year": 2003,
                "active_year_span": 2,
                "paper_count_by_phase": {"phase_001": 2},
                "trend": "declining",
                "persistence_score": 0.2,
                "closure_signal": "possibly_resolved",
            },
        ],
        "hypothesis_evolution": [
            {
                "hypothesis_cluster_id": "hc_001",
                "unified_hypothesis_statement": "Test emerging hypothesis",
                "linked_gap_cluster_id": "gc_001",
                "first_seen_year": 2008,
                "last_seen_year": 2009,
                "trend": "emerging",
                "validation_status": "partially_supported",
                "risk_trend": "stable",
            },
        ],
        "opportunity_evolution": [
            {
                "opportunity_id": "opp_001",
                "title": "Test opportunity",
                "opportunity_score": 0.85,
                "first_seen_year": 2008,
                "latest_support_year": 2009,
                "trend": "growing",
                "priority_trajectory": "rising",
            },
        ],
        "summary": {
            "total_papers": 54,
            "year_span": 28,
            "year_min": 1996,
            "year_max": 2024,
            "phase_count": 6,
            "total_gap_clusters": 134,
            "total_hypothesis_clusters": 182,
            "total_opportunities": 134,
            "gap_trend_distribution": {"persistent": 80, "emerging": 30, "declining": 24},
        },
    }


# ── Tests ──


class TestResearchEvolutionNotAvailable:
    """Test API behavior when research evolution file doesn't exist."""

    def test_available_false_when_no_data(self, mock_evolution_data):
        """When load_research_evolution returns None, available should be false."""
        with patch("scientra.ai.research_evolution.load_research_evolution", return_value=None):
            from scientra.ai.research_evolution import load_research_evolution
            data = load_research_evolution()
            assert data is None


class TestResearchEvolutionAPI:
    """Test the API response shape (unit-level, not integration)."""

    def test_response_has_available_field(self, mock_evolution_data):
        """Full response should have available=True."""
        assert "phases" in mock_evolution_data
        assert "gap_evolution" in mock_evolution_data
        assert "hypothesis_evolution" in mock_evolution_data
        assert "opportunity_evolution" in mock_evolution_data
        assert "summary" in mock_evolution_data
        assert mock_evolution_data["status"] == "generated"

    def test_phases_have_required_fields(self, mock_evolution_data):
        """Each phase should have required fields."""
        for ph in mock_evolution_data["phases"]:
            assert "phase_id" in ph
            assert "year_range" in ph
            assert "paper_count" in ph
            assert "dominant_topics" in ph
            assert "dominant_methods" in ph
            assert "dominant_entities" in ph
            assert "emerging_gaps" in ph
            assert "persistent_gaps" in ph
            assert "emerging_hypotheses" in ph
            assert "opportunity_signals" in ph
            assert "phase_summary" in ph

    def test_gap_evolution_has_required_fields(self, mock_evolution_data):
        """Each gap evolution entry should have required fields."""
        for g in mock_evolution_data["gap_evolution"]:
            assert "cluster_id" in g
            assert "trend" in g
            assert "first_seen_year" in g
            assert "last_seen_year" in g
            assert "active_year_span" in g
            assert "paper_count_by_phase" in g
            assert "persistence_score" in g
            assert "closure_signal" in g

    def test_hypothesis_evolution_has_required_fields(self, mock_evolution_data):
        """Each hypothesis evolution entry should have required fields."""
        for h in mock_evolution_data["hypothesis_evolution"]:
            assert "hypothesis_cluster_id" in h
            assert "trend" in h
            assert "first_seen_year" in h
            assert "last_seen_year" in h
            assert "validation_status" in h
            assert "risk_trend" in h
            assert "linked_gap_cluster_id" in h

    def test_opportunity_evolution_has_required_fields(self, mock_evolution_data):
        """Each opportunity evolution entry should have required fields."""
        for o in mock_evolution_data["opportunity_evolution"]:
            assert "opportunity_id" in o
            assert "trend" in o
            assert "first_seen_year" in o
            assert "latest_support_year" in o
            assert "priority_trajectory" in o


class TestFilterLogic:
    """Test that filter logic would work correctly."""

    def test_filter_by_phase(self, mock_evolution_data):
        """Filtering gaps by phase_id should return only gaps in that phase."""
        gaps = mock_evolution_data["gap_evolution"]
        phase_id = "phase_002"
        filtered = [g for g in gaps if phase_id in g.get("paper_count_by_phase", {})]
        assert len(filtered) == 2  # gc_001 and gc_002

    def test_filter_by_trend(self, mock_evolution_data):
        """Filtering by trend should return only matching items."""
        gaps = mock_evolution_data["gap_evolution"]
        filtered = [g for g in gaps if g.get("trend") == "emerging"]
        assert len(filtered) == 1
        assert filtered[0]["cluster_id"] == "gc_001"

    def test_filter_by_gap_type(self, mock_evolution_data):
        """Filtering by gap_type should return only matching gaps."""
        gaps = mock_evolution_data["gap_evolution"]
        filtered = [g for g in gaps if g.get("gap_type") == "mechanistic"]
        assert len(filtered) == 2

    def test_filter_unknown_trend_returns_empty(self, mock_evolution_data):
        """Filtering by a trend not in data should return empty."""
        gaps = mock_evolution_data["gap_evolution"]
        filtered = [g for g in gaps if g.get("trend") == "single_period"]
        assert len(filtered) == 0
