import pytest
from scientra.release.large_file_scanner import LargeFileScanner
class TestLarge:
    def test_scan(self): r = LargeFileScanner(max_mb=1).scan(); assert isinstance(r, list)
