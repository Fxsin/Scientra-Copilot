import json
import pytest
from scientra.cross_asset_query import CrossAssetQueryEngine, make_query

class TestAPI:
    def test_result_json_serializable(self):
        engine = CrossAssetQueryEngine()
        result = engine.query(make_query("test", top_k=3))
        j = json.dumps(result, ensure_ascii=False)
        assert isinstance(j, str)

    def test_no_absolute_paths(self):
        engine = CrossAssetQueryEngine()
        result = engine.query(make_query("test", top_k=3))
        for h in result.get("hits", []):
            sp = h.get("source_relative_path", "")
            assert ":\\" not in sp, f"Absolute path found: {sp}"
            assert not sp.startswith("/"), f"Absolute Unix path: {sp}"

    def test_no_db_v2(self):
        from scientra.cross_asset_query.cross_asset_query_engine import CrossAssetQueryEngine
        engine = CrossAssetQueryEngine()
        assert "DB/DB_v2" not in str(engine.root)

    def test_warnings_on_missing(self):
        engine = CrossAssetQueryEngine()
        result = engine.query(make_query("test", top_k=3))
        assert isinstance(result.get("warnings"), list)
