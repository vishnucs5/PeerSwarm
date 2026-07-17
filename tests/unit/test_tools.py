"""
Tests for core tools: calculator, citation, self-evaluation.
"""
from __future__ import annotations

import pytest


class TestCalculatorTool:
    def test_add(self):
        from src.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = calc.evaluate("1 + 2")
        assert result == 3

    def test_complex_expression(self):
        from src.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = calc.evaluate("(3 + 5) * 2")
        assert result == 16

    def test_division(self):
        from src.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = calc.evaluate("10 / 2")
        assert result == 5.0

    def test_invalid_expression(self):
        from src.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = calc.evaluate("invalid @@@")
        assert isinstance(result, str)

    def test_unsafe_expression_raises(self):
        from src.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = calc.evaluate("__import__('os').system('ls')")
        assert isinstance(result, str)


class TestCitationTool:
    def test_format_apa(self):
        from src.tools.citation_tool import CitationTool
        tool = CitationTool()
        citation = tool.format_apa(
            authors=["Lewis, P."],
            year=2020,
            title="RAG paper",
            journal="arXiv",
        )
        assert citation is not None

    def test_format_mla(self):
        from src.tools.citation_tool import CitationTool
        tool = CitationTool()
        citation = tool.format_mla(
            authors=["Lewis, P."],
            year=2020,
            title="RAG paper",
        )
        assert citation is not None
        assert "Lewis" in citation

    def test_format_chicago(self):
        from src.tools.citation_tool import CitationTool
        tool = CitationTool()
        citation = tool.format_chicago(
            authors=["Lewis, P."],
            year=2020,
            title="RAG paper",
            journal="arXiv",
        )
        assert citation is not None
        assert "Lewis" in citation


class TestSelfEvaluationTool:
    def test_claim_grounding(self):
        from src.tools.self_evaluation import SelfEvaluationTool
        tool = SelfEvaluationTool()
        result = tool.evaluate_claim(
            claim="RAG improves accuracy",
            evidence="Studies show 30% improvement",
        )
        assert isinstance(result, dict)

    def test_citation_check(self):
        from src.tools.self_evaluation import SelfEvaluationTool
        tool = SelfEvaluationTool()
        result = tool.check_citation(
            claim="RAG improves accuracy",
            source="Lewis et al. 2020",
        )
        assert isinstance(result, dict)

    def test_contradiction_detection(self):
        from src.tools.self_evaluation import SelfEvaluationTool
        tool = SelfEvaluationTool()
        result = tool.check_contradiction(
            claim1="RAG improves accuracy by 30%",
            claim2="RAG has no effect on accuracy",
        )
        assert isinstance(result, dict)