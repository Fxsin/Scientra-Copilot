"""
Test: Evidence Input Comparison (P1.5).

Verifies:
- compare_evidence_inputs generates report when both sources exist
- Returns use_legacy_raw_text or insufficient_data when hybrid missing
- Comparison does NOT write to 03_Evidence/
- summary.json is generated correctly by compare_all_papers
- malformed_text_ratio is computed correctly
- Recommendation logic is testable
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Helpers ──

def _make_legacy_text(root: Path, paper_id: str, content: str) -> Path:
    rt_dir = root / "03_Summary" / "raw_text"
    rt_dir.mkdir(parents=True, exist_ok=True)
    rt_path = rt_dir / f"{paper_id}.txt"
    rt_path.write_text(content, encoding="utf-8")
    return rt_path


def _make_hybrid_markdown(root: Path, paper_id: str, content: str) -> Path:
    md_dir = root / "02_Parse" / "markdown" / "final"
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{paper_id}.md"
    md_path.write_text(content, encoding="utf-8")
    return md_path


def _make_manifest(root: Path, paper_id: str, overall_score: float = 0.85) -> Path:
    manifest_dir = root / "02_Parse" / "reports" / "hybrid"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{paper_id}_parse_manifest.json"
    manifest_path.write_text(json.dumps({
        "paper_id": paper_id,
        "quality_report": {
            "overall_score": overall_score,
            "markdown_score": overall_score,
        },
    }, indent=2), encoding="utf-8")
    return manifest_path


_GOOD_PAPER_TEXT = """
# Abstract
This paper investigates the effects of Bt toxin Vip3Aa on Spodoptera frugiperda.

# Introduction
Bacillus thuringiensis produces insecticidal proteins that are widely used in agriculture.
The Vip3Aa toxin has shown activity against lepidopteran pests.

# Methods
We used RNA-seq analysis to measure gene expression changes.
Western blot validation was performed using standard protocols.
The assay was conducted in triplicate with appropriate controls.
Quantitative PCR confirmed the expression levels.
Statistical analysis was performed using R.

# Results
We found that Vip3Aa significantly increased mortality rates by 80 percent.
The results demonstrate dose-dependent response in treated cells.
Our data show upregulation of apoptotic markers within 6 hours.
We observed membrane disruption in midgut epithelial cells.
The effect was specific to lepidopteran cell lines.

# Discussion
These findings suggest a novel mechanism of action involving membrane pore formation.
The results appear consistent with previous studies on Cry toxins.
This may have implications for resistance management strategies.
A limitation is the small sample size used in this study.
Future studies should investigate binding domain specificity.

# Conclusion
In conclusion, Vip3Aa represents a promising biopesticide with a distinct mode of action.
Our study provides mechanistic insights into its insecticidal activity.
"""


# ── Test 1: Both sources exist → generates comparison report ──

def test_comparison_with_both_sources():
    """When both legacy and hybrid exist, generates a full comparison report."""
    from scientra.parsers.evidence_input_comparison import compare_evidence_inputs

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_both_sources"

        _make_legacy_text(root, paper_id, _GOOD_PAPER_TEXT)
        _make_hybrid_markdown(root, paper_id, "# Hybrid\n\n" + _GOOD_PAPER_TEXT)
        _make_manifest(root, paper_id, overall_score=0.85)

        report = compare_evidence_inputs(paper_id=paper_id, root=root)

        # Basic structure
        assert report["paper_id"] == paper_id
        assert report["recommendation"] in (
            "use_hybrid_markdown", "use_legacy_raw_text",
            "manual_review", "insufficient_data",
        )

        # Sources available
        assert report["sources"]["legacy_raw_text_available"] is True
        assert report["sources"]["hybrid_final_markdown_available"] is True

        # Both extractions succeeded
        assert report["legacy"]["status"] == "success"
        assert report["hybrid"]["status"] == "success"

        # Evidence was extracted
        le = report["legacy"]["evidence_stats"]
        assert le["total_evidence_count"] > 0

        he = report["hybrid"]["evidence_stats"]
        assert he["total_evidence_count"] > 0

        # Comparison deltas exist
        comp = report["comparison"]
        assert "text_length_delta" in comp

        # Report was saved
        report_path = Path(report["_report_path"])
        assert report_path.exists()
        assert "hybrid_validation" in str(report_path)

        print(f"[OK] Both sources: recommendation={report['recommendation']}, "
              f"legacy_evidence={le['total_evidence_count']}, "
              f"hybrid_evidence={he['total_evidence_count']}")


# ── Test 2: Hybrid missing → use_legacy_raw_text or insufficient_data ──

def test_comparison_hybrid_missing():
    """When hybrid final markdown doesn't exist, recommendation is appropriate."""
    from scientra.parsers.evidence_input_comparison import compare_evidence_inputs

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_hybrid_missing"

        _make_legacy_text(root, paper_id, _GOOD_PAPER_TEXT)
        # No hybrid markdown or manifest

        report = compare_evidence_inputs(paper_id=paper_id, root=root)

        assert report["sources"]["legacy_raw_text_available"] is True
        assert report["sources"]["hybrid_final_markdown_available"] is False
        assert report["hybrid"]["status"] == "skipped"

        # Recommendation must be use_legacy_raw_text or insufficient_data
        assert report["recommendation"] in ("use_legacy_raw_text", "insufficient_data"), (
            f"Expected use_legacy_raw_text or insufficient_data, got {report['recommendation']}"
        )

        print(f"[OK] Hybrid missing: recommendation={report['recommendation']}")


