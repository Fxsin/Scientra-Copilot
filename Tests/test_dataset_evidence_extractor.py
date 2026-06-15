import pytest
from scientra.datasets.intelligence.dataset_evidence_extractor import extract_evidence

class TestEvidence:
    def test_extract(self):
        schema = {"dataset_type": "differential_expression", "confidence": 0.9}
        entities = [{"entity_text": "MAP2K4", "entity_type": "gene", "row_index": 0, "column_name": "Gene", "confidence": 0.8}]
        numerics = {"top_positive": [{"entity": "MAP2K4", "value": 3.5}], "top_negative": [], "thresholds_detected": {"p_lt_0.05": 1}}
        ev = extract_evidence(schema, entities, numerics, "p1", "ds1", "a1")
        assert len(ev) >= 2
        assert any(e["evidence_type"] == "entity_presence" for e in ev)
