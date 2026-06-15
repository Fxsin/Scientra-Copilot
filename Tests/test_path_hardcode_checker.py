import pytest
from scientra.release.path_hardcode_checker import PathHardcodeChecker
class TestPath:
    def test_scan(self): r = PathHardcodeChecker().scan(); assert isinstance(r, list)
    def test_no_db_v2(self): assert "DB/DB_v2" not in "Storage Layout v3"
