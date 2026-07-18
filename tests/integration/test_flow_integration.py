"""
Integration tests for the full research flow.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestFlowIntegration:
    """Integration tests for the research flow state machine."""

    def test_research_state_create(self):
        from src.flows.state import ResearchState

        state = ResearchState(question="Integration test question")
        assert state.question == "Integration test question"
        assert state.run_id == ""
        assert state.iteration == 0

    def test_quality_score_creation(self):
        from src.models.quality import QualityScore

        score = QualityScore(
            factual_accuracy=8,
            source_quality=7,
            logical_coherence=9,
            completeness=7,
            clarity=8,
            overall=7.8,
            iteration=1,
        )
        assert score.overall == 7.8
        assert score.improved_from_previous is False

    def test_quality_score_hard_gate(self):
        from src.models.quality import HardGateFailure, QualityDimension, QualityScore

        score = QualityScore(
            factual_accuracy=5,
            source_quality=8,
            logical_coherence=8,
            completeness=8,
            clarity=8,
            overall=7.4,
            iteration=1,
            hard_gate_failures=[
                HardGateFailure(
                    dimension=QualityDimension.FACTUAL_ACCURACY,
                    score=5,
                    threshold=6,
                    reason="Below threshold",
                ),
            ],
        )
        assert len(score.hard_gate_failures) >= 1

    def test_flow_state_routing(self):
        from src.flows.state import ResearchState

        state = ResearchState(question="Routing test", max_iterations=3)
        assert state.should_continue() is True
        state.iteration = 3
        assert state.should_continue() is False

    def test_flow_state_routing_action(self):
        from src.flows.state import ResearchState

        state = ResearchState(question="Routing test")
        result = state.next_action()
        assert result in (
            "evaluate",
            "write",
            "write_with_warning",
            "revise_research",
            "revise_analysis",
            "revise_writing",
        )

    def test_finding_and_synthesis_flow(self, sample_findings, sample_synthesis):
        assert len(sample_findings) == 3
        assert sample_synthesis.question == "What are advances in RAG?"
        assert len(sample_synthesis.clusters) >= 1

    def test_quality_gate_result_serialization(self, passing_gate_result):
        d = passing_gate_result.model_dump()
        assert d["passed"] is True
        assert d["action"] == "write"

    def test_research_plan_with_routing(self, sample_plan):
        assert len(sample_plan.sub_questions) == 3
        researchers = {sq.assigned_researcher for sq in sample_plan.sub_questions}
        assert "researcher_a" in researchers
        assert "researcher_b" in researchers
        assert "researcher_c" in researchers


@pytest.mark.integration
class TestModelValidation:
    def test_research_finding_serialization(self, sample_findings):
        d = sample_findings[0].model_dump()
        assert d["claim"] == "RAG combines retrieval with generation to ground LLM outputs"
        assert d["evidence_type"] == "academic_paper"

    def test_synthesis_citations(self, sample_synthesis):
        assert "lewis2020" in sample_synthesis.citations

    def test_score_improvement_tracking(self):
        from src.models.quality import QualityScore

        prev = QualityScore(
            factual_accuracy=5,
            source_quality=5,
            logical_coherence=5,
            completeness=5,
            clarity=5,
            overall=5.0,
            iteration=1,
        )
        curr = QualityScore(
            factual_accuracy=8,
            source_quality=8,
            logical_coherence=8,
            completeness=8,
            clarity=8,
            overall=8.0,
            iteration=2,
        )
        assert curr.improved_from_previous is False
        assert curr.iteration == 2


@pytest.mark.integration
class TestMetricsIntegration:
    def test_weighted_score(self):
        from src.evaluation.metrics import compute_weighted_score

        scores = {
            "factual_accuracy": 8,
            "source_quality": 7,
            "logical_coherence": 9,
            "completeness": 6,
            "clarity": 8,
        }
        weighted = compute_weighted_score(scores)
        assert 7.0 <= weighted <= 8.5

    def test_score_to_grade_roundtrip(self):
        from src.evaluation.metrics import compute_weighted_score, score_to_grade

        scores = {
            "factual_accuracy": 9,
            "source_quality": 9,
            "logical_coherence": 9,
            "completeness": 9,
            "clarity": 9,
        }
        weighted = compute_weighted_score(scores)
        grade = score_to_grade(weighted)
        assert grade == "A"

    def test_failing_dimensions_extraction(self, failing_quality_score):
        from src.evaluation.metrics import get_failing_dimensions

        failing = get_failing_dimensions(failing_quality_score)
        assert len(failing) >= 1
