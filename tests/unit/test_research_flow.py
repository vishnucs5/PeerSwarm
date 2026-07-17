"""
Tests for ResearchFlow step methods, helpers, and async wrapper.
"""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.flows.research_flow import ResearchFlow, run_research_async
from src.flows.state import ResearchState, TokenUsage
from src.models.quality import (
    QualityGateResult,
    QualityScore,
    QualityDimension,
    HardGateFailure,
)
from src.models.research import (
    EvidenceType,
    FindingCluster,
    ResearchFinding,
    ResearchPlan,
    SubQuestion,
    SubQuestionPriority,
    ResearchStrategy,
    Synthesis,
)


@pytest.fixture(autouse=True)
def mock_get_settings(tmp_path):
    settings = MagicMock(
        quality=MagicMock(max_iterations=3, threshold=8.0, hard_gate_threshold=6.0),
        storage=MagicMock(output_dir=tmp_path / "reports"),
        models=MagicMock(get_model=MagicMock(return_value="gpt-4o")),
    )
    with patch("src.flows.research_flow.get_settings", return_value=settings):
        yield settings


def _create_flow(question: str = "Test?", **kwargs):
    flow = ResearchFlow(question, **kwargs)
    flow.planning = MagicMock()
    flow.analysis = MagicMock()
    flow.critique = MagicMock()
    flow.writing = MagicMock()
    flow.revision = MagicMock()
    return flow


class TestResearchFlowInit:
    def test_run_id_generated_by_default(self):
        flow = _create_flow("Q?")
        assert flow.state.run_id != ""
        assert len(flow.state.run_id) == 12

    def test_run_id_from_kwargs(self):
        flow = _create_flow("Q?", run_id="custom12345678")
        assert flow.state.run_id == "custom12345678"

    def test_max_iterations_from_kwargs(self):
        flow = _create_flow("Q?", max_iterations=5)
        assert flow.state.max_iterations == 5
        assert flow.state.iteration == 0

    def test_quality_threshold_from_kwargs(self):
        flow = _create_flow("Q?", quality_threshold=9.0)
        assert flow.quality_threshold == 9.0

    def test_hard_gate_threshold_from_kwargs(self):
        flow = _create_flow("Q?", hard_gate_threshold=7.0)
        assert flow.hard_gate_threshold == 7.0


class TestTrackCost:
    def test_accumulates_cost_by_model(self):
        flow = _create_flow("Q?")
        flow._cost_tracker = lambda model, p, c: 0.001 * p + 0.002 * c
        flow._costs_by_model = {}
        flow.state.token_usage = TokenUsage()
        flow._track_cost("gpt-4o", 100, 50)
        flow._track_cost("gpt-4o", 50, 25)
        assert flow._costs_by_model["gpt-4o"] == pytest.approx(0.3)
        assert flow.state.token_usage.cost_estimate == pytest.approx(0.3)

    def test_cost_estimate_rounded(self):
        flow = _create_flow("Q?")
        flow._cost_tracker = lambda model, p, c: 0.12345
        flow._costs_by_model = {}
        flow.state.token_usage = TokenUsage()
        flow._track_cost("gpt-4o", 100, 50)
        assert flow.state.token_usage.cost_estimate == 0.1235


class TestTrackAgentUsage:
    def test_reads_last_usage_and_records(self):
        flow = _create_flow("Q?")
        flow.state.token_usage = TokenUsage()
        task = MagicMock()
        task.agent.role = "planner"
        task.agent.model = "gpt-4o"
        task.agent._last_usage = {"prompt_tokens": 100, "completion_tokens": 50}
        flow._track_agent_usage(task)
        assert flow.state.token_usage.total_prompt_tokens == 100
        assert flow.state.token_usage.total_completion_tokens == 50
        assert flow.state.token_usage.by_agent["planner"]["prompt"] == 100
        assert task.agent._last_usage is None

    def test_returns_early_when_no_agent(self):
        flow = _create_flow("Q?")
        flow.state.token_usage = TokenUsage()
        task = MagicMock()
        del task.agent
        flow._track_agent_usage(task)
        assert flow.state.token_usage.total_tokens == 0

    def test_returns_early_when_no_usage(self):
        flow = _create_flow("Q?")
        flow.state.token_usage = TokenUsage()
        task = MagicMock()
        task.agent.role = "planner"
        task.agent.model = "gpt-4o"
        task.agent._last_usage = None
        flow._track_agent_usage(task)
        assert flow.state.token_usage.total_tokens == 0


