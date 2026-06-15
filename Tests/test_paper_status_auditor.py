import pytest
from scientra.validation.e2e.paper_status_auditor import PaperStatusAuditor
class TestAuditor:
    def test_audit_all(self):
        result = PaperStatusAuditor().audit_all()
        assert isinstance(result, list)
    def test_audit_one_structure(self):
        r = PaperStatusAuditor().audit_one("nonexistent_paper")
        assert "completion_score" in r; assert "warnings" in r