# ── Test 3: Comparison does NOT pollute 03_Evidence/ ──

def test_comparison_does_not_write_evidence():
    """Running comparison must not write to 03_Evidence/."""
    from scientra.parsers.evidence_input_comparison import compare_evidence_inputs

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_no_pollution"

        _make_legacy_text(root, paper_id, _GOOD_PAPER_TEXT)
        _make_hybrid_markdown(root, paper_id, "# Hybrid\n\n" + _GOOD_PAPER_TEXT)
        _make_manifest(root, paper_id, overall_score=0.85)

        # Ensure 03_Evidence directory doesn't exist before
        evidence_dir = root / "03_Evidence" / paper_id
        assert not evidence_dir.exists(), "03_Evidence should not exist before test"

        report = compare_evidence_inputs(paper_id=paper_id, root=root)

        # 03_Evidence must NOT have been created
        assert not evidence_dir.exists(), (
            f"03_Evidence/{paper_id} was created — comparison must not pollute main pipeline!"
        )

        # But validation report must exist
        report_path = Path(report["_report_path"])
        assert report_path.exists()
        assert "hybrid_validation" in str(report_path)

        print(f"[OK] No pollution: 03_Evidence/ not created, report in hybrid_validation/")


# ── Test 4: summary.json generated correctly ──

def test_compare_all_generates_summary():
    """compare_all_papers should generate a valid summary.json."""
    from scientra.parsers.evidence_input_comparison import compare_all_papers

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_ids = ["paper_a", "paper_b", "paper_c"]

        for pid in paper_ids:
            _make_legacy_text(root, pid, _GOOD_PAPER_TEXT)
            _make_hybrid_markdown(root, pid, f"# Hybrid {pid}\n\n" + _GOOD_PAPER_TEXT)
            _make_manifest(root, pid, overall_score=0.80)

        summary = compare_all_papers(root=root, limit=3)

        assert summary["total_papers_compared"] == 3
        assert "recommendations" in summary
        assert "hybrid_recommended_pct" in summary
        assert "legacy_recommended_pct" in summary
        assert "manual_review_pct" in summary
        assert "average_hybrid_quality_score" in summary
        assert "average_legacy_evidence_count" in summary
        assert "average_hybrid_evidence_count" in summary
        assert "per_paper_results" in summary
        assert len(summary["per_paper_results"]) == 3

        # Verify summary was saved
        summary_path = Path(summary["_summary_path"])
        assert summary_path.exists()
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
        assert saved["total_papers_compared"] == 3

        print(f"[OK] Summary: {summary['total_papers_compared']} papers, "
              f"hybrid_rec={summary['hybrid_recommended_pct']}%, "
              f"manual_review={summary['manual_review_pct']}%")


# ── Test 5: malformed_text_ratio computed correctly ──