class TestCurrentQualityResult:
    def test_builds_result_from_state(self):
        flow = _create_flow("Q?")
        flow.state.iteration = 2
        flow.state.quality_score = QualityScore(
            factual_accuracy=7,
            source_quality=7,
            logical_coherence=7,
            completeness=7,
            clarity=7,
            overall=7.0,
            iteration=2,
        )
        result = flow._current_quality_result()
        assert result.passed is False
        assert result.score.overall == 7.0
        assert result.action == "revise_analysis"
        assert result.iteration == 2
        assert result.max_iterations == 3

    def test_uses_default_score_when_none(self):
        flow = _create_flow("Q?")
        flow.state.quality_score = None
        result = flow._current_quality_result()
        assert result.score.overall == 5.0
        assert result.action == "revise_analysis"


class TestDefaultScore:
    def test_returns_five_overall(self):
        flow = _create_flow("Q?")
        flow.state.iteration = 1
        score = flow._default_score()
        assert score.overall == 5.0
        assert score.factual_accuracy == 5
        assert score.iteration == 1


class TestRouteQuality:
    def test_write_action_returns_write(self):
        flow = _create_flow("Q?")
        result = QualityGateResult(
            passed=True,
            score=QualityScore(
                factual_accuracy=8,
                source_quality=8,
                logical_coherence=8,
                completeness=8,
                clarity=8,
                overall=8.0,
                iteration=1,
            ),
            action="write",
            reason="ok",
            iteration=1,
            max_iterations=3,
        )
        assert flow.route_quality(result) == "write"

    def test_revise_research_action(self):
        flow = _create_flow("Q?")
        result = QualityGateResult(
            passed=False,
            score=QualityScore(
                factual_accuracy=5,
                source_quality=8,
                logical_coherence=8,
                completeness=8,
                clarity=8,
                overall=6.6,
                iteration=1,
            ),
            action="revise_research",
            reason="low",
            iteration=1,
            max_iterations=3,
        )
        assert flow.route_quality(result) == "revise_research"

    def test_max_iterations_reached(self):
        flow = _create_flow("Q?", max_iterations=2)
        flow.state.iteration = 2
        result = QualityGateResult(
            passed=False,
            score=QualityScore(
                factual_accuracy=5,
                source_quality=8,
                logical_coherence=8,
                completeness=8,
                clarity=8,
                overall=6.6,
                iteration=2,
            ),
            action="revise_research",
            reason="low",
            iteration=2,
            max_iterations=2,
        )
        assert flow.route_quality(result) == "max_iterations"

    def test_fallback_returns_revise_analysis(self):
        flow = _create_flow("Q?")
        result = QualityGateResult(
            passed=False,
            score=QualityScore(
                factual_accuracy=5,
                source_quality=8,
                logical_coherence=8,
                completeness=8,
                clarity=8,
                overall=6.6,
                iteration=1,
            ),
            action="max_iterations",
            reason="low",
            iteration=1,
            max_iterations=3,
        )
        assert flow.route_quality(result) == "revise_analysis"


class TestPlan:
    def test_stores_plan_and_tracks_usage(self):
        flow = _create_flow("Q?")
        plan = ResearchPlan(
            original_question="Q?",
            sub_questions=[
                SubQuestion(
                    question="sq1",
                    rationale="r",
                    priority=SubQuestionPriority.HIGH,
                    strategy=ResearchStrategy.ACADEMIC_DEEP,
                    assigned_researcher="researcher_a",
                    search_terms=["t"],
                    success_criteria="sc",
                ),
                SubQuestion(
                    question="sq2",
                    rationale="r2",
                    priority=SubQuestionPriority.MEDIUM,
                    strategy=ResearchStrategy.INDUSTRY_SURVEY,
                    assigned_researcher="researcher_b",
                    search_terms=["t2"],
                    success_criteria="sc2",
                ),
            ],
            overall_strategy="strat",
            risk_assessment={},
            success_criteria=["sc"],
        )
        flow.planning.execute = MagicMock(return_value=plan)
        flow.planning.agent.role = "planner"
        flow.planning.agent.model = "gpt-4o"
        flow.planning.agent._last_usage = {"prompt_tokens": 100, "completion_tokens": 50}
        result = flow.plan()
        assert flow.state.plan == plan
        assert flow.state.current_step == "planning"
        assert flow.state.token_usage.total_prompt_tokens == 100


