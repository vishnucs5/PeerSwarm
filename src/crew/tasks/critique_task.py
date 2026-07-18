"""
Critique task - Critic evaluates synthesis quality and produces routing directives.
"""

from __future__ import annotations

from typing import Any

from src.crew.agents.base import AgentContext
from src.crew.agents.critic import CriticAgent
from src.models.quality import QualityGateResult, QualityScore
from src.models.research import ResearchFinding, Synthesis
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CritiqueTask:
    """Task that evaluates synthesis quality and determines routing."""

    def __init__(self, critic_agent: CriticAgent):
        self.agent = critic_agent

    def execute(
        self,
        synthesis: Synthesis,
        findings: list[ResearchFinding],
        context: AgentContext | None = None,
        previous_score: QualityScore | None = None,
        quality_threshold: float = 8.0,
        hard_gate_threshold: int = 6,
        max_iterations: int = 3,
    ) -> QualityGateResult:
        """Evaluate quality and determine routing action."""
        ctx = context or AgentContext(question=synthesis.question)
        score = self.agent.execute(
            ctx, synthesis=synthesis, findings=findings, previous_score=previous_score
        )
        result = self.agent.route_quality(score, max_iterations=max_iterations)
        self._log_result(result)
        return result

    def _log_result(self, result: QualityGateResult):
        action = result.action
        score = result.score.overall
        iteration = result.iteration
        logger.info(f"Quality gate: score={score}/10, action={action}, iter={iteration}")

    def to_crewai_task(self, crewai_agent) -> Any:
        try:
            from crewai import Task as CrewTask

            return CrewTask(
                description="""Evaluate the quality of the research synthesis across multiple dimensions:
1. Factual accuracy (0-10)
2. Source quality (0-10)
3. Logical coherence (0-10)
4. Completeness (0-10)
5. Clarity (0-10)

Produce a weighted overall score. Trigger hard gates for any dimension below 6.
Determine if the synthesis should proceed to writing or be revised.""",
                agent=crewai_agent,
                expected_output="A QualityGateResult with scores, hard gate failures, and routing decision",
            )
        except ImportError:
            return None


def create_critique_task(critic: CriticAgent | None = None) -> CritiqueTask:
    if critic is None:
        from src.crew.agents import create_critic_agent

        critic = create_critic_agent()
    return CritiqueTask(critic)
