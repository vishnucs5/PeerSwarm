"""
Flow state management for CrewAI Flows.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.models.memory import TokenUsage as BaseTokenUsage
from src.models.quality import QualityScore, RevisionDirective
from src.models.research import FinalReport, ResearchFinding, ResearchPlan, Synthesis


class TokenUsage(BaseTokenUsage):
    """Token usage tracking with per-agent breakdown."""
    by_agent: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_model: dict[str, dict[str, int]] = Field(default_factory=dict)

    def add(self, agent: str, model: str, prompt: int, completion: int):
        """Add token usage."""
        self.total_prompt_tokens += prompt
        self.total_completion_tokens += completion
        self.total_tokens += prompt + completion

        if agent not in self.by_agent:
            self.by_agent[agent] = {"prompt": 0, "completion": 0, "total": 0}
        self.by_agent[agent]["prompt"] += prompt
        self.by_agent[agent]["completion"] += completion
        self.by_agent[agent]["total"] += prompt + completion

        if model not in self.by_model:
            self.by_model[model] = {"prompt": 0, "completion": 0, "total": 0}
        self.by_model[model]["prompt"] += prompt
        self.by_model[model]["completion"] += completion
        self.by_model[model]["total"] += prompt + completion

    def get_summary(self) -> dict[str, Any]:
        """Get usage summary."""
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "estimated_cost": self.estimated_cost,
            "by_agent": self.by_agent,
            "by_model": self.by_model,
        }


class ResearchState(BaseModel):
    """State for the research flow."""

    # Input
    question: str = ""
    context: str | None = None

    # Plan
    plan: ResearchPlan | None = None

    # Research findings
    findings: dict[str, list[ResearchFinding]] = Field(default_factory=dict)

    # Synthesis
    synthesis: Synthesis | None = None

    # Quality evaluation
    quality_score: QualityScore | None = None
    revision_directive: RevisionDirective | None = None

    # Flow control
    iteration: int = Field(default=0, ge=0)
    max_iterations: int = Field(default=3, ge=1)
    current_step: str = "initialized"

    # Token tracking
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    # Metadata
    trace_id: str = ""
    run_id: str = ""
    tags: list[str] = Field(default_factory=list)
    final_report: FinalReport | None = None

    def get_all_findings(self) -> list[ResearchFinding]:
        """Get all findings from all researchers."""
        all_findings = []
        for findings_list in self.findings.values():
            all_findings.extend(findings_list)
        return all_findings

    def has_hard_gate_failures(self) -> bool:
        """Check if quality score has hard gate failures."""
        return self.quality_score is not None and len(self.quality_score.hard_gate_failures) > 0

    def should_continue(self, quality_threshold: float = 8.0) -> bool:
        """Determine if flow should continue to next iteration."""
        if self.iteration >= self.max_iterations:
            return False
        if self.quality_score is None:
            return True
        if self.has_hard_gate_failures():
            return True
        return self.quality_score.overall < quality_threshold

    def next_action(self, quality_threshold: float = 8.0) -> str:
        """Determine next action based on state."""
        if self.iteration >= self.max_iterations:
            return "write_with_warning"
        if self.quality_score is None:
            return "evaluate"
        if self.has_hard_gate_failures():
            # Route based on failed dimension
            failures = self.quality_score.hard_gate_failures
            dim_to_action = {
                "factual_accuracy": "revise_research",
                "source_quality": "revise_research",
                "logical_coherence": "revise_analysis",
                "completeness": "revise_analysis",
                "clarity": "revise_writing",
            }
            for failure in failures:
                action = dim_to_action.get(failure.dimension.value, "revise_analysis")
                return action
        if self.quality_score.overall >= quality_threshold:
            return "write"
        # Soft gate - use revision priority
        priority_to_action = {
            "research": "revise_research",
            "analysis": "revise_analysis",
            "writing": "revise_writing",
        }
        return priority_to_action.get(self.quality_score.revision_priority, "revise_analysis")


