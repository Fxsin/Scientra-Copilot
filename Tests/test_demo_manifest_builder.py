import pytest
from scientra.demo.demo_manifest_builder import DemoManifestBuilder
class TestManifest:
    def test_build(self):
        m = DemoManifestBuilder().build()
        assert m.get("synthetic") is True; assert "paper_id" in m
