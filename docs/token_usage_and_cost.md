# Token Usage & Cost Transparency

## Where Token Usage Comes From

The Scientra Literature Agent captures token usage directly from the LLM provider's API response:

- **DeepSeek**: `response.usage.prompt_tokens`, `response.usage.completion_tokens`, `response.usage.total_tokens`
- **Anthropic**: `response.usage.input_tokens`, `response.usage.output_tokens`

Token counts are reported in the `token_usage` field of every `/v1/agent/ask` response.

## Evidence-Only Mode

When Answer Mode is set to **Evidence-only** (or Auto falls back), no LLM API is called.

```json
{ "source": "no_llm", "total_tokens": 0, "note": "Evidence-only mode; no LLM tokens used." }
```

## Cost Estimation

Costs are estimated from `Config/llm_pricing.yaml`:

```yaml
deepseek:
  deepseek-chat:
    input_per_1m_tokens_usd: 0.27
    output_per_1m_tokens_usd: 1.10
```

Formula:
```
input_cost = prompt_tokens / 1,000,000 * input_price
output_cost = completion_tokens / 1,000,000 * output_price
total_cost = input_cost + output_cost
```

**Costs are estimates only.** Update pricing values from provider documentation.

## Factors Affecting Token Usage

| Factor | Impact |
|---|---|
| `top_k` | Higher top_k → more context chunks → more prompt tokens |
| `chunk_types` | Fewer types → fewer chunks → fewer tokens |
| `paper_id` | Single paper → fewer chunks → fewer tokens |
| `use_llm=false` | Zero LLM tokens (evidence-only) |
| Answer length | Longer answers → more completion tokens |

## API Key Security

- API key is **never** returned to the frontend
- Only token counts and cost estimates are exposed
- Raw provider responses are not forwarded

## Updating Pricing

Edit `Config/llm_pricing.yaml` with current prices from:
- DeepSeek: https://platform.deepseek.com/pricing
- Anthropic: https://www.anthropic.com/pricing
