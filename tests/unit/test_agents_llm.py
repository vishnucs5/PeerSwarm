"""
Tests for LLM integration in agents.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.crew.agents.analyst import AnalystAgent
from src.crew.agents.base import AgentContext
from src.crew.agents.critic import CriticAgent
from src.crew.agents.planner import PlannerAgent
from src.crew.agents.writer import WriterAgent
from src.models.quality import QualityDimension, QualityScore
from src.models.research import (
    EvidenceType,
    ResearchFinding,
    ResearchPlan,
    Synthesis,
)


@pytest.fixture
def context() -> AgentContext:
    return AgentContext(question="What is RAG?", temperature=0.3, max_tokens=2000)


def make_mock_completion(content: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    """Build a mock litellm.completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    return mock_response


def mock_llm(agent, content, prompt_tokens=100, completion_tokens=50):
    """Patch _llm_completion to return content and set _last_usage."""
    def side_effect(messages, context=None, response_format=None):
        agent._last_usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        return content, agent._last_usage
    return patch.object(agent, '_llm_completion', side_effect=side_effect)


class TestPlannerAgentLLM:
    def test_llm_plan_success(self, context):
        agent = PlannerAgent()
        json_output = """{
            "original_question": "What is RAG?",
            "sub_questions": [
                {"question": "What are RAG fundamentals?", "rationale": "Baseline", "priority": "high", "strategy": "academic_deep", "assigned_researcher": "researcher_a", "search_terms": ["RAG fundamentals"], "success_criteria": "Find 3 papers"},
                {"question": "What are RAG challenges?", "rationale": "Identify gaps", "priority": "high", "strategy": "gap_analysis", "assigned_researcher": "researcher_b", "search_terms": ["RAG challenges"], "success_criteria": "Find gaps"}
            ],
            "overall_strategy": "Literature survey",
            "risk_assessment": {},
            "success_criteria": ["Cover basics"],
            "estimated_iterations": 1
        }"""
        with mock_llm(agent, json_output, 100, 50):
            plan = agent.execute(context)
        assert isinstance(plan, ResearchPlan)
        assert len(plan.sub_questions) == 2
        assert agent._last_usage == {"prompt_tokens": 100, "completion_tokens": 50}

    def test_llm_plan_fallback_on_invalid_json(self, context):
        agent = PlannerAgent()
        with mock_llm(agent, "{bad json}", 100, 50):
            plan = agent.execute(context)
        assert isinstance(plan, ResearchPlan)
        assert len(plan.sub_questions) >= 1

    def test_llm_plan_sets_last_usage(self, context):
        agent = PlannerAgent()
        json_output = """{
            "original_question": "test",
            "sub_questions": [
                {"question": "q1", "rationale": "r1", "priority": "high", "strategy": "academic_deep", "assigned_researcher": "researcher_a", "search_terms": ["t1"], "success_criteria": "sc1"},
                {"question": "q2", "rationale": "r2", "priority": "medium", "strategy": "industry_survey", "assigned_researcher": "researcher_b", "search_terms": ["t2"], "success_criteria": "sc2"}
            ],
            "overall_strategy": "s1",
            "risk_assessment": {},
            "success_criteria": ["c1"],
            "estimated_iterations": 1
        }"""
        with mock_llm(agent, json_output, 50, 25):
            agent.execute(context)
        assert agent._last_usage == {"prompt_tokens": 50, "completion_tokens": 25}


