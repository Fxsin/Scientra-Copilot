"""LLM Provider implementations.

Each provider module exposes a single function:
    call(prompt, model, api_key, base_url, temperature, max_tokens) -> LLMResponse
"""

from scientra.ai.providers.deepseek import call as deepseek_call
from scientra.ai.providers.openai import call as openai_call
from scientra.ai.providers.anthropic import call as anthropic_call
from scientra.ai.providers.local import call as local_call

PROVIDER_MAP = {
    "deepseek": deepseek_call,
    "openai": openai_call,
    "anthropic": anthropic_call,
    "local": local_call,
}
