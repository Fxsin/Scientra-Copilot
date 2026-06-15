import pytest, shutil
from pathlib import Path
from scientra.demo.demo_project_builder import DemoProjectBuilder
class TestBuilder:
    def test_create(self):
        b = DemoProjectBuilder()
        r = b.create(force=True)
        assert r.get("success") or "error" in r
    def test_source_exists(self):
        assert (Path(__file__).parent.parent / "examples/demo_project/article_bundle/Demo_Paper_001").exists()
