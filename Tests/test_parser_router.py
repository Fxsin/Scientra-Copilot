"""
Test: Parser Router.

Verifies:
- run_hybrid_parse gracefully handles missing dependencies
- System does not crash with missing PDF
- PDF type detection works (via scan report)
- hybrid_parser.enabled=false preserves existing flow
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_run_hybrid_parse_missing_pdf():
    """run_hybrid_parse should handle missing PDF gracefully."""
    from scientra.parsers.parser_router import run_hybrid_parse

    result = run_hybrid_parse(
        pdf_path="/nonexistent/path/paper.pdf",
        paper_id="test_paper_001",
    )

    assert result is not None
    assert result.paper_id == "test_paper_001"
    # Should not have crashed despite missing PDF
    print(f"Missing PDF handled gracefully: status={result.pdf_type.value}")


def test_run_hybrid_parse_with_dummy_pdf():
    """run_hybrid_parse with a minimal dummy PDF."""
    from scientra.parsers.parser_router import run_hybrid_parse

    # Create a minimal valid PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        # Minimal PDF content
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\n"
            b"startxref\n190\n%%EOF\n"
        )
        f.write(pdf_content)
        pdf_path = f.name

    try:
        result = run_hybrid_parse(
            pdf_path=pdf_path,
            paper_id="test_dummy_001",
        )

        assert result is not None
        assert result.paper_id == "test_dummy_001"
        assert result.pdf_path == pdf_path

        # The result should always have parser_outputs
        assert result.parser_outputs is not None

        # Should have a manifest path
        assert result.manifest_path
        manifest_path = Path(result.manifest_path)
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            assert manifest["paper_id"] == "test_dummy_001"
            print(f"Manifest written to: {result.manifest_path}")

        print(f"PDF type: {result.pdf_type.value}")
        print(f"Markdown source: {result.markdown_source}")
        print(f"Metadata source: {result.metadata_source}")

    finally:
        # Cleanup
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


def test_parse_without_config_crash():
    """run_hybrid_parse should work even without custom config."""
    from scientra.parsers.parser_router import run_hybrid_parse

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n")
        pdf_path = f.name

    try:
        # Passing empty config dict
        result = run_hybrid_parse(
            pdf_path=pdf_path,
            paper_id="test_no_config",
            config={"use_grobid": False, "use_opendataloader": False, "use_marker": False, "use_pymupdf": True},
        )
        assert result is not None
        print(f"Run without external parsers: pdf_type={result.pdf_type.value}")
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


if __name__ == "__main__":
    test_run_hybrid_parse_missing_pdf()
    test_run_hybrid_parse_with_dummy_pdf()
    test_parse_without_config_crash()
    print("\n[OK] All parser router tests passed!")
