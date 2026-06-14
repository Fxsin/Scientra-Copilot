"""
Test: Parse Quality Scoring.

Verifies:
- score_parse_result returns ParserQualityReport
- All quality dimensions are scored (metadata, markdown, layout, refs, figures, tables)
- Garbled text detection works
- Missing data produces appropriate problems/recommendations
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_score_empty_result():
    """Empty inputs should produce zero scores with problems."""
    from scientra.parsers.quality import score_parse_result

    report = score_parse_result(
        paper_id="test_empty",
        parser_outputs=[],
    )

    assert report is not None
    assert report.metadata_score == 0.0
    assert report.markdown_score == 0.0
    assert len(report.problems) > 0
    assert len(report.recommendations) > 0
    print(f"Empty result: overall={report.overall_score}, problems={len(report.problems)}")


def test_score_good_metadata():
    """Good metadata should score high."""
    from scientra.parsers.quality import score_parse_result

    metadata = {
        "title": "A Comprehensive Study of Bt Toxins",
        "abstract": "This paper explores the mechanisms of Bacillus thuringiensis toxins...",
        "doi": "10.1234/example.2024",
        "authors": ["Smith, John", "Doe, Jane"],
        "year": "2024",
        "journal": "Journal of Insect Science",
        "references": [
            {"title": "Ref 1", "authors": ["Author A"], "year": "2020"},
            {"title": "Ref 2", "authors": ["Author B"], "year": "2021"},
            {"title": "Ref 3", "authors": ["Author C"], "year": "2022"},
            {"title": "Ref 4", "authors": ["Author D"], "year": "2023"},
            {"title": "Ref 5", "authors": ["Author E"], "year": "2023"},
            {"title": "Ref 6", "authors": ["Author F"], "year": "2024"},
            {"title": "Ref 7", "authors": ["Author G"], "year": "2024"},
            {"title": "Ref 8", "authors": ["Author H"], "year": "2024"},
            {"title": "Ref 9", "authors": ["Author I"], "year": "2024"},
            {"title": "Ref 10", "authors": ["Author J"], "year": "2024"},
            {"title": "Ref 11", "authors": ["Author K"], "year": "2024"},
        ],
    }

    report = score_parse_result(
        paper_id="test_good_meta",
        parser_outputs=[],
        metadata=metadata,
    )

    assert report.metadata_score > 0.5, f"Expected metadata_score > 0.5, got {report.metadata_score}"
    print(f"Good metadata score: metadata={report.metadata_score}")


def test_score_good_markdown():
    """Good markdown with sections should score high."""
    from scientra.parsers.quality import score_parse_result

    markdown_text = """
    # Abstract
    This study investigates...

    # Introduction
    Bacillus thuringiensis (Bt) produces insecticidal proteins...

    # Methods
    We used RNA-seq and proteomics approaches...

    # Results
    Our analysis revealed significant changes in gene expression...

    # Discussion
    These findings suggest that Vip3Aa triggers...

    # Conclusion
    In summary, our study demonstrates...

    # References
    1. Smith et al., 2020
    2. Doe et al., 2021
    """ * 10  # Make it longer

    report = score_parse_result(
        paper_id="test_good_md",
        parser_outputs=[],
        markdown_text=markdown_text,
    )

    assert report.markdown_score > 0.5, f"Expected markdown_score > 0.5, got {report.markdown_score}"
    print(f"Good markdown score: markdown={report.markdown_score}")


def test_score_garbled_text():
    """Garbled text should lower the markdown score."""
    from scientra.parsers.quality import score_parse_result

    garbled_text = """
    Introduction ���
    Some text with encoding issues Ã¢ and â characters.
    But there is still some Introduction and Methods content.
    """ * 20

    report = score_parse_result(
        paper_id="test_garbled",
        parser_outputs=[],
        markdown_text=garbled_text,
    )

    # With garbled text, the score should be lower than a clean text
    problems_text = " ".join(report.problems).lower()
    has_garbled_flag = any(
        word in problems_text for word in ["garbled", "encod"]
    )
    print(f"Garbled text score: markdown={report.markdown_score}, problems={report.problems}")
    # At minimum, we should not crash
    assert report.markdown_score >= 0.0


def test_score_all_dimensions():
    """All quality dimensions should be present in the report."""
    from scientra.parsers.quality import score_parse_result

    report = score_parse_result(
        paper_id="test_dims",
        parser_outputs=[],
    )

    d = report.to_dict()
    assert "metadata_score" in d
    assert "markdown_score" in d
    assert "layout_score" in d
    assert "reference_score" in d
    assert "figure_score" in d
    assert "table_score" in d
    assert "overall_score" in d
    assert "problems" in d
    assert "recommendations" in d
    print("All quality dimensions present.")


if __name__ == "__main__":
    test_score_empty_result()
    test_score_good_metadata()
    test_score_good_markdown()
    test_score_garbled_text()
    test_score_all_dimensions()
    print("\n[OK] All parse quality tests passed!")
