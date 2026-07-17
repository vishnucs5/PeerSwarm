"""
Tests for flow state model and routing logic.
"""
from __future__ import annotations

from src.flows.state import ResearchState
from src.models.memory import TokenUsage


class TestResearchState:
    def test_create_minimal(self):
        state = ResearchState(question="Test question")
        assert state.question == "Test question"
        assert state.run_id == ""
        assert state.current_step == "initialized"
        assert state.iteration == 0
        assert state.max_iterations == 3

    def test_get_all_findings_empty(self):
        state = ResearchState(question="Test?")
        findings = state.get_all_findings()
        assert findings == []

    def test_get_all_findings_with_data(self):
        state = ResearchState(question="Test?")
        from src.models.research import ResearchFinding, EvidenceType
        state.findings = {
            "researcher_a": [
                ResearchFinding(
                    sub_question_id="sq_1", researcher="researcher_a",
                    claim="Claim 1", evidence="Ev 1",
                    evidence_type=EvidenceType.ACADEMIC_PAPER, source="Src 1",
                ),
            ],
        }
        findings = state.get_all_findings()
        assert len(findings) == 1

    def test_increment_iteration(self):
        state = ResearchState(question="Test?")
        assert state.iteration == 0
        state.iteration += 1
        assert state.iteration == 1

    def test_has_hard_gate_failures_none(self):
        state = ResearchState(question="Test?")
        assert state.has_hard_gate_failures() is False

    def test_should_continue_default(self):
        state = ResearchState(question="Test?")
        assert state.should_continue() is True

    def test_should_continue_max_reached(self):
        state = ResearchState(question="Test?", max_iterations=3)
        state.iteration = 3
        assert state.should_continue() is False

    def test_next_action_write(self):
        state = ResearchState(question="Test?", max_iterations=3)
        state.iteration = 3
        assert state.next_action() == "write_with_warning"

    def test_next_action_evaluate(self):
        state = ResearchState(question="Test?")
        assert state.next_action() == "evaluate"

    def test_token_usage(self):
        state = ResearchState(question="Test?")
        state.token_usage = TokenUsage(
            total_prompt_tokens=1000,
            total_completion_tokens=500,
            total_tokens=1500,
        )
        assert state.token_usage.total_tokens == 1500

    def test_has_hard_gate_failures_with_score(self, failing_quality_score):
        state = ResearchState(question="Test?")
        state.quality_score = failing_quality_score
        assert state.has_hard_gate_failures() is True