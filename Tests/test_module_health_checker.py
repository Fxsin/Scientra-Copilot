import pytest
from scientra.validation.e2e.module_health_checker import ModuleHealthChecker
class TestHealth:
    def test_check(self):
        r = ModuleHealthChecker().check()
        assert "modules" in r; assert "scripts" in r; assert "all_modules_ok" in r
