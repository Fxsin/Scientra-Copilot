import pytest
from scientra.release.storage_safety_checker import StorageSafetyChecker
class TestStorage:
    def test_check(self): r = StorageSafetyChecker().check(); assert isinstance(r, list)
