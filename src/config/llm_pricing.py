"""
LLM pricing table and cost estimation utilities.

Prices are in USD per 1M tokens. Updated March 2026.
"""

from __future__ import annotations

# model_prefix → (input_price_per_1M, output_price_per_1M)
LLM_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (0.25, 1.25),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-5-haiku": (0.25, 1.25),
    "claude-3-opus": (15.0, 75.0),
    "claude-3-haiku": (0.25, 1.25),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-4-turbo": (10.0, 30.0),
    "o3-mini": (1.10, 4.40),
    # HuggingFace Inference API (serverless, free tier — $0 effective cost)
    "Meta-Llama": (0.0, 0.0),
    "meta-llama/": (0.0, 0.0),
    # Google
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-pro": (1.25, 10.0),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.30),
}

DEFAULT_PRICING: tuple[float, float] = (5.0, 15.0)


def get_pricing(model: str) -> tuple[float, float]:
    """Prefix-match model name against pricing table.

    Sorts by longest prefix first so "gpt-4o-mini" matches before "gpt-4o".
    """
    for prefix, prices in sorted(LLM_PRICING.items(), key=lambda x: -len(x[0])):
        if model.startswith(prefix):
            return prices
    return DEFAULT_PRICING


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost in USD for a single LLM call."""
    inp_price, out_price = get_pricing(model)
    return (input_tokens * inp_price + output_tokens * out_price) / 1_000_000
