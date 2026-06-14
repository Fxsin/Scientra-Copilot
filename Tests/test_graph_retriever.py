import pytest
from scientra.cross_asset_query.graph_retriever import GraphRetriever

class TestGraph:
    def test_availability(self):
        gr = GraphRetriever()
        assert isinstance(gr.is_available(), bool)

    def test_search_no_crash(self):
        gr = GraphRetriever()
        hits = gr.search_nodes("test")
        assert isinstance(hits, list)

    def test_support_chain_no_crash(self):
        gr = GraphRetriever()
        chain = gr.get_support_chain("nonexistent")
        assert chain is None or isinstance(chain, dict)
