"""Tests for P6.6.1 system API endpoints."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scientra.server import create_app


class TestSystemAPI:
    @pytest.fixture
    def client(self):
        """Client pointing to real project root (has Config)."""
        root = Path(__file__).resolve().parents[1]
        app = create_app(root)
        with TestClient(app) as c:
            yield c

    def test_health_endpoint(self, client):
        resp = client.get("/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert "health_score" in data
        assert "checks" in data
        assert 0 <= data["health_score"] <= 100

    def test_environment_endpoint(self, client):
        resp = client.get("/system/environment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert len(data["checks"]) == 12

    def test_startup_status_endpoint(self, client):
        resp = client.get("/system/startup-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_running" in data
        assert "web_running" in data
        assert "health_score" in data

    def test_health_score_in_range(self, client):
        resp = client.get("/system/health")
        data = resp.json()
        assert 0 <= data["health_score"] <= 100

    def test_checks_have_required_fields(self, client):
        resp = client.get("/system/health")
        data = resp.json()
        for c in data["checks"]:
            assert "name" in c
            assert "status" in c
            assert "detail" in c
            assert "fix" in c

    def test_no_absolute_paths(self, client):
        """API responses should not contain absolute paths."""
        for ep in ["/system/health", "/system/environment", "/system/startup-status"]:
            resp = client.get(ep)
            text = resp.text
            assert "C:\\" not in text
            assert "file:///" not in text

    def test_no_api_key_exposed(self, client):
        """API keys should be masked in responses."""
        resp = client.get("/system/health")
        data = resp.json()
        # Check API key check detail
        for c in data["checks"]:
            if c["name"] == "API Keys":
                detail = c.get("detail", "")
                # Should not contain the raw full key
                if "sk-" in detail:
                    # Must be masked (containing ...)
                    assert "..." in detail or detail == ""

    def test_no_db_v2_references(self, client):
        resp = client.get("/system/health")
        text = resp.text.lower()
        assert "db_v2" not in text


class TestSystemAPIEmpty:
    @pytest.fixture
    def empty_client(self):
        """Client pointing to empty dir."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(root)
            with TestClient(app) as c:
                yield c

    def test_health_works_with_empty_root(self, empty_client):
        resp = empty_client.get("/system/health")
        assert resp.status_code == 200  # Not 500
        data = resp.json()
        assert data["available"] is True

    def test_environment_works_with_empty_root(self, empty_client):
        resp = empty_client.get("/system/environment")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["checks"]) == 12

    def test_startup_status_works_with_empty_root(self, empty_client):
        resp = empty_client.get("/system/startup-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_running" in data
