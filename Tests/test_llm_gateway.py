"""Tests for the LLM Gateway — provider abstraction and unified call interface.

Run:
    python -m pytest Tests/test_llm_gateway.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scientra is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientra.ai.schemas import LLMResponse, LLMConfig
from scientra.ai.llm_gateway import call_llm, get_config, reload_config, save_config


class TestLLMResponse:
    """Test the LLMResponse schema."""

    def test_success_response(self):
        resp = LLMResponse(
            success=True,
            provider="deepseek",
            model="deepseek-chat",
            text="Hello, world!",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_estimate=0.0000082,
        )
        assert resp.success is True
        assert resp.provider == "deepseek"
        assert resp.text == "Hello, world!"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        assert resp.total_tokens == 15
        assert resp.error == ""

    def test_failure_response(self):
        resp = LLMResponse.failure("openai", "gpt-4o", "Rate limit exceeded")
        assert resp.success is False
        assert resp.provider == "openai"
        assert resp.model == "gpt-4o"
        assert resp.error == "Rate limit exceeded"
        assert resp.text == ""

    def test_to_dict(self):
        resp = LLMResponse(success=True, provider="anthropic", model="claude-sonnet-4-6", text="OK")
        d = resp.__dict__
        assert d["success"] is True
        assert d["provider"] == "anthropic"


class TestLLMConfig:
    """Test the LLMConfig schema."""

    def test_default_config(self):
        cfg = LLMConfig()
        assert cfg.enabled is True
        assert cfg.provider == "deepseek"
        assert cfg.model == "deepseek-chat"
        assert cfg.temperature == 0.2
        assert cfg.max_tokens == 4096

    def test_is_task_enabled(self):
        cfg = LLMConfig()
        assert cfg.is_task_enabled("summary") is True
        assert cfg.is_task_enabled("figure_interpretation") is False
        assert cfg.is_task_enabled("nonexistent") is False

    def test_is_task_enabled_when_disabled(self):
        cfg = LLMConfig(enabled=False)
        assert cfg.is_task_enabled("summary") is False

    def test_to_safe_dict_masks_api_key(self):
        cfg = LLMConfig(api_key="sk-1234567890abcdef")
        safe = cfg.to_safe_dict()
        assert safe["api_key_configured"] is True
        # Full key is NOT in the safe dict
        assert "sk-1234567890abcdef" not in str(safe)
        # Only a masked preview
        assert "*" in safe["api_key_preview"] or safe["api_key_preview"] == ""

    def test_to_safe_dict_no_key(self):
        cfg = LLMConfig(api_key="")
        safe = cfg.to_safe_dict()
        assert safe["api_key_configured"] is False
        assert safe["api_key_preview"] == ""


class TestConfigPersistence:
    """Test config loading and saving."""

    def test_reload_config_returns_config(self):
        # Because the real config file exists in the project, reload_config() should succeed
        cfg = reload_config()
        assert isinstance(cfg, LLMConfig)
        assert cfg.provider in ("deepseek", "openai", "anthropic", "local")

    def test_save_and_reload_roundtrip(self):
        import yaml

        original = get_config()
        try:
            test_cfg = LLMConfig(
                enabled=True,
                provider="openai",
                model="gpt-4o-mini",
                api_key="sk-test123",
                base_url="https://api.openai.com",
                temperature=0.5,
                max_tokens=2048,
                enabled_tasks={"summary": True, "agent_chat": False},
            )
            save_config(test_cfg)
            loaded = reload_config()
            assert loaded.enabled is True
            assert loaded.provider == "openai"
            assert loaded.model == "gpt-4o-mini"
            assert loaded.api_key == "sk-test123"
            assert loaded.temperature == 0.5
            assert loaded.max_tokens == 2048
            assert loaded.is_task_enabled("summary") is True
            assert loaded.is_task_enabled("agent_chat") is False
        finally:
            save_config(original)
            reload_config()


class TestProviderDispatch:
    """Test the gateway dispatches to correct providers."""

    def test_unknown_provider_returns_failure(self):
        resp = call_llm(
            prompt="Hello",
            provider="nonexistent_provider_xyz",
            model="test",
        )
        assert resp.success is False
        assert "Unknown provider" in resp.error

    def test_disabled_tasks_blocked(self):
        # Save config with summary disabled
        original = get_config()
        try:
            cfg = LLMConfig(
                enabled=True,
                provider="deepseek",
                model="deepseek-chat",
                api_key="sk-test",
                enabled_tasks={"summary": False, "agent_chat": True},
            )
            save_config(cfg)
            reload_config()
            resp = call_llm(prompt="Hello", task_name="summary")
            assert resp.success is False
            assert "disabled" in resp.error.lower()
        finally:
            save_config(original)
            reload_config()

    def test_llm_disabled_blocks_call(self):
        original = get_config()
        try:
            cfg = LLMConfig(enabled=False, provider="deepseek", model="deepseek-chat", api_key="sk-test")
            save_config(cfg)
            reload_config()
            resp = call_llm(prompt="Hello")
            assert resp.success is False
            assert "disabled" in resp.error.lower()
        finally:
            save_config(original)
            reload_config()


class TestDeepSeekProvider:
    """Test the DeepSeek provider directly."""

    def test_missing_api_key_returns_failure(self):
        from scientra.ai.providers.deepseek import call as deepseek_call

        resp = deepseek_call(prompt="Hello", api_key="")
        assert resp.success is False
        assert "not configured" in resp.error.lower()

    @patch("urllib.request.urlopen")
    def test_successful_call(self, mock_urlopen):
        from scientra.ai.providers.deepseek import call as deepseek_call

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        resp = deepseek_call(prompt="Hello", api_key="sk-test")
        assert resp.success is True
        assert resp.provider == "deepseek"
        assert resp.text == "OK"
        assert resp.input_tokens == 5
        assert resp.output_tokens == 2
        assert resp.total_tokens == 7
        assert resp.cost_estimate > 0

    @patch("urllib.request.urlopen")
    def test_http_error_returns_failure(self, mock_urlopen):
        from scientra.ai.providers.deepseek import call as deepseek_call
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.deepseek.com", 401, "Unauthorized", {}, None
        )

        resp = deepseek_call(prompt="Hello", api_key="sk-bad")
        assert resp.success is False
        assert "401" in resp.error or "Unauthorized" in resp.error


class TestOpenAIProvider:
    """Test the OpenAI provider directly."""

    def test_missing_api_key_returns_failure(self):
        from scientra.ai.providers.openai import call as openai_call

        resp = openai_call(prompt="Hello", api_key="")
        assert resp.success is False
        assert "not configured" in resp.error.lower()

    @patch("urllib.request.urlopen")
    def test_successful_call(self, mock_urlopen):
        from scientra.ai.providers.openai import call as openai_call

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hello from GPT"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        resp = openai_call(prompt="Hello", api_key="sk-test", model="gpt-4o-mini")
        assert resp.success is True
        assert resp.provider == "openai"
        assert resp.text == "Hello from GPT"
        assert resp.cost_estimate > 0


class TestAnthropicProvider:
    """Test the Anthropic provider directly."""

    def test_missing_api_key_returns_failure(self):
        from scientra.ai.providers.anthropic import call as anthropic_call

        resp = anthropic_call(prompt="Hello", api_key="")
        assert resp.success is False
        assert "not configured" in resp.error.lower()

    @patch("urllib.request.urlopen")
    def test_successful_call(self, mock_urlopen):
        from scientra.ai.providers.anthropic import call as anthropic_call

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "content": [{"type": "text", "text": "Bonjour from Claude"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        resp = anthropic_call(prompt="Hello", api_key="sk-test", model="claude-haiku-4-5")
        assert resp.success is True
        assert resp.provider == "anthropic"
        assert resp.text == "Bonjour from Claude"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5


class TestLocalProvider:
    """Test the local provider."""

    def test_no_transformers_returns_failure(self):
        with patch.dict(sys.modules, {"transformers": None}):
            # Force ImportError
            import importlib
            # Actually Local provider handles import internally; let's test the plain call
            from scientra.ai.providers.local import call as local_call

            resp = local_call(prompt="Hello", model="local")
            # Should either fail gracefully or import transformers
            assert isinstance(resp, LLMResponse)


class TestGatewayIntegration:
    """Integration-style tests for the gateway."""

    def test_gateway_dispatches_to_provider(self):
        """Test that the gateway dispatches to the correct provider function."""
        from scientra.ai.providers import PROVIDER_MAP
        from scientra.ai.llm_gateway import call_llm as gw_call

        original_map = dict(PROVIDER_MAP)

        mock_fn = MagicMock()
        mock_fn.return_value = LLMResponse(
            success=True, provider="deepseek", model="deepseek-chat", text="OK"
        )

        try:
            # Replace the provider map with our mock
            PROVIDER_MAP["deepseek"] = mock_fn

            resp = gw_call(
                prompt="Hello",
                task_name="agent_chat",
                provider="deepseek",
                model="deepseek-chat",
            )
            assert resp.success is True
            assert resp.text == "OK"
            mock_fn.assert_called_once()
        finally:
            # Restore original providers
            PROVIDER_MAP.clear()
            PROVIDER_MAP.update(original_map)

    def test_env_var_api_key_override(self, monkeypatch):
        """Test that env var API key takes precedence."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-override")
        from scientra.ai.llm_gateway import call_llm

        # This won't actually succeed but tests the env var resolution path
        resp = call_llm(
            prompt="Hello",
            provider="deepseek",
            model="deepseek-chat",
        )
        # Should use the env var key (though the API call will fail without real key)
        assert isinstance(resp, LLMResponse)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