class TestCriticAgentLLM:
    def test_llm_evaluate_success(self, context):
        agent = CriticAgent()
        findings = [
            ResearchFinding(
                sub_question_id="sq1", researcher="researcher_a",
                claim="RAG improves accuracy", evidence="Study shows 30% improvement",
                evidence_type=EvidenceType.ACADEMIC_PAPER, source="arxiv",
                confidence=0.9, relevance=0.9,
            )
        ]
        synthesis = Synthesis(question="What is RAG?", plan_id="p1")
        json_output = """{
            "factual_accuracy": 8, "source_quality": 7, "logical_coherence": 8,
            "completeness": 6, "clarity": 7,
            "issues": ["Missing recent papers"], "suggestions": ["Add more sources"],
            "confidence": 0.85
        }"""
        with mock_llm(agent, json_output, 200, 80):
            score = agent.execute(context, synthesis=synthesis, findings=findings)
        assert isinstance(score, QualityScore)
        assert score.factual_accuracy == 8
        assert score.issues == ["Missing recent papers"]
        assert agent._last_usage == {"prompt_tokens": 200, "completion_tokens": 80}

    def test_llm_evaluate_fallback_on_missing_synthesis(self, context):
        agent = CriticAgent()
        score = agent.execute(context, synthesis=None, findings=[])
        assert isinstance(score, QualityScore)
        assert score.overall == 5.0

    def test_route_quality_hard_gate(self, context):
        agent = CriticAgent()
        score = QualityScore(
            factual_accuracy=4, source_quality=7, logical_coherence=7,
            completeness=7, clarity=7, iteration=1,
        )
        result = agent.route_quality(score, max_iterations=3)
        assert result.passed is False
        assert result.action == "revise_research"
        assert QualityDimension.FACTUAL_ACCURACY in result.failing_dimensions

    def test_route_quality_max_iterations(self, context):
        agent = CriticAgent()
        score = QualityScore(
            factual_accuracy=4, source_quality=7, logical_coherence=7,
            completeness=7, clarity=7, iteration=3,
        )
        result = agent.route_quality(score, max_iterations=3)
        assert result.passed is True
        assert result.action == "write"


class TestAnalystAgentLLM:
    def test_llm_synthesis_success(self, context):
        agent = AnalystAgent()
        findings = [
            ResearchFinding(
                sub_question_id="sq1", researcher="researcher_a",
                claim="RAG improves accuracy", evidence="Study",
                evidence_type=EvidenceType.ACADEMIC_PAPER, source="arxiv",
                confidence=0.9, relevance=0.9,
            )
        ]
        json_output = """{
            "executive_summary": "RAG is effective.",
            "key_insights": ["RAG outperforms fine-tuning"],
            "limitations": ["Small sample sizes"],
            "future_work": ["Apply to more domains"],
            "evidence_gaps": ["Long-term effects"],
            "contradictions": []
        }"""
        with mock_llm(agent, json_output, 150, 60):
            synthesis = agent.execute(context, findings=findings)
        assert isinstance(synthesis, Synthesis)
        assert "RAG is effective" in synthesis.executive_summary
        assert len(synthesis.key_insights) == 1

    def test_llm_synthesis_fallback_empty(self, context):
        agent = AnalystAgent()
        findings = []
        with mock_llm(agent, "{}", 0, 0):
            synthesis = agent.execute(context, findings=findings)
        assert isinstance(synthesis, Synthesis)
        assert "No findings" in synthesis.executive_summary


class TestWriterAgentLLM:
    def test_llm_write_success(self, context):
        agent = WriterAgent()
        synthesis = Synthesis(
            question="What is RAG?",
            plan_id="p1",
            executive_summary="RAG combines retrieval and generation.",
            key_insights=["RAG improves accuracy"],
        )
        md = "# Research Report\n\nExecutive summary here..."
        with mock_llm(agent, md, 300, 150):
            report = agent.execute(context, synthesis=synthesis)
        assert md in report.markdown
        assert agent._last_usage == {"prompt_tokens": 300, "completion_tokens": 150}

    def test_llm_write_fallback_to_heuristic(self, context):
        agent = WriterAgent()
        synthesis = Synthesis(
            question="What is RAG?",
            plan_id="p1",
            executive_summary="RAG combines retrieval and generation.",
        )
        with mock_llm(agent, "", 0, 0):
            report = agent.execute(context, synthesis=synthesis)
        assert report.markdown
        assert "RAG" in report.markdown or "Research Report" in report.markdown

    def test_llm_write_no_synthesis(self, context):
        agent = WriterAgent()
        report = agent.execute(context, synthesis=None)
        assert "No synthesis available" in report.executive_summary
