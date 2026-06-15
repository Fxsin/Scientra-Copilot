import json, pytest
from scientra.validation.e2e import E2EValidationRunner
class TestRunner:
    def test_run_quick(self):
        r = E2EValidationRunner().run(skip_agent=True, skip_query=True, check_storage=False, check_db=False)
        assert "papers" in r; assert isinstance(r.get("p0_count"), int)
    def test_no_db_v2(self):
        assert "DB/DB_v2" not in str(E2EValidationRunner().out)
    def test_summary_no_data(self):
        r = E2EValidationRunner().get_summary()
        assert isinstance(r, dict)
