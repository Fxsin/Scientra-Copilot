import pytest
from scientra.cross_asset_query.vector_retriever import VectorRetriever

class TestVector:
    def test_availability_check(self):
        vr = VectorRetriever()
        avail = vr.is_available()
        assert isinstance(avail, bool)

    def test_search_no_crash(self):
        vr = VectorRetriever()
        hits = vr.search("test query")
        assert isinstance(hits, list)

    def test_warnings_on_unavailable(self):
        vr = VectorRetriever()
        if not vr.is_available():
            vr.search("test")
            assert any("available" in w.lower() or "embedding" in w.lower() for w in vr.warnings)
