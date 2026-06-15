import pytest
from scientra.validation.dashboard.dashboard_data_loader import DashboardDataLoader
class TestLoader:
    def test_availability(self):
        loader = DashboardDataLoader()
        assert isinstance(loader.is_available(), bool)
    def test_load_empty(self):
        loader = DashboardDataLoader()
        data = loader.load_all()
        assert isinstance(data, dict); assert "summary" in data
