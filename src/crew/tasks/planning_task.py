"""
Planning task - PI agent decomposes questions into research plans.
"""

from __future__ import annotations

from typing import Any

from src.crew.agents.base import AgentContext
from src.crew.agents.planner import PlannerAgent
from src.models.research import ResearchPlan
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PlanningTask:
    """Task that creates a structured research plan from a user question."""

    def __init__(self, planner_agent: PlannerAgent):
        self.agent = planner_agent

    def execute(self, question: str, context: AgentContext | None = None, **kwargs) -> ResearchPlan:
        """Execute the planning task."""
        ctx = context or AgentContext(question=question)
        plan = self.agent.execute(ctx, **kwargs)
        self._log_plan(plan)
        return plan

    def _log_plan(self, plan: ResearchPlan):
        """Log plan details."""
        sub_qs = [
            f"  {i + 1}. [{sq.assigned_researcher}] {sq.question[:80]}"
            for i, sq in enumerate(plan.sub_questions)
        ]
        logger.info("Research plan created:\n" + "\n".join(sub_qs))

    def to_crewai_task(self, crewai_agent) -> Any:
        """Convert to CrewAI Task format."""
        try:
            from crewai import Task as CrewTask

            return CrewTask(
                description=self._get_description(),
                agent=crewai_agent,
                expected_output=self._get_expected_output(),
            )
        except ImportError:
            logger.warning("CrewAI not available for task conversion")
            return None

    def _get_description(self) -> str:
        return """Analyze the research question and create a structured research plan.

1. Decompose the question into 3-5 key sub-questions
2. Assign each sub-question to the appropriate researcher
3. Define search strategies and success criteria
4. Assess risks and identify success criteria

Output a complete ResearchPlan with all sub-questions, strategies, and risk assessments."""

    def _get_expected_output(self) -> str:
        return """A structured ResearchPlan containing:
- Original question
- 3-5 well-scoped sub-questions with assigned researchers
- Search strategies and evidence requirements
- Risk assessment and success criteria"""


def create_planning_task(planner: PlannerAgent | None = None) -> PlanningTask:
    if planner is None:
        from src.crew.agents import create_planner_agent

        planner = create_planner_agent()
    return PlanningTask(planner)
