import pytest
from scientra.cross_asset_query.query_intent_classifier import classify_intent, get_target_asset_types

class TestIntent:
    def test_entity_search(self):
        r = classify_intent("MAP2K4 expression")
        assert r["primary_intent"] in ("entity_search", "expression_search")

    def test_claim_support(self):
        r = classify_intent("which figures support claims about receptor binding")
        assert r["primary_intent"] in ("claim_support_search", "figure_search")

    def test_table_search(self):
        r = classify_intent("gene expression supplementary tables")
        assert r["primary_intent"] in ("supplementary_search", "table_search", "expression_search")

    def test_bioassay(self):
        r = classify_intent("LC50 bioassay results for Cry toxin")
        assert r["primary_intent"] in ("bioassay_search", "entity_search")

    def test_get_target_assets(self):
        assets = get_target_asset_types("claim_support_search")
        assert "evidence" in assets or "figure" in assets or "graph" in assets

    def test_unknown_defaults(self):
        r = classify_intent("hello world")
        assert r["confidence"] > 0
