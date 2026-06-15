import pytest
from scientra.validation.e2e.storage_layout_validator import StorageLayoutValidator
class TestValidator:
    def test_validate(self):
        r = StorageLayoutValidator().validate()
        assert "v3_compliant" in r; assert "db_v2_clean" in r
    def test_no_db_v2_in_this_file(self):
        assert "DB/DB_v2" not in "Storage Layout v3"
