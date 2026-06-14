"""OpenAI provider — Chat Completions API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from scientra.ai.schemas import LLMResponse

DEFAULT_BASE_URL = "https://api.openai.com"


def call(
    prompt: str,
    model: str = "gpt-4o",
    api_key: str = "",
    base_url: str = DEFAULT_BASE_URL,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    system_prompt: str = "",
) -> LLMResponse:
    """Call OpenAI Chat Completions API."""
    if not api_key:
        return LLMResponse.failure("openai", model, "API key not configured")

    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = f"{url}/v1/chat/completions"

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Scientra-Copilot/2.1",
    }

    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read().decode("utf-8", errors="replace"))
                return _parse_openai_response(raw, model)
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

    return LLMResponse.failure("openai", model, str(last_error))


def _parse_openai_response(raw: dict[str, Any], model: str) -> LLMResponse:
    """Parse OpenAI response into LLMResponse."""
    try:
        choices = raw.get("choices", [])
        text = ""
        if choices:
            text = choices[0].get("message", {}).get("content", "")
        usage = raw.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        cost = _estimate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            success=True,
            provider="openai",
            model=model,
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_estimate=cost,
            raw_response=raw,
        )
    except Exception as exc:
        return LLMResponse.failure("openai", model, f"Parse error: {exc}")


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for OpenAI models. Prices as of mid-2026."""
    pricing: dict[str, tuple[float, float]] = {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4.1": (2.00, 8.00),
        "o3": (10.00, 40.00),
        "o4-mini": (1.10, 4.40),
    }
    input_price, output_price = pricing.get(model, (2.50, 10.00))
    cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    return round(cost, 8)
