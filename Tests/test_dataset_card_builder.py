import pytest
from scientra.datasets.intelligence.dataset_card_builder import build_card

class TestCard:
    def test_build(self):
        card = build_card(
            {"dataset_id": "ds1", "paper_id": "p1", "asset_id": "a1", "source_relative_path": "t.xlsx", "file_type": "xlsx"},
            {"dataset_type": "differential_expression", "confidence": 0.9, "key_columns": {}},
            {"n_rows": 100, "n_columns": 6, "sheets": [{}], "headers": ["G"]},
            [{"entity_text": "MAP2K4", "entity_type": "gene"}],
            {"numeric_columns": [{"field_type": "log2FC"}], "statistical_columns": [], "effect_size_columns": ["log2FC"]},
            [{"evidence_id": "e1", "entity_text": "MAP2K4"}],
            {"quality_score": 0.8, "warnings": []},
        )
        assert card["dataset_type"] == "differential_expression"
        assert card["n_rows"] == 100
        assert card["quality_score"] == 0.8
