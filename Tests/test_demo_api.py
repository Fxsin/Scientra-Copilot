import json, pytest
from scientra.demo import DemoStatusChecker, DemoQueryRunner, DemoManifestBuilder
class TestAPI:
    def test_no_db_v2(self): assert "DB/DB_v2" not in str(DemoStatusChecker().root)
    def test_synthetic_warning(self): assert "SYNTHETIC" in DemoStatusChecker().check()["warning"]
    def test_manifest(self): assert DemoManifestBuilder().build()["synthetic"]
    def test_queries_no_agent(self):
        r = DemoQueryRunner().run(use_agent=False)
        assert "results" in r
