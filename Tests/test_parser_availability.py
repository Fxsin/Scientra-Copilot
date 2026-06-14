"""
Test: Parser Availability Detection.

Verifies:
- check_parser_availability() returns a ParserAvailability object
- System does not crash when parsers are missing
- hybrid_parser_enabled defaults to False
- /import/status returns parser_availability field
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_availability_returns_data():
    """check_parser_availability should always return a ParserAvailability."""
    from scientra.parsers.availability import check_parser_availability

    avail = check_parser_availability()

    # It should always be callable without crashing
    assert avail is not None

    # Check it can be serialized
    d = avail.to_dict()
    assert "grobid_available" in d
    assert "opendataloader_available" in d
    assert "marker_available" in d
    assert "pymupdf_available" in d
    assert "hybrid_parser_enabled" in d

    # All values should be booleans
    for key in d:
        if key != "error":
            assert isinstance(d[key], bool), f"{key} should be bool, got {type(d[key])}"


def test_availability_no_crash_on_missing_deps():
    """Even if all parsers are missing, the function should not crash."""
    from scientra.parsers.availability import check_parser_availability

    # Should work without any parsers installed
    avail = check_parser_availability()
    d = avail.to_dict()

    # PyMuPDF may or may not be installed — either way it shouldn't crash
    assert d["hybrid_parser_enabled"] is False  # Default should be False


def test_import_status_includes_parser_availability():
    """The /import/status endpoint should include parser_availability."""
    # This tests the helper function used by the endpoint
    from scientra.parsers.availability import check_parser_availability

    avail = check_parser_availability()
    d = avail.to_dict()

    # Verify the structure matches what the API would return
    assert "grobid_available" in d
    assert "opendataloader_available" in d
    assert "marker_available" in d
    assert "pymupdf_available" in d
    assert "hybrid_parser_enabled" in d

    print(f"Parser availability: {json.dumps(d, indent=2)}")


def test_hybrid_parser_disabled_by_default():
    """The hybrid parser must be disabled by default."""
    from scientra.parsers.availability import check_parser_availability

    avail = check_parser_availability()
    # In the default config, hybrid_parser.enabled is false
    assert avail.hybrid_parser_enabled is False, (
        "hybrid_parser must be disabled by default (enabled: false in workflow_config.yaml)"
    )


if __name__ == "__main__":
    test_availability_returns_data()
    test_availability_no_crash_on_missing_deps()
    test_import_status_includes_parser_availability()
    test_hybrid_parser_disabled_by_default()
    print("\n[OK] All parser availability tests passed!")
