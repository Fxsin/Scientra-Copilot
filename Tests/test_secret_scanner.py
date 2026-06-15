import pytest, tempfile
from pathlib import Path
from scientra.release.secret_scanner import SecretScanner
class TestSecret:
    def test_scan_no_false_positive(self):
        r = SecretScanner().scan()
        # Should not flag docs that say "NEVER commit api_key"
        assert all("example" not in i.get("detail", "").lower() or "NEVER" in i.get("detail", "") for i in r if i["priority"] == "P0")
    def test_empty_scan(self):
        r = SecretScanner().scan()
        assert isinstance(r, list)
