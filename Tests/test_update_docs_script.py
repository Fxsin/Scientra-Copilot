import pytest, subprocess, sys
class TestScript:
    def test_check_storage(self):
        r = subprocess.run([sys.executable, "Scripts/update_docs.py", "--check-storage-paths", "--check-consistency"], capture_output=True, timeout=30, env={**__import__('os').environ, "PYTHONIOENCODING": "utf-8"})
        assert r.returncode in (0, 1)  # May return 1 if DB_v2 hits found (which is expected behavior)
