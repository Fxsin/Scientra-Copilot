"""Anthropic provider — Messages API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from scientra.ai.schemas import LLMResponse

DEFAULT_BASE_URL = "https://api.anthropic.com"


def call(
    prompt: str,
    model: str = "claude-sonnet-4-6",
    api_key: str = "",
    base_url: str = DEFAULT_BASE_URL,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    system_prompt: str = "",
) -> LLMResponse:
    """Call Anthropic Messages API."""
    if not api_key:
        return LLMResponse.failure("anthropic", model, "API key not configured")

    url = base_url.rstrip("/")
    if not url.endswith("/messages"):
        if "/anthropic" in url and not url.endswith("/v1/messages"):
            url = f"{url}/v1/messages"
        else:
            url = f"{url}/v1/messages"

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system_prompt:
        payload["system"] = system_prompt

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Scientra-Copilot/2.1",
    }

    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read().decode("utf-8", errors="replace"))
                return _parse_anthropic_response(raw, model)
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            last_error = RuntimeError(f"HTTP {exc.code}: {error_body}")
            if exc.code in (401, 403, 404):
                break
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(1.5 * (2 ** attempt))

    return LLMResponse.failure("anthropic", model, str(last_error))


def _parse_anthropic_response(raw: dict[str, Any], model: str) -> LLMResponse:
    """Parse Anthropic Messages response into LLMResponse."""
    try:
        content_list = raw.get("content", [])
        text = ""
        for block in content_list:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")

        usage = raw.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        cost = _estimate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            success=True,
            provider="anthropic",
            model=model,
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_estimate=cost,
            raw_response=raw,
        )
    except Exception as exc:
        return LLMResponse.failure("anthropic", model, f"Parse error: {exc}")


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for Anthropic models. Prices as of mid-2026."""
    pricing: dict[str, tuple[float, float]] = {
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-haiku-4-5": (0.80, 4.00),
        "claude-opus-4-8": (15.00, 75.00),
        "claude-fable-5": (3.00, 15.00),
    }
    input_price, output_price = pricing.get(model, (3.00, 15.00))
    cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    return round(cost, 8)
