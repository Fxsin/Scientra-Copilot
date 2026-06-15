import pytest
from scientra.validation.e2e.pipeline_inventory import PipelineInventory
class TestInventory:
    def test_scan(self):
        inv = PipelineInventory().scan()
        assert "03_assets" in inv; assert "05_knowledge" in inv
    def test_no_db_v2(self):
        assert "DB/DB_v2" not in str(PipelineInventory().root)
