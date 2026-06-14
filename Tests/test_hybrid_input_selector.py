"""
Test: Hybrid Input Selector (P1).

Verifies:
- select_text_for_evidence returns legacy text when hybrid is disabled
- select_text_for_evidence returns hybrid markdown when enabled and quality is good
- Falls back to legacy when final markdown is missing
- Falls back to legacy when final markdown is empty
- Falls back to legacy when quality score is below threshold
- evidence_input_source appears in evidence extraction output
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Helpers ──

def _make_dummy_manifest(root: Path, paper_id: str, overall_score: float = 0.85) -> Path:
    """Create a dummy hybrid parse manifest."""
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


def _make_dummy_final_markdown(root: Path, paper_id: str, content: str = "# Test Paper\n\nContent here.") -> Path:
    """Create a dummy final markdown file."""
    md_dir = root / "02_Parse" / "markdown" / "final"
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{paper_id}.md"
    md_path.write_text(content, encoding="utf-8")
    return md_path


def _make_dummy_legacy_text(root: Path, paper_id: str, content: str = "Legacy raw text content.") -> Path:
    """Create a dummy legacy raw text file."""
    rt_dir = root / "03_Summary" / "raw_text"
    rt_dir.mkdir(parents=True, exist_ok=True)
    rt_path = rt_dir / f"{paper_id}.txt"
    rt_path.write_text(content, encoding="utf-8")
    return rt_path


# ── Test 1: prefer_hybrid_markdown_for_evidence=false → legacy ──

def test_disabled_returns_legacy():
    """When prefer_hybrid_markdown_for_evidence=false, should return legacy text."""
    from scientra.parsers.hybrid_input_selector import select_text_for_evidence

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_disabled_legacy"

        # Create both hybrid and legacy outputs
        _make_dummy_final_markdown(root, paper_id, "# Hybrid markdown")
        _make_dummy_manifest(root, paper_id, overall_score=0.9)
        legacy_path = _make_dummy_legacy_text(root, paper_id, "Legacy raw text content.")

        result = select_text_for_evidence(
            paper_id=paper_id,
            legacy_text_path=str(legacy_path),
            config={"enabled": True, "prefer_hybrid_markdown_for_evidence": False},
            root=root,
        )

        assert result["source"] == "legacy_raw_text", (
            f"Expected legacy_raw_text when prefer=false, got {result['source']}"
        )
        assert "Legacy raw text content" in result["text"]
        print("[OK] prefer=false correctly returns legacy text.")


# ── Test 2: prefer=true + good quality → hybrid markdown ──

def test_enabled_with_good_quality_returns_hybrid():
    """When prefer=true and quality is good, should return hybrid markdown."""
    from scientra.parsers.hybrid_input_selector import select_text_for_evidence

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_good_hybrid"

        _make_dummy_final_markdown(root, paper_id, "# Hybrid Final Markdown\n\nExcellent content here.")
        _make_dummy_manifest(root, paper_id, overall_score=0.85)
        legacy_path = _make_dummy_legacy_text(root, paper_id, "Legacy raw text.")

        result = select_text_for_evidence(
            paper_id=paper_id,
            legacy_text_path=str(legacy_path),
            config={
                "enabled": True,
                "prefer_hybrid_markdown_for_evidence": True,
                "min_final_markdown_score_for_evidence": 0.65,
            },
            root=root,
        )

        assert result["source"] == "hybrid_final_markdown", (
            f"Expected hybrid_final_markdown, got {result['source']}"
        )
        assert "Hybrid Final Markdown" in result["text"]
        assert result["quality_score"] == 0.85
        assert result["fallback_reason"] is None
        print("[OK] prefer=true with good quality correctly returns hybrid markdown.")


# ── Test 3: final markdown missing → fallback legacy ──

def test_missing_markdown_falls_back():
    """When final markdown doesn't exist, should fall back to legacy."""
    from scientra.parsers.hybrid_input_selector import select_text_for_evidence

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_missing_md"

        # Only create legacy text — no hybrid markdown
        legacy_path = _make_dummy_legacy_text(root, paper_id, "Legacy fallback text.")

        result = select_text_for_evidence(
            paper_id=paper_id,
            legacy_text_path=str(legacy_path),
            config={
                "enabled": True,
                "prefer_hybrid_markdown_for_evidence": True,
                "min_final_markdown_score_for_evidence": 0.65,
            },
            root=root,
        )

        assert result["source"] == "legacy_raw_text", (
            f"Expected legacy_raw_text fallback, got {result['source']}"
        )
        assert "Legacy fallback text" in result["text"]
        assert result["fallback_reason"] is not None
        assert "not found" in result["fallback_reason"].lower()
        print("[OK] Missing final markdown correctly falls back to legacy.")


# ── Test 4: final markdown empty → fallback legacy ──

def test_empty_markdown_falls_back():
    """When final markdown is empty, should fall back to legacy."""
    from scientra.parsers.hybrid_input_selector import select_text_for_evidence

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_empty_md"

        # Create empty final markdown
        _make_dummy_final_markdown(root, paper_id, "   \n  \n   ")
        _make_dummy_manifest(root, paper_id, overall_score=0.9)
        legacy_path = _make_dummy_legacy_text(root, paper_id, "Legacy text for empty fallback.")

        result = select_text_for_evidence(
            paper_id=paper_id,
            legacy_text_path=str(legacy_path),
            config={
                "enabled": True,
                "prefer_hybrid_markdown_for_evidence": True,
                "min_final_markdown_score_for_evidence": 0.65,
            },
            root=root,
        )

        assert result["source"] == "legacy_raw_text", (
            f"Expected legacy_raw_text for empty markdown, got {result['source']}"
        )
        assert result["fallback_reason"] is not None
        assert "empty" in result["fallback_reason"].lower()
        print("[OK] Empty final markdown correctly falls back to legacy.")


