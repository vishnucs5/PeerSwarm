"""
Analysis task - Analyst synthesizes all research findings.
"""

from __future__ import annotations

from typing import Any

from src.crew.agents.analyst import AnalystAgent
from src.crew.agents.base import AgentContext
from src.models.research import ResearchFinding, ResearchPlan, Synthesis
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisTask:
    """Task that synthesizes research findings into a coherent analysis."""

    def __init__(self, analyst_agent: AnalystAgent):
        self.agent = analyst_agent

    def execute(
        self,
        findings: list[ResearchFinding],
        plan: ResearchPlan,
        context: AgentContext | None = None,
        **kwargs,
    ) -> Synthesis:
        """Execute analysis task: cluster findings, identify gaps, build synthesis."""
        ctx = context or AgentContext(question=plan.original_question)
        synthesis = self.agent.execute(ctx, findings=findings, plan=plan)
        self._log_synthesis(synthesis)
        return synthesis

    def execute_revised(
        self,
        findings: list[ResearchFinding],
        plan: ResearchPlan,
        previous_synthesis: Synthesis,
        revision_focus: list[str],
        context: AgentContext | None = None,
        **kwargs,
    ) -> Synthesis:
        """Execute analysis with revision focus from critic."""
        ctx = context or AgentContext(question=plan.original_question)
        logger.info(f"Revised analysis focusing on: {revision_focus}")
        synthesis = self.agent.execute(
            ctx,
            findings=findings,
            plan=plan,
            revision_focus=revision_focus,
            previous_synthesis=previous_synthesis,
        )
        synthesis.version = previous_synthesis.version + 1
        self._log_synthesis(synthesis)
        return synthesis

    def _log_synthesis(self, synthesis: Synthesis):
        clusters = len(synthesis.clusters) if hasattr(synthesis, "clusters") else 0
        insights = len(synthesis.key_insights) if hasattr(synthesis, "key_insights") else 0
        logger.info(f"Synthesis complete: {clusters} clusters, {insights} insights")

    def to_crewai_task(self, crewai_agent) -> Any:
        try:
            from crewai import Task as CrewTask

            return CrewTask(
                description="""Synthesize all research findings into a coherent analysis.

1. Cluster findings by theme
2. Identify contradictions and evidence gaps
3. Build a unified narrative
4. Extract key insights
5. Identify limitations and future work

Output a complete Synthesis document.""",
                agent=crewai_agent,
                expected_output="""A Synthesis document containing:
- Executive summary
- Thematic clusters with findings
- Key insights and contradictions
- Evidence gaps and limitations
- Future work suggestions""",
            )
        except ImportError:
            return None


def create_analysis_task(analyst: AnalystAgent | None = None) -> AnalysisTask:
    if analyst is None:
        from src.crew.agents import create_analyst_agent

        analyst = create_analyst_agent()
    return AnalysisTask(analyst)
