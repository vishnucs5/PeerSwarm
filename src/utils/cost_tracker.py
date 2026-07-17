"""
Cost tracking for LLM API calls.
"""
from __future__ import annotations

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Pricing per 1K tokens (USD)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {
        "prompt": 0.0025,
        "completion": 0.0100,
    },
    "gpt-4o-2024-08-06": {
        "prompt": 0.0025,
        "completion": 0.0100,
    },
    "gpt-4o-mini": {
        "prompt": 0.00015,
        "completion": 0.00060,
    },
    "gpt-4o-mini-2024-07-18": {
        "prompt": 0.00015,
        "completion": 0.00060,
    },
    "claude-3-5-sonnet-20240620": {
        "prompt": 0.0030,
        "completion": 0.0150,
    },
    "claude-3-5-sonnet": {
        "prompt": 0.0030,
        "completion": 0.0150,
    },
    "claude-3-haiku": {
        "prompt": 0.00025,
        "completion": 0.00125,
    },
    "gemini-1.5-pro": {
        "prompt": 0.00125,
        "completion": 0.00500,
    },
    "gemini-1.5-flash": {
        "prompt": 0.000075,
        "completion": 0.00030,
    },
    "default": {
        "prompt": 0.0020,
        "completion": 0.0080,
    },
}


def get_model_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate cost for an LLM API call.

    Args:
        model: Model name (e.g., "gpt-4o", "claude-3-5-sonnet")
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Cost in USD
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1000) * pricing["completion"]
    total = round(prompt_cost + completion_cost, 6)
    return total


def estimate_cost_from_response(model: str, usage: dict[str, int]) -> float:
    """
    Estimate cost from a usage dict (e.g., from OpenAI API response).
    Usage format: {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
    """
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    return get_model_cost(model, prompt, completion)


def format_cost(cost_usd: float) -> str:
    """Format USD cost for display."""
    if cost_usd < 0.001:
        return f"${cost_usd:.6f}"
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    return f"${cost_usd:.3f}"


def summarize_costs(costs: dict[str, float]) -> dict[str, float]:
    """Summarize costs by model."""
    total = sum(costs.values())
    return {
        "by_model": costs,
        "total": round(total, 4),
        "total_formatted": format_cost(total),
    }