def test_malformed_text_ratio():
    """malformed_text_ratio should detect garbled text correctly."""
    from scientra.parsers.evidence_input_comparison import _compute_text_stats

    # Clean text
    clean = _compute_text_stats("This is a clean text with proper encoding. No issues here.")
    assert clean["malformed_text_ratio"] == 0.0

    # Garbled text
    garbled = _compute_text_stats("Introduction ��� Some text with Ã©ncoding issues â here.")
    assert garbled["malformed_text_ratio"] > 0.0, (
        f"Expected malformed_text_ratio > 0 for garbled text, got {garbled['malformed_text_ratio']}"
    )

    # More garbled = higher ratio
    very_garbled = _compute_text_stats("��� ��� ��� Ã¢ Ã© â")
    assert very_garbled["malformed_text_ratio"] > garbled["malformed_text_ratio"], (
        "More garbled chars should produce higher malformed ratio"
    )

    print(f"[OK] Malformed ratios: clean={clean['malformed_text_ratio']:.6f}, "
          f"garbled={garbled['malformed_text_ratio']:.6f}, "
          f"very_garbled={very_garbled['malformed_text_ratio']:.6f}")


# ── Test 6: Recommendation logic ──

def test_recommendation_logic():
    """_generate_recommendation should produce correct results for known cases."""
    from scientra.parsers.evidence_input_comparison import _generate_recommendation

    # Case 1: Both excellent, hybrid better
    legacy = {
        "text_stats": {"text_length": 5000, "heading_count": 5, "malformed_text_ratio": 0.001,
                       "figure_reference_count": 3, "table_reference_count": 2},
        "evidence_stats": {"total_evidence_count": 15, "key_results_count": 5,
                          "methods_count": 3, "section_coverage": {"has_methods": True, "has_results": True}},
    }
    hybrid = {
        "text_stats": {"text_length": 5200, "heading_count": 8, "malformed_text_ratio": 0.0005,
                       "figure_reference_count": 4, "table_reference_count": 3},
        "evidence_stats": {"total_evidence_count": 16, "key_results_count": 6,
                          "methods_count": 4, "section_coverage": {"has_methods": True, "has_results": True}},
    }

    rec = _generate_recommendation(legacy, hybrid, hybrid_quality_score=0.85)
    assert rec == "use_hybrid_markdown", f"Expected use_hybrid_markdown, got {rec}"

    # Case 2: Hybrid much worse
    hybrid_bad = {
        "text_stats": {"text_length": 500, "heading_count": 0, "malformed_text_ratio": 0.05,
                       "figure_reference_count": 0, "table_reference_count": 0},
        "evidence_stats": {"total_evidence_count": 1, "key_results_count": 0,
                          "methods_count": 0, "section_coverage": {"has_methods": False, "has_results": False}},
    }

    rec = _generate_recommendation(legacy, hybrid_bad, hybrid_quality_score=0.30)
    assert rec == "use_legacy_raw_text", f"Expected use_legacy_raw_text for bad hybrid, got {rec}"

    # Case 3: Insufficient data (both empty)
    empty_legacy = {
        "text_stats": {"text_length": 0, "heading_count": 0, "malformed_text_ratio": 0},
        "evidence_stats": {"total_evidence_count": 0, "section_coverage": {}},
    }
    empty_hybrid = {
        "text_stats": {"text_length": 0, "heading_count": 0, "malformed_text_ratio": 0},
        "evidence_stats": {"total_evidence_count": 0, "section_coverage": {}},
    }

    rec = _generate_recommendation(empty_legacy, empty_hybrid, hybrid_quality_score=0.0)
    assert rec == "insufficient_data", f"Expected insufficient_data, got {rec}"

    # Case 4: Only hybrid has text (legacy empty)
    rec = _generate_recommendation(empty_legacy, hybrid, hybrid_quality_score=0.85)
    assert rec == "use_hybrid_markdown", f"Expected use_hybrid_markdown when only hybrid has text, got {rec}"

    # Case 5: Only hybrid has text but low quality
    rec = _generate_recommendation(empty_legacy, hybrid_bad, hybrid_quality_score=0.30)
    assert rec == "manual_review", f"Expected manual_review when only hybrid has low-quality text, got {rec}"

    print(f"[OK] Recommendation logic: all 5 cases pass")


if __name__ == "__main__":
    test_comparison_with_both_sources()
    test_comparison_hybrid_missing()
    test_comparison_does_not_write_evidence()
    test_compare_all_generates_summary()
    test_malformed_text_ratio()
    test_recommendation_logic()
    print("\n[OK] All evidence input comparison tests passed!")
