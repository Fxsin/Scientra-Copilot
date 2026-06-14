import pytest
from scientra.cross_asset_query.cross_asset_input_loader import CrossAssetInputLoader

class TestLoader:
    def test_load_all_no_crash(self):
        loader = CrossAssetInputLoader()
        data = loader.load_all()
        assert isinstance(data, dict)
        for k in ["evidence", "figure", "table", "supplementary", "graph", "gap", "hypothesis"]:
            assert k in data

    def test_load_graph(self):
        loader = CrossAssetInputLoader()
        nodes = loader._load_graph_nodes()
        assert isinstance(nodes, list)
