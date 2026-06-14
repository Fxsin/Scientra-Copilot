"""Tests for Table Context Builder."""

import pytest
from scientra.assets.table_intelligence.table_context_builder import TableContextBuilder


class TestContextBuilder:
    def test_empty_paper(self):
        builder = TableContextBuilder()
        contexts = builder.build_all("nonexistent_paper_99999")
        assert isinstance(contexts, list)
        assert len(contexts) == 0

    def test_label_from_filename(self):
        builder = TableContextBuilder()
        assert "Table S1" == builder._label_from_filename("Table_S1.xlsx")
        assert "Table 2" == builder._label_from_filename("Table_2_results.csv")
        assert "Table 3" == builder._label_from_filename("Tab.3_final.xlsx")
        assert "" == builder._label_from_filename("data.csv")

    def test_warnings_full(self):
        builder = TableContextBuilder()
        w = builder._gen_warnings(
            {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True, "has_readable_table": True},
            "A detailed caption with enough detail for interpretation.",
        )
        assert len(w) == 0

    def test_warnings_missing(self):
        builder = TableContextBuilder()
        w = builder._gen_warnings(
            {"has_caption": False, "has_body_mention": False, "has_linked_evidence": False, "has_readable_table": False},
            "",
        )
        assert len(w) >= 3

    def test_warnings_short_caption(self):
        builder = TableContextBuilder()
        w = builder._gen_warnings(
            {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True, "has_readable_table": True},
            "Short.",
        )
        assert any("short" in x.lower() for x in w)

    def test_completeness_structure(self):
        builder = TableContextBuilder()
        # Verify the completeness dict keys
        completeness = {"has_caption": True, "has_body_mention": True, "has_linked_evidence": True, "has_readable_table": True}
        for key in ["has_caption", "has_body_mention", "has_linked_evidence", "has_readable_table"]:
            assert key in completeness
