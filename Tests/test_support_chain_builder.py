import pytest
from scientra.cross_asset_query.support_chain_builder import SupportChainBuilder
from scientra.cross_asset_query.query_schema import make_hit

class TestChains:
    def test_build_no_graph(self):
        scb = SupportChainBuilder()
        hits = [make_hit("h1", "figure", "p1", "Fig 1", score=0.8)]
        chains = scb.build_chains(hits, None)
        assert isinstance(chains, list)

    def test_format_chain(self):
        chain = {"nodes": [{"node_id": "n1", "node_type": "claim", "title": "C"}], "edges": [{"source_node_id": "n1", "target_node_id": "n2", "edge_type": "supports"}]}
        result = SupportChainBuilder._format_chain(chain, "test")
        assert result["chain_type"] == "test"
        assert len(result["nodes"]) == 1
