import pytest
from scientra.docs_tools.docs_consistency_checker import DocsConsistencyChecker
class TestConsistency:
    def test_check(self):
        r = DocsConsistencyChecker().check()
        assert "all_docs_exist" in r; assert "missing_docs" in r
