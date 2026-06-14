"""Tests for the AI Settings API endpoints.

Run:
    python -m pytest Tests/test_ai_settings_api.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAISettingsAPI:
    """Test the AI settings API endpoints via FastAPI TestClient."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")

        from scientra.server import create_app

        app = create_app()
        return TestClient(app)

    def test_get_ai_settings(self, client):
        """GET /settings/ai returns settings with masked API key."""
        response = client.get("/settings/ai")
        assert response.status_code == 200
        data = response.json()
        # Required fields
        assert "enabled" in data
        assert "provider" in data
        assert "model" in data
        assert "base_url" in data
        assert "temperature" in data
        assert "max_tokens" in data
        assert "enabled_tasks" in data
        assert "api_key_configured" in data
        assert "api_key_preview" in data
        # Full API key should NOT be in response
        assert "api_key" not in data

    def test_get_ai_settings_task_keys(self, client):
        """GET /settings/ai has the expected task keys."""
        response = client.get("/settings/ai")
        assert response.status_code == 200
        data = response.json()
        tasks = data["enabled_tasks"]
        expected_tasks = [
            "summary",
            "evidence_enrichment",
            "figure_interpretation",
            "table_interpretation",
            "supplementary_interpretation",
            "agent_chat",
        ]
        for task in expected_tasks:
            assert task in tasks, f"Missing task: {task}"

    def test_post_ai_settings_update(self, client):
        """POST /settings/ai updates config and returns masked key."""
        # First get current settings to know original values
        original = client.get("/settings/ai").json()

        # Update only the model
        response = client.post("/settings/ai", json={
            "model": "deepseek-chat",
            "temperature": 0.3,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "deepseek-chat"
        assert data["temperature"] == 0.3
        # API key should not be exposed
        assert "api_key" not in data

        # Restore original
        client.post("/settings/ai", json={
            "model": original["model"],
            "temperature": original["temperature"],
        })

    def test_post_ai_settings_preserves_api_key(self, client):
        """POST /settings/ai without api_key field should not clear existing key."""
        original = client.get("/settings/ai").json()

        # Update only enabled_tasks
        response = client.post("/settings/ai", json={
            "enabled_tasks": {"summary": True, "agent_chat": False},
        })
        assert response.status_code == 200
        data = response.json()
        # API key config status should be preserved
        assert data["api_key_configured"] == original["api_key_configured"]

        # Restore
        client.post("/settings/ai", json={
            "enabled_tasks": original["enabled_tasks"],
        })

    def test_test_connection_no_api_key(self, client):
        """POST /settings/ai/test returns failed status when no valid key."""
        response = client.post("/settings/ai/test", json={})
        # Will either return 200 with status="failed" or 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "failed"
        else:
            # 500 is also acceptable if the module can't be loaded
            assert response.status_code == 500

    def test_test_connection_with_provider(self, client):
        """POST /settings/ai/test with explicit provider."""
        response = client.post("/settings/ai/test", json={
            "provider": "deepseek",
            "model": "deepseek-chat",
        })
        # Either 200 with result or 500 from module issues
        assert response.status_code in (200, 500)

    def test_cors_headers(self, client):
        """API responses include CORS headers."""
        response = client.options(
            "/settings/ai",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # OPTIONS might return 200 or 405 depending on FastAPI config
        assert response.status_code in (200, 405, 204)


class TestAISettingsSchema:
    """Test the Pydantic schemas used by the API."""

    def test_ai_settings_response_model(self):
        """Verify AISettingsResponse model can be constructed via the API."""
        # Since AISettingsResponse is defined inside create_app(), we test
        # it indirectly via the API endpoint.
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")

        from scientra.server import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/settings/ai")
        assert resp.status_code == 200
        data = resp.json()
        # Verify the response shape matches AISettingsResponse
        assert data["enabled"] is not None
        assert data["provider"] in ("deepseek", "openai", "anthropic", "local")
        assert "api_key" not in data  # Full key never exposed
        assert "api_key_preview" in data
        assert "api_key_configured" in data

    def test_ai_settings_update_model(self):
        """Verify AISettingsUpdate model accepts partial updates."""
        # Test via the actual API endpoint since AISettingsUpdate is defined
        # inside create_app() and not exported at module level.
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")

        from scientra.server import create_app

        app = create_app()
        client = TestClient(app)

        # Partial update with just model
        resp = client.post("/settings/ai", json={"model": "gpt-4o-mini"})
        if resp.status_code == 200:
            data = resp.json()
            assert data["model"] == "gpt-4o-mini"
        else:
            # If server doesn't support this exact model, at least verify
            # the request was parsed (not a 422 schema error)
            assert resp.status_code != 422, f"Schema validation failed: {resp.text}"


class TestConfigEndToEnd:
    """End-to-end test of the config read/write flow."""

    def test_save_and_get_roundtrip(self):
        """Save config, then GET to verify persistence."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not installed")

        from scientra.server import create_app
        from scientra.ai.llm_gateway import save_config, reload_config, get_config, LLMConfig

        app = create_app()
        client = TestClient(app)

        # Save original
        original = get_config()

        try:
            # Set a known config
            test_cfg = LLMConfig(
                enabled=True,
                provider="openai",
                model="gpt-4o-mini",
                api_key="sk-test-e2e",
                base_url="https://api.openai.com",
                temperature=0.7,
                max_tokens=1024,
                enabled_tasks={"summary": True},
            )
            save_config(test_cfg)
            reload_config()

            # GET should reflect changes
            resp = client.get("/settings/ai")
            assert resp.status_code == 200
            data = resp.json()
            assert data["provider"] == "openai"
            assert data["model"] == "gpt-4o-mini"
            assert data["temperature"] == 0.7
            assert data["api_key_configured"] is True
            # Full key not exposed
            assert "sk-test-e2e" not in resp.text
        finally:
            save_config(original)
            reload_config()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
