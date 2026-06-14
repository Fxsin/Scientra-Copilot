"""Local provider — fallback using local models via transformers.

This is a lightweight implementation for offline/air-gapped environments.
Requires: transformers, torch
"""

from __future__ import annotations

from typing import Any

from scientra.ai.schemas import LLMResponse


def call(
    prompt: str,
    model: str = "local",
    api_key: str = "",
    base_url: str = "",
    temperature: float = 0.2,
    max_tokens: int = 4096,
    system_prompt: str = "",
) -> LLMResponse:
    """Call a local model.

    Currently returns a not-implemented response. Full local model support
    will be added in a future phase when local inference is needed.
    """
    try:
        # Attempt to use a local pipeline if available
        from transformers import pipeline  # noqa: F401
    except ImportError:
        return LLMResponse(
            success=False,
            provider="local",
            model=model,
            error="Local models require: pip install transformers torch. "
                  "Configure a cloud provider (deepseek/openai/anthropic) in Settings → AI.",
        )

    try:
        generator = pipeline(
            "text-generation",
            model="microsoft/phi-2",
            device="cpu",
            trust_remote_code=True,
        )

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        result = generator(
            full_prompt,
            max_new_tokens=min(max_tokens, 1024),
            temperature=temperature,
            do_sample=temperature > 0,
        )

        text = ""
        if result and isinstance(result, list) and len(result) > 0:
            text = result[0].get("generated_text", "")

        # Remove the prompt from the output if present
        if text.startswith(full_prompt):
            text = text[len(full_prompt):].strip()

        return LLMResponse(
            success=True,
            provider="local",
            model=model,
            text=text,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost_estimate=0.0,
        )
    except Exception as exc:
        return LLMResponse.failure("local", model, f"Local inference failed: {exc}")
