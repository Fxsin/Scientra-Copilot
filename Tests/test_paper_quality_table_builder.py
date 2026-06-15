import pytest
from scientra.validation.dashboard.paper_quality_table_builder import PaperQualityTableBuilder
class TestTable:
    def test_sort(self):
        papers = [{"paper_id": "a", "completion_score": 0.3, "warnings": []}, {"paper_id": "b", "completion_score": 0.9, "warnings": []}]
        r = PaperQualityTableBuilder().build(papers, sort_by="completion_score")
        assert r[0]["paper_id"] == "b"
    def test_filter_warnings(self):
        papers = [{"paper_id": "a", "completion_score": 0.5, "warnings": ["w1"]}, {"paper_id": "b", "completion_score": 0.5, "warnings": []}]
        r = PaperQualityTableBuilder().build(papers, filter_warnings=True)
        assert len(r) == 1; assert r[0]["paper_id"] == "a"
    def test_search(self):
        r = PaperQualityTableBuilder().build([{"paper_id": "paper_abc", "completion_score": 0.5}], search="abc")
        assert len(r) == 1
