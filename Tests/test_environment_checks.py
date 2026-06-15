"""Tests for P6.6.1 environment checks."""

import tempfile
from pathlib import Path

from scientra.environment.checks import (
    check_python_version, check_node, check_git, check_disk_space,
    check_ram, check_cpu, check_gpu, check_dependencies,
    check_lancedb, check_bge_m3, check_api_keys, check_ports,
    run_all_checks, mask_key,
)


class TestPythonCheck:
    def test_python_version(self):
        result = check_python_version()
        assert result["name"] == "Python"
        assert result["status"] in ("PASS", "FAIL", "WARN")
        assert result["detail"]

    def test_python_pass(self):
        result = check_python_version()
        # Our environment should be 3.11+
        assert result["status"] == "PASS"


class TestNodeCheck:
    def test_node_check_no_crash(self):
        result = check_node()
        assert result["name"] == "Node.js"
        assert result["status"] in ("PASS", "WARN", "FAIL")


class TestGitCheck:
    def test_git_check_no_crash(self):
        result = check_git()
        assert result["name"] == "Git"
        assert result["status"] in ("PASS", "WARN", "FAIL")


class TestDiskCheck:
    def test_disk_space(self):
        result = check_disk_space(min_gb=1)
        assert result["name"] == "Disk Space"
        # With min_gb=1 it should always pass
        assert result["status"] in ("PASS", "WARN")

    def test_disk_space_unrealistic(self):
        result = check_disk_space(min_gb=99999)
        assert result["status"] == "WARN"


class TestRAMCheck:
    def test_ram_no_crash(self):
        result = check_ram()
        assert result["name"] == "RAM"
        assert result["status"] in ("PASS", "WARN", "FAIL", "INFO")


class TestCPUCheck:
    def test_cpu_no_crash(self):
        result = check_cpu()
        assert result["name"] == "CPU"
        assert result["status"] in ("PASS", "WARN", "INFO")


class TestGPUCheck:
    def test_gpu_no_crash(self):
        result = check_gpu()
        assert result["name"] == "GPU"
        # GPU may or may not be available — both are fine
        assert result["status"] in ("PASS", "WARN")


class TestDependenciesCheck:
    def test_dependencies(self):
        result = check_dependencies()
        assert result["name"] == "Dependencies"
        # In our test environment, dependencies should be installed
        assert result["status"] in ("PASS", "WARN")

    def test_dependencies_returns_detail(self):
        result = check_dependencies()
        assert "detail" in result
        assert "fix" in result


class TestLanceDBCheck:
    def test_lancedb_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = check_lancedb(root)
            assert result["name"] == "LanceDB"
            assert result["status"] in ("PASS", "WARN", "FAIL")

    def test_lancedb_missing_dir_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = check_lancedb(root)
            # No data = WARN, not FAIL
            assert result["status"] != "FAIL" or "lancedb package not installed" in result.get("detail", "")


class TestBGECheck:
    def test_bge_m3_no_crash(self):
        result = check_bge_m3()
        assert result["name"] == "BGE-M3 Model"
        assert result["status"] in ("PASS", "WARN")


class TestAPIKeyCheck:
    def test_api_keys_missing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = check_api_keys(root)
            assert result["name"] == "API Keys"
            # Missing config = WARN
            assert result["status"] == "WARN"

    def test_api_keys_with_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "Config"
            config_dir.mkdir()
            import yaml
            config = {"provider": "deepseek", "api_key": "sk-test12345678", "model": "deepseek-chat", "enabled": True}
            (config_dir / "llm_config.yaml").write_text(yaml.dump(config), encoding="utf-8")
            result = check_api_keys(root)
            assert result["status"] == "PASS"
            # Key should be masked
            assert "test12345678" not in result["detail"]


class TestPortCheck:
    def test_ports_no_crash(self):
        result = check_ports()
        assert result["name"] == "Ports"
        assert result["status"] in ("PASS", "WARN")


class TestMaskKey:
    def test_mask_key(self):
        assert mask_key("sk-1234567890abcdefgh") == "sk-123...efgh"

    def test_mask_short_key(self):
        assert mask_key("short") == "***"

    def test_mask_empty(self):
        assert mask_key("") == "(empty)"


class TestRunAllChecks:
    def test_run_all_checks(self):
        results = run_all_checks()
        assert len(results) == 12
        for r in results:
            assert "name" in r
            assert "status" in r
            assert "detail" in r
            assert "fix" in r

    def test_all_checks_have_valid_status(self):
        results = run_all_checks()
        for r in results:
            assert r["status"] in ("PASS", "WARN", "FAIL", "INFO")