class TestAnalyze:
    def test_empty_findings_returns_empty_synthesis(self):
        flow = _create_flow("Q?")
        flow.state.findings = {}
        result = flow.analyze()
        assert result.question == "Q?"
        assert flow.state.synthesis == result

    def test_non_empty_findings_tracks_usage(self):
        flow = _create_flow("Q?")
        findings = [
            ResearchFinding(
                sub_question_id="sq1",
                researcher="researcher_a",
                claim="c",
                evidence="e",
                evidence_type=EvidenceType.ACADEMIC_PAPER,
                source="s",
                confidence=0.9,
                relevance=0.9,
            ),
        ]
        flow.state.findings = {"researcher_a": findings}
        flow.state.plan = ResearchPlan(
            original_question="Q?",
            sub_questions=[
                SubQuestion(question="sq1", rationale="r1", assigned_researcher="researcher_a"),
                SubQuestion(question="sq2", rationale="r2", assigned_researcher="researcher_b"),
            ],
            overall_strategy="s",
            risk_assessment={},
            success_criteria=[],
        )
        synthesis = Synthesis(question="Q?", plan_id="p1")
        flow.analysis.execute = MagicMock(return_value=synthesis)
        flow.analysis.agent.role = "analyst"
        flow.analysis.agent.model = "gpt-4o"
        flow.analysis.agent._last_usage = {"prompt_tokens": 50, "completion_tokens": 25}
        result = flow.analyze()
        assert result == synthesis
        assert flow.state.token_usage.total_prompt_tokens == 50


class TestQualityGate:
    def test_missing_synthesis_returns_default(self):
        flow = _create_flow("Q?")
        flow.state.synthesis = None
        result = flow.quality_gate()
        assert result.passed is False
        assert result.score.overall == 5.0
        assert result.action == "revise_analysis"

    def test_synthesis_present_tracks_usage(self):
        flow = _create_flow("Q?")
        flow.state.synthesis = Synthesis(question="Q?", plan_id="p1")
        flow.state.findings = {}
        gate = QualityGateResult(
            passed=True,
            score=QualityScore(
                factual_accuracy=8,
                source_quality=8,
                logical_coherence=8,
                completeness=8,
                clarity=8,
                overall=8.0,
                iteration=1,
            ),
            action="write",
            reason="ok",
            iteration=1,
            max_iterations=3,
        )
        flow.critique.execute = MagicMock(return_value=gate)
        flow.critique.agent.role = "critic"
        flow.critique.agent.model = "gpt-4o"
        flow.critique.agent._last_usage = {"prompt_tokens": 30, "completion_tokens": 10}
        result = flow.quality_gate()
        assert result == gate
        assert flow.state.token_usage.total_prompt_tokens == 30


class TestWriteReport:
    def test_delegates_execute_and_logs(self, tmp_path: Path):
        flow = _create_flow("Q?")
        flow.state.synthesis = Synthesis(question="Q?", plan_id="p1")
        flow.state.quality_score = QualityScore(
            factual_accuracy=8,
            source_quality=8,
            logical_coherence=8,
            completeness=8,
            clarity=8,
            overall=8.0,
            iteration=1,
        )
        flow.writing.execute = MagicMock(return_value="report.md")
        flow.writing.agent.role = "writer"
        flow.writing.agent.model = "claude"
        flow.writing.agent._last_usage = {"prompt_tokens": 20, "completion_tokens": 10}
        result = flow.write_report()
        assert result == "report.md"
        assert flow.state.current_step == "completed"
        output_path = tmp_path / "reports" / f"{flow.state.run_id}.md"
        flow.writing.execute.assert_called_once_with(
            synthesis=flow.state.synthesis,
            quality_score=flow.state.quality_score,
            output_path=output_path,
        )


class TestWriteWithWarning:
    def test_delegates_execute_with_warning(self, tmp_path: Path):
        flow = _create_flow("Q?")
        flow.state.synthesis = Synthesis(question="Q?", plan_id="p1")
        flow.state.quality_score = QualityScore(
            factual_accuracy=5,
            source_quality=5,
            logical_coherence=5,
            completeness=5,
            clarity=5,
            overall=5.0,
            iteration=1,
        )
        flow.writing.execute_with_warning = MagicMock(return_value="report_warn.md")
        flow.writing.agent.role = "writer"
        flow.writing.agent.model = "claude"
        flow.writing.agent._last_usage = {"prompt_tokens": 20, "completion_tokens": 10}
        result = flow.write_with_warning()
        assert result == "report_warn.md"
        assert flow.state.current_step == "completed"
        output_path = tmp_path / "reports" / f"{flow.state.run_id}.md"
        flow.writing.execute_with_warning.assert_called_once_with(
            synthesis=flow.state.synthesis,
            quality_score=flow.state.quality_score,
            output_path=output_path,
        )


class TestRunResearchAsync:
    def test_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(run_research_async)