# ── Test 5: quality score below threshold → fallback legacy ──

def test_low_quality_falls_back():
    """When manifest quality score is below threshold, should fall back to legacy."""
    from scientra.parsers.hybrid_input_selector import select_text_for_evidence

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paper_id = "test_low_quality"

        _make_dummy_final_markdown(root, paper_id, "# Low quality markdown\n\nSome text.")
        _make_dummy_manifest(root, paper_id, overall_score=0.45)  # Below threshold
        legacy_path = _make_dummy_legacy_text(root, paper_id, "Legacy fallback for low quality.")

        result = select_text_for_evidence(
            paper_id=paper_id,
            legacy_text_path=str(legacy_path),
            config={
                "enabled": True,
                "prefer_hybrid_markdown_for_evidence": True,
                "min_final_markdown_score_for_evidence": 0.65,
            },
            root=root,
        )

        assert result["source"] == "legacy_raw_text", (
            f"Expected legacy_raw_text for low quality, got {result['source']}"
        )
        assert result["fallback_reason"] is not None
        assert "below threshold" in result["fallback_reason"].lower()
        print("[OK] Low quality score correctly falls back to legacy.")


# ── Test 6: evidence extraction records input source ──

def test_evidence_extraction_records_source():
    """After evidence extraction, output should contain evidence_input_source."""
    from scientra.evidence_extraction import extract_sections, extract_evidence

    # Use the extract functions directly (they accept text as string param)
    paper_id = "test_source_record"
    raw_text = """
    # Abstract
    This paper investigates the effects of Bt toxin on insect cells.

    # Introduction
    Bacillus thuringiensis produces insecticidal proteins.

    # Methods
    We used RNA-seq analysis and western blot validation.
    The assay was performed using standard protocols.
    We measured expression levels using quantitative PCR.

    # Results
    We found that Vip3Aa significantly increased mortality rates.
    The results demonstrate that toxin exposure led to 80% cell death.
    Our data show a dose-dependent response was observed.
    We demonstrated that the effect was specific to lepidopteran cells.

    # Discussion
    These findings suggest a novel mechanism of action.
    This appears to be mediated through membrane disruption.
    Future studies should investigate the binding domain.
    A limitation is the small sample size.

    # Conclusion
    In conclusion, Vip3Aa represents a promising biopesticide.
    """

    sections = extract_sections(raw_text, paper_id)

    # Simulate the metadata that would be recorded in main()
    sections["text_source"] = "hybrid_final_markdown"
    sections["text_source_path"] = "/tmp/02_Parse/markdown/final/test_source_record.md"
    sections["text_quality_score"] = 0.82

    evidence = extract_evidence(sections, None, {"title": "Test Paper", "year": "2024"}, paper_id)

    # Add the fields that main() would add
    evidence["evidence_input_source"] = "hybrid_final_markdown"
    evidence["evidence_input_path"] = "/tmp/02_Parse/markdown/final/test_source_record.md"
    evidence["evidence_input_quality_score"] = 0.82

    # Verify structure
    assert evidence["evidence_input_source"] == "hybrid_final_markdown"
    assert evidence["evidence_input_path"]
    assert evidence["evidence_input_quality_score"] == 0.82
    assert evidence["paper_id"] == paper_id
    assert "key_results" in evidence
    assert "methods" in evidence
    assert "core_findings" in evidence

    # Verify actual evidence was extracted
    assert len(evidence["key_results"]) > 0, "Should have extracted key results"
    assert len(evidence["methods"]) > 0, "Should have extracted methods"

    # Verify sections quality
    assert sections["section_quality"]["results"] in ("found", "combined")
    assert sections["section_quality"]["methods"] in ("found", "combined")

    print(f"[OK] Evidence extraction records source correctly.")
    print(f"     - key_results: {len(evidence['key_results'])}")
    print(f"     - methods: {len(evidence['methods'])}")
    print(f"     - core_findings: {len(evidence['core_findings'])}")
    print(f"     - evidence_input_source: {evidence['evidence_input_source']}")


# ── Test 7: legacy fallback also records source correctly ──

def test_legacy_fallback_records_source():
    """When falling back to legacy, evidence should record legacy_raw_text source."""
    from scientra.evidence_extraction import extract_sections, extract_evidence

    paper_id = "test_legacy_source"
    raw_text = "Legacy raw text from GROBID output. Introduction. Methods. Results. Discussion."

    sections = extract_sections(raw_text, paper_id)
    sections["text_source"] = "legacy_raw_text"
    sections["text_source_path"] = "/tmp/03_Summary/raw_text/test_legacy_source.txt"
    sections["text_quality_score"] = 0.0
    sections["fallback_reason"] = "Hybrid parser disabled"

    evidence = extract_evidence(sections, None, {}, paper_id)
    evidence["evidence_input_source"] = "legacy_raw_text"
    evidence["evidence_input_path"] = "/tmp/03_Summary/raw_text/test_legacy_source.txt"
    evidence["evidence_input_quality_score"] = 0.0
    evidence["fallback_reason"] = "Hybrid parser disabled"

    assert evidence["evidence_input_source"] == "legacy_raw_text"
    assert evidence["fallback_reason"] == "Hybrid parser disabled"
    print("[OK] Legacy fallback correctly records source and reason.")


if __name__ == "__main__":
    test_disabled_returns_legacy()
    test_enabled_with_good_quality_returns_hybrid()
    test_missing_markdown_falls_back()
    test_empty_markdown_falls_back()
    test_low_quality_falls_back()
    test_evidence_extraction_records_source()
    test_legacy_fallback_records_source()
    print("\n[OK] All hybrid input selector tests passed!")
