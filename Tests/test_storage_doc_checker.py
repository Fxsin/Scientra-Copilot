import pytest
from scientra.docs_tools.storage_doc_checker import StorageDocChecker
class TestStorage:
    def test_check(self):
        r = StorageDocChecker().check()
        assert "clean" in r; assert "db_v2_hits" in r
    def test_no_db_v2_in_this_file(self):
        assert "DB/DB_v2" not in "Storage Layout v3 is used"
