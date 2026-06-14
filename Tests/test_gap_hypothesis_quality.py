"""Tests for Gap-Hypothesis Quality Check module.

Run: python -m pytest Tests/test_gap_hypothesis_quality.py -v
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestGapScoring:
    def test_evidence_grounding_empty(self):
        from scientra.ai.gap_hypothesis_quality import _score_gap
        gap = {"gap_id": "g1", "based_on_evidence": [], "gap_statement": "Test gap about mechanism X.", "gap_type": "mechanistic", "confidence": 0.8}
        s = _score_gap(gap, {"g1"})
        assert s["evidence_grounding_score"] < 0.3

    def test_evidence_grounding_strong(self):
        from scientra.ai.gap_hypothesis_quality import _score_gap
        gap = {"gap_id": "g1", "based_on_evidence": ["Evidence A long text here", "Evidence B long text here", "Evidence C long text here"],
               "gap_statement": "The mechanism of X is unknown because Y is not tested.", "gap_type": "mechanistic", "confidence": 0.8,
               "missing_information": "Missing pathway link", "why_it_matters": "Drug target"}
        s = _score_gap(gap, {"g1"})
        assert s["evidence_grounding_score"] >= 0.7

    def test_vague_statement_penalty(self):
        from scientra.ai.gap_hypothesis_quality import _score_gap
        gap = {"gap_id": "g1", "based_on_evidence": ["E1"], "gap_type": "mechanistic",
               "gap_statement": "Further research is needed to understand the mechanism.", "confidence": 0.6}
        s = _score_gap(gap, {"g1"})
        assert s["specificity_score"] < 0.5

    def test_high_confidence_low_grounding_overclaim(self):
        from scientra.ai.gap_hypothesis_quality import _score_gap
        gap = {"gap_id": "g1", "based_on_evidence": [], "gap_type": "unknown",
               "gap_statement": "X", "confidence": 0.95}
        s = _score_gap(gap, {"g1"})
        # No evidence + high confidence = high overclaim risk
        assert s["overclaim_risk"] in ("medium", "high")

    def test_medium_confidence_with_some_evidence(self):
        from scientra.ai.gap_hypothesis_quality import _score_gap
        gap = {"gap_id": "g1", "based_on_evidence": ["E1 long enough text here"],
               "gap_type": "mechanistic", "gap_statement": "Mechanism X is unknown.",
               "confidence": 0.7, "missing_information": "Pathway", "why_it_matters": "Target"}
        s = _score_gap(gap, {"g1"})
        # One evidence item, moderate confidence → not high overclaim
        assert s["overclaim_risk"] in ("low", "medium")

    def test_gap_type_affects_novelty(self):
        from scientra.ai.gap_hypothesis_quality import _score_gap
        gap1 = {"gap_id": "g1", "based_on_evidence": ["E long text"], "gap_type": "contradiction",
                "gap_statement": "Finding A contradicts B.", "confidence": 0.7,
                "missing_information": "Explanation needed", "why_it_matters": "Field impact"}
        gap2 = {"gap_id": "g2", "based_on_evidence": ["E long text"], "gap_type": "scope",
                "gap_statement": "Only tested in one cell line.", "confidence": 0.7,
                "missing_information": "Other cell types", "why_it_matters": "Generalizability"}
        s1 = _score_gap(gap1, {"g1", "g2"})
        s2 = _score_gap(gap2, {"g1", "g2"})
        assert s1["novelty_score"] > s2["novelty_score"]


class TestHypothesisScoring:
    def test_linked_gap_valid(self):
        from scientra.ai.gap_hypothesis_quality import _score_hypothesis
        hyp = {"hypothesis_id": "h1", "linked_gap_id": "g1",
               "testable_prediction": "X will increase upon treatment.",
               "suggested_experiment": "RNAi knockdown in Sf9 cells followed by qPCR",
               "rationale": "Because X is downstream of the pathway.",
               "supporting_evidence": ["E1"], "confidence": 0.8}
        s = _score_hypothesis(hyp, {"g1", "g2"})
        assert s["linked_gap_valid"] is True

    def test_linked_gap_invalid(self):
        from scientra.ai.gap_hypothesis_quality import _score_hypothesis
        hyp = {"hypothesis_id": "h1", "linked_gap_id": "nonexistent_gap",
               "testable_prediction": "X", "suggested_experiment": "Y", "rationale": "Z",
               "supporting_evidence": [], "confidence": 0.5}
        s = _score_hypothesis(hyp, {"g1"})
        assert s["linked_gap_valid"] is False

    def test_testability_missing_prediction(self):
        from scientra.ai.gap_hypothesis_quality import _score_hypothesis
        hyp = {"hypothesis_id": "h1", "linked_gap_id": "g1",
               "testable_prediction": "", "suggested_experiment": "Experiment.",
               "rationale": "Reason.", "supporting_evidence": [], "confidence": 0.5}
        s = _score_hypothesis(hyp, {"g1"})
        assert s["testability_score"] < 0.4

    def test_testability_strong_prediction(self):
        from scientra.ai.gap_hypothesis_quality import _score_hypothesis
        hyp = {"hypothesis_id": "h1", "linked_gap_id": "g1",
               "testable_prediction": "Knockdown of gene X will significantly reduce apoptosis as measured by a significant decrease in caspase-3 cleavage.",
               "suggested_experiment": "RNAi knockdown in Sf9 cells, measure caspase-3 cleavage by western blot.",
               "rationale": "X is an upstream activator of the apoptotic cascade.", "supporting_evidence": ["E1", "E2"],
               "confidence": 0.85}
        s = _score_hypothesis(hyp, {"g1"})
        assert s["testability_score"] >= 0.7

    def test_missing_experiment_lowers_feasibility(self):
        from scientra.ai.gap_hypothesis_quality import _score_hypothesis
        hyp = {"hypothesis_id": "h1", "linked_gap_id": "g1",
               "testable_prediction": "X prediction.", "suggested_experiment": "",
               "rationale": "R.", "supporting_evidence": [], "confidence": 0.5}
        s = _score_hypothesis(hyp, {"g1"})
        assert s["experiment_feasibility_score"] < 0.4

    def test_dangerous_keyword_detected(self):
        from scientra.ai.gap_hypothesis_quality import _score_hypothesis
        hyp = {"hypothesis_id": "h1", "linked_gap_id": "g1",
               "hypothesis_statement": "If we do a clinical trial in human subjects, then...",
               "testable_prediction": "X", "suggested_experiment": "Clinical trial with patients",
               "rationale": "R.", "supporting_evidence": [], "confidence": 0.5}
        s = _score_hypothesis(hyp, {"g1"})
        assert len(s["safety_or_ethics_warning"]) > 0


class TestOverallEvaluation:
    def test_evaluate_single_paper(self, tmp_path):
        from scientra.ai.gap_hypothesis_quality import evaluate_gap_hypothesis_quality, OUTPUT_DIR
        import scientra.ai.gap_hypothesis_quality as ghq

        with patch.object(ghq, "OUTPUT_DIR", tmp_path / "quality"):
            with patch.object(ghq, "PROJECT_ROOT", tmp_path):
                # Create gaps and hypotheses
                assets = tmp_path / "03_Assets" / "ai"
                gaps_dir = assets / "gaps"
                gaps_dir.mkdir(parents=True)
                (gaps_dir / "test.json").write_text(json.dumps({
                    "gaps": [
                        {"gap_id": "g1", "gap_statement": "Mechanism of X is unknown because no knockout data.",
                         "gap_type": "mechanistic", "based_on_evidence": ["E1 long text", "E2 long text", "E3 long text"],
                         "missing_information": "Knockout data for X", "why_it_matters": "Drug target validation",
                         "confidence": 0.85, "warnings": []},
                    ]
                }))
                hyp_dir = assets / "hypotheses"
                hyp_dir.mkdir(parents=True)
                (hyp_dir / "test.json").write_text(json.dumps({
                    "hypotheses": [
                        {"hypothesis_id": "h1", "hypothesis_statement": "If X is knocked down, then Y decreases.",
                         "rationale": "X is upstream of Y based on evidence.", "linked_gap_id": "g1",
                         "supporting_evidence": ["E1", "E2"],
                         "testable_prediction": "X knockdown will significantly decrease Y protein levels.",
                         "suggested_experiment": "RNAi knockdown of X in Sf9 cells, measure Y by western blot.",
                         "risk_level": "medium", "confidence": 0.85, "warnings": []},
                    ]
                }))

                result = evaluate_gap_hypothesis_quality(paper_id="test")
                assert result["status"] == "evaluated"
                assert result["gap_count"] == 1
                assert result["hypothesis_count"] == 1
                assert result["hypothesis_scores"][0]["linked_gap_valid"] is True
                assert result["overall_quality_score"] > 0.6

    def test_missing_data(self, tmp_path):
        from scientra.ai.gap_hypothesis_quality import evaluate_gap_hypothesis_quality
        import scientra.ai.gap_hypothesis_quality as ghq

        with patch.object(ghq, "OUTPUT_DIR", tmp_path / "quality"):
            with patch.object(ghq, "PROJECT_ROOT", tmp_path / "empty"):
                result = evaluate_gap_hypothesis_quality(paper_id="nonexistent")
                assert result["status"] == "insufficient_data"
                assert result["recommendation"] == "insufficient_data"

    def test_invalid_link_detected(self, tmp_path):
        from scientra.ai.gap_hypothesis_quality import evaluate_gap_hypothesis_quality
        import scientra.ai.gap_hypothesis_quality as ghq

        with patch.object(ghq, "OUTPUT_DIR", tmp_path / "quality"):
            with patch.object(ghq, "PROJECT_ROOT", tmp_path):
                assets = tmp_path / "03_Assets" / "ai"
                (assets / "gaps").mkdir(parents=True)
                (assets / "hypotheses").mkdir(parents=True)
                (assets / "gaps" / "test.json").write_text(json.dumps({
                    "gaps": [{"gap_id": "g1", "gap_statement": "Gap.", "gap_type": "mechanistic",
                              "based_on_evidence": ["E1"], "missing_information": "M", "why_it_matters": "W",
                              "confidence": 0.7, "warnings": []}]
                }))
                (assets / "hypotheses" / "test.json").write_text(json.dumps({
                    "hypotheses": [{"hypothesis_id": "h1", "linked_gap_id": "WRONG_GAP",
                                    "testable_prediction": "T", "suggested_experiment": "E",
                                    "rationale": "R", "supporting_evidence": [], "confidence": 0.5, "warnings": []}]
                }))
                result = evaluate_gap_hypothesis_quality(paper_id="test")
                assert result["hypothesis_scores"][0]["linked_gap_valid"] is False
                assert result["metrics"]["invalid_linked_gap_count"] == 1


class TestSummaryGeneration:
    def test_evaluate_all_papers(self, tmp_path):
        from scientra.ai.gap_hypothesis_quality import evaluate_all_papers, OUTPUT_DIR
        import scientra.ai.gap_hypothesis_quality as ghq

        with patch.object(ghq, "OUTPUT_DIR", tmp_path / "quality"):
            with patch.object(ghq, "PROJECT_ROOT", tmp_path):
                assets = tmp_path / "03_Assets" / "ai"
                gaps_dir = assets / "gaps"
                gaps_dir.mkdir(parents=True)
                hyp_dir = assets / "hypotheses"
                hyp_dir.mkdir(parents=True)

                for pid in ["p1", "p2"]:
                    (gaps_dir / f"{pid}.json").write_text(json.dumps({
                        "gaps": [{"gap_id": f"{pid}:g1", "gap_statement": "Research gap.", "gap_type": "mechanistic",
                                  "based_on_evidence": ["E1", "E2", "E3"], "missing_information": "M", "why_it_matters": "W",
                                  "confidence": 0.8, "warnings": []}]
                    }))
                    (hyp_dir / f"{pid}.json").write_text(json.dumps({
                        "hypotheses": [{"hypothesis_id": f"{pid}:h1", "linked_gap_id": f"{pid}:g1",
                                        "testable_prediction": "X will decrease.", "suggested_experiment": "RNAi + qPCR.",
                                        "rationale": "X is downstream.", "supporting_evidence": ["E1"],
                                        "confidence": 0.8, "warnings": []}]
                    }))

                summary = evaluate_all_papers(limit=2)
                assert summary["total_papers"] == 2
                # With minimal test data, any recommendation valid except insufficient_data
                assert summary["accept_count"] + summary["manual_review_count"] + summary["reject_count"] >= 1
                assert "average_quality_score" in summary
                assert summary["invalid_linked_gap_count"] == 0

    def test_empty_summary(self):
        from scientra.ai.gap_hypothesis_quality import _empty_summary
        s = _empty_summary()
        assert s["total_papers"] == 0
        assert s["accept_count"] == 0


class TestOutputSaveLoad:
    def test_save_and_load(self, tmp_path):
        from scientra.ai.gap_hypothesis_quality import _save_output, load_quality, OUTPUT_DIR
        import scientra.ai.gap_hypothesis_quality as ghq

        with patch.object(ghq, "OUTPUT_DIR", tmp_path / "quality"):
            data = {"paper_id": "t", "recommendation": "accept", "overall_quality_score": 0.85}
            _save_output("t", data)
            loaded = load_quality("t")
            assert loaded is not None
            assert loaded["recommendation"] == "accept"

    def test_load_missing(self, tmp_path):
        from scientra.ai.gap_hypothesis_quality import load_quality
        import scientra.ai.gap_hypothesis_quality as ghq

        with patch.object(ghq, "OUTPUT_DIR", tmp_path / "empty"):
            assert load_quality("nope") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
