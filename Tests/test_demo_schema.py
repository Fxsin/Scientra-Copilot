import pytest
from scientra.demo.demo_schema import make_demo_manifest, make_demo_status
class TestSchema:
    def test_manifest(self): assert make_demo_manifest()["synthetic"] is True
    def test_status(self):
        s = make_demo_status(files_exist=True, imported=True, pipeline_run=True, validated=True)
        assert s["ready_for_demo"]; assert s["files_exist"]
