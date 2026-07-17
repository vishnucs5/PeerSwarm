"""
Tests for cost tracking utilities.
"""
from __future__ import annotations

from src.utils.cost_tracker import (
    get_model_cost, estimate_cost_from_response, format_cost, summarize_costs,
)


class TestGetModelCost:
    def test_gpt4o_cost(self):
        cost = get_model_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
        expected = (1000 / 1000) * 0.0025 + (500 / 1000) * 0.0100
        assert cost == round(expected, 6)

    def test_gpt4o_mini_cost(self):
        cost = get_model_cost("gpt-4o-mini", prompt_tokens=2000, completion_tokens=1000)
        expected = (2000 / 1000) * 0.00015 + (1000 / 1000) * 0.00060
        assert cost == round(expected, 6)

    def test_claude_cost(self):
        cost = get_model_cost("claude-3-5-sonnet", prompt_tokens=1000, completion_tokens=500)
        expected = (1000 / 1000) * 0.0030 + (500 / 1000) * 0.0150
        assert cost == round(expected, 6)

    def test_unknown_model_fallsback_to_default(self):
        cost = get_model_cost("unknown-model", prompt_tokens=1000, completion_tokens=500)
        expected = (1000 / 1000) * 0.0020 + (500 / 1000) * 0.0080
        assert cost == round(expected, 6)

    def test_zero_tokens(self):
        cost = get_model_cost("gpt-4o", prompt_tokens=0, completion_tokens=0)
        assert cost == 0.0


class TestEstimateCostFromResponse:
    def test_openai_style_usage(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
        cost = estimate_cost_from_response("gpt-4o", usage)
        assert cost > 0

    def test_anthropic_style_usage(self):
        usage = {"input_tokens": 1000, "output_tokens": 500}
        cost = estimate_cost_from_response("claude-3-5-sonnet", usage)
        assert cost > 0


class TestFormatCost:
    def test_large_cost(self):
        assert "$0.010" in format_cost(0.01)

    def test_small_cost(self):
        result = format_cost(0.0005)
        assert "$" in result
        assert "0.0005" in result

    def test_zero_cost(self):
        assert "$0.000000" in format_cost(0)


class TestSummarizeCosts:
    def test_summary(self):
        result = summarize_costs({"gpt-4o": 0.05, "claude-3-5-sonnet": 0.03})
        assert result["total"] == 0.08
        assert result["by_model"]["gpt-4o"] == 0.05
        assert "$" in result["total_formatted"]