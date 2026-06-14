"""Unified LLM Gateway — single entry point for all AI calls.

Usage:
    from scientra.ai import call_llm

    response = call_llm(
        prompt="Summarize this paper...",
        task_name="summary",
        provider="deepseek",
        model="deepseek-chat",
        temperature=0.2,
        max_tokens=4096,
    )

    if response.success:
        print(response.text)
    else:
        print(f"Error: {response.error}")
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scientra.ai.providers import PROVIDER_MAP
from scientra.ai.schemas import LLMConfig, LLMResponse
from scientra.ai.cost_tracker import log_usage

# ── Config Resolution ──


def _detect_project_root() -> Path:
    """Walk up from this file until Config/llm_config.yaml is found."""
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "Config" / "llm_config.yaml").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _detect_project_root()
CONFIG_PATH = PROJECT_ROOT / "Config" / "llm_config.yaml"

# In-memory cached config — call reload_config() to refresh
_config_cache: LLMConfig | None = None


def _load_config_from_file() -> dict[str, Any]:
    """Load raw config dict from YAML file."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return {}
        return raw
    except Exception:
        return {}


def get_config() -> LLMConfig:
    """Get current LLM configuration (cached)."""
    global _config_cache
    if _config_cache is None:
        reload_config()
    return _config_cache  # type: ignore[return-value]


def reload_config() -> LLMConfig:
    """Reload configuration from disk."""
    global _config_cache
    raw = _load_config_from_file()

    _config_cache = LLMConfig(
        enabled=raw.get("enabled", True),
        provider=raw.get("provider", "deepseek"),
        model=raw.get("model", "deepseek-chat"),
        api_key=raw.get("api_key", ""),
        base_url=raw.get("base_url", ""),
        temperature=float(raw.get("temperature", 0.2)),
        max_tokens=int(raw.get("max_tokens", 4096)),
        enabled_tasks=raw.get("enabled_tasks", {
            "summary": True,
            "evidence_enrichment": False,
            "figure_interpretation": False,
            "table_interpretation": False,
            "supplementary_interpretation": False,
            "agent_chat": True,
        }),
    )
    return _config_cache


def save_config(config: LLMConfig) -> None:
    """Save configuration to disk and reload cache."""
    global _config_cache
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "enabled": config.enabled,
        "provider": config.provider,
        "model": config.model,
        "api_key": config.api_key,
        "base_url": config.base_url,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "enabled_tasks": config.enabled_tasks,
    }
    CONFIG_PATH.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    _config_cache = config


# ── Gateway ──


def call_llm(
    prompt: str,
    task_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    system_prompt: str = "",
    paper_id: str | None = None,
) -> LLMResponse:
    """Call an LLM through the unified gateway.

    Args:
        prompt: The user prompt text.
        task_name: Logical task name (e.g. "summary", "agent_chat"). Used for
                   cost tracking and task-gating.
        provider: Override configured provider.
        model: Override configured model.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        system_prompt: Optional system-level instruction.
        paper_id: Optional paper identifier for usage tracking.

    Returns:
        LLMResponse — always succeeds at the call level. Check response.success
        to determine if the actual LLM call succeeded.
    """
    config = get_config()

    # Resolve provider
    resolved_provider = provider or config.provider
    resolved_model = model or config.model
    resolved_base_url = config.base_url
    resolved_api_key = config.api_key

    # Allow environment variable override per provider
    env_key_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    if resolved_provider in env_key_map:
        env_key = os.environ.get(env_key_map[resolved_provider])
        if env_key:
            resolved_api_key = env_key

    # Override base_url from env if set
    env_url_map = {
        "deepseek": "DEEPSEEK_BASE_URL",
        "openai": "OPENAI_BASE_URL",
        "anthropic": "ANTHROPIC_BASE_URL",
    }
    if resolved_provider in env_url_map:
        env_url = os.environ.get(env_url_map[resolved_provider])
        if env_url:
            resolved_base_url = env_url

    # Task gate check
    if task_name and not config.is_task_enabled(task_name):
        return LLMResponse.failure(
            resolved_provider,
            resolved_model,
            f"Task '{task_name}' is disabled in llm_config.yaml → enabled_tasks",
        )

    if not config.enabled:
        return LLMResponse.failure(
            resolved_provider,
            resolved_model,
            "LLM is disabled in llm_config.yaml (enabled: false)",
        )

    # Dispatch to provider
    provider_fn = PROVIDER_MAP.get(resolved_provider)
    if provider_fn is None:
        return LLMResponse.failure(
            resolved_provider,
            resolved_model,
            f"Unknown provider '{resolved_provider}'. Available: {list(PROVIDER_MAP)}",
        )

    # Allow task-level temperature/max_tokens from config
    resolved_temperature = temperature if temperature != 0.2 else config.temperature
    resolved_max_tokens = max_tokens if max_tokens != 4096 else config.max_tokens

    response = provider_fn(
        prompt=prompt,
        model=resolved_model,
        api_key=resolved_api_key,
        base_url=resolved_base_url or "",
        temperature=resolved_temperature,
        max_tokens=resolved_max_tokens,
        system_prompt=system_prompt,
    )

    # Log usage regardless of success/failure
    log_usage(
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=resolved_provider,
        model=resolved_model,
        task_name=task_name or "unknown",
        paper_id=paper_id or "",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        cost_estimate=response.cost_estimate,
        success=response.success,
        error=response.error if not response.success else "",
    )

    return response


def test_connection(provider: str | None = None) -> LLMResponse:
    """Test the LLM connection with a minimal ping prompt.

    Returns an LLMResponse. If success=True, the connection works.
    """
    resolved_provider = provider or get_config().provider
    return call_llm(
        prompt="Reply with exactly: OK",
        task_name="connection_test",
        provider=resolved_provider,
        max_tokens=10,
        temperature=0.0,
    )
