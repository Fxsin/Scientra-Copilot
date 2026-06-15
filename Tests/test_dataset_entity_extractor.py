import pytest
from scientra.datasets.intelligence.dataset_entity_extractor import extract_entities

class TestEntity:
    def test_extract_entities(self):
        headers = ["Gene Symbol", "log2FC", "pvalue"]
        rows = [["MAP2K4", "2.5", "0.001"], ["Vip3Aa", "-1.3", "0.05"]]
        entities = extract_entities(headers, rows, "p1", "ds1", "a1")
        assert len(entities) >= 1

    def test_empty(self):
        entities = extract_entities([], [], "p1", "ds1", "a1")
        assert entities == []
