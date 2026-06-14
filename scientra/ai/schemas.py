"""Data schemas for the AI Enrichment Layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class LLMResponse:
    """Unified response from any LLM provider.

    On failure, success=False and error is populated.
    The caller never needs to catch exceptions.
    """

    success: bool
    provider: str
    model: str
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_estimate: float = 0.0
    error: str = ""
    raw_response: dict[str, Any] | None = None

    @classmethod
    def failure(cls, provider: str, model: str, error: str) -> LLMResponse:
        return cls(
            success=False,
            provider=provider,
            model=model,
            error=error,
        )


@dataclass
class LLMConfig:
    """Configuration loaded from Config/llm_config.yaml."""

    enabled: bool = True
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    enabled_tasks: dict[str, bool] = field(default_factory=lambda: {
        "summary": True,
        "evidence_enrichment": False,
        "figure_interpretation": False,
        "table_interpretation": False,
        "supplementary_interpretation": False,
        "agent_chat": True,
    })

    def is_task_enabled(self, task_name: str) -> bool:
        if not self.enabled:
            return False
        return self.enabled_tasks.get(task_name, False)

    def to_safe_dict(self) -> dict[str, Any]:
        """Return config without exposing the full API key."""
        result = {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enabled_tasks": dict(self.enabled_tasks),
            "api_key_configured": bool(self.api_key),
            "api_key_preview": _mask_api_key(self.api_key),
        }
        return result


def _mask_api_key(key: str) -> str:
    """Mask an API key showing only first 4 and last 4 characters."""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "*" * (len(key) - 4) + key[-2:]
    return key[:4] + "*" * (len(key) - 8) + key[-4:]
