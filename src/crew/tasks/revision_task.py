"""
Revision task - applies targeted revisions based on critic feedback.
"""

from __future__ import annotations

from typing import Any, Literal

from src.crew.agents.analyst import AnalystAgent
from src.crew.agents.base import AgentContext
from src.crew.agents.researcher_academic import AcademicResearcherAgent
from src.crew.agents.researcher_kb import KBResearcherAgent
from src.crew.agents.researcher_web import WebResearcherAgent
from src.models.quality import QualityGateResult, RevisionDirective
from src.models.research import ResearchFinding, ResearchPlan, Synthesis
from src.utils.logger import get_logger

logger = get_logger(__name__)

TargetAgent = Literal["researcher_a", "researcher_b", "researcher_c", "analyst", "writer"]


class RevisionTask:
    """Task that applies targeted revisions based on the critic's directive."""

    def __init__(self):
        self._researcher_a: AcademicResearcherAgent | None = None
        self._researcher_b: WebResearcherAgent | None = None
        self._researcher_c: KBResearcherAgent | None = None
        self._analyst: AnalystAgent | None = None

    @property
    def researcher_a(self) -> AcademicResearcherAgent:
        if self._researcher_a is None:
            from src.crew.agents import create_academic_researcher

            self._researcher_a = create_academic_researcher()
        return self._researcher_a

    @property
    def researcher_b(self) -> WebResearcherAgent:
        if self._researcher_b is None:
            from src.crew.agents import create_web_researcher

            self._researcher_b = create_web_researcher()
        return self._researcher_b

    @property
    def researcher_c(self) -> KBResearcherAgent:
        if self._researcher_c is None:
            from src.crew.agents import create_kb_researcher

            self._researcher_c = create_kb_researcher()
        return self._researcher_c

    @property
    def analyst(self) -> AnalystAgent:
        if self._analyst is None:
            from src.crew.agents import create_analyst_agent

            self._analyst = create_analyst_agent()
        return self._analyst

    def execute(
        self,
        target: TargetAgent,
        quality_result: QualityGateResult,
        findings: dict[str, list[ResearchFinding]],
        current_synthesis: Synthesis | None = None,
        plan: ResearchPlan | None = None,
        context: AgentContext | None = None,
    ) -> dict[str, Any]:
        """Execute targeted revision based on quality gate result."""
        ctx = context or AgentContext(question="", iteration=quality_result.score.iteration)
        score = quality_result.score
        ctx.iteration = score.iteration
        result = {"revised": False, "findings": findings, "synthesis": current_synthesis}
        revision_reason = quality_result.reason

        logger.info(f"Revision targeting {target}: {revision_reason}")

        if target == "researcher_a":
            additional = self.researcher_a.execute(
                ctx,
                sub_question=revision_reason,
                sub_question_id="revision",
                search_terms=score.suggestions[:2],
            )
            result["findings"]["researcher_a"] = (
                result["findings"].get("researcher_a", []) + additional
            )
            result["revised"] = True

        elif target == "researcher_b":
            additional = self.researcher_b.execute(
                ctx,
                sub_question=revision_reason,
                sub_question_id="revision",
                search_terms=score.suggestions[:2],
            )
            result["findings"]["researcher_b"] = (
                result["findings"].get("researcher_b", []) + additional
            )
            result["revised"] = True

        elif target == "researcher_c":
            additional = self.researcher_c.execute(
                ctx, sub_question=revision_reason, sub_question_id="revision"
            )
            result["findings"]["researcher_c"] = (
                result["findings"].get("researcher_c", []) + additional
            )
            result["revised"] = True

        elif target == "analyst" and current_synthesis:
            all_findings = []
            for flist in findings.values():
                all_findings.extend(flist)
            new_synthesis = self.analyst.execute(
                ctx,
                findings=all_findings,
                plan=plan,
                revision_focus=score.issues,
                previous_synthesis=current_synthesis,
            )
            new_synthesis.version = current_synthesis.version + 1
            result["synthesis"] = new_synthesis
            result["revised"] = True

        return result

    def create_revision_directive(self, quality_result: QualityGateResult) -> RevisionDirective:
        """Create a revision directive from the quality gate result."""
        issues = quality_result.score.issues
        suggestions = quality_result.score.suggestions
        target = self._map_action_to_agent(quality_result.action)
        return RevisionDirective(
            target_agent=target,
            specific_issues=issues,
            suggested_approach=suggestions[0] if suggestions else "",
            max_tokens=4000,
        )

    def _map_action_to_agent(self, action: str) -> TargetAgent:
        mapping = {
            "revise_research": "researcher_a",
            "revise_analysis": "analyst",
            "revise_write": "writer",
            "write": "analyst",
            "max_iterations": "analyst",
        }
        return mapping.get(action, "analyst")

    def to_crewai_task(self, crewai_agent) -> Any:
        try:
            from crewai import Task as CrewTask

            return CrewTask(
                description="""Apply targeted revisions based on quality critique feedback.

Focus on the specific issues identified by the critic agent:
- Missing evidence: conduct additional research
- Logical gaps: re-analyze existing findings
- Clarity issues: improve structure and language

Return revised findings and/or synthesis.""",
                agent=crewai_agent,
                expected_output="Revised findings and/or synthesis addressing all identified issues",
            )
        except ImportError:
            return None


def create_revision_task() -> RevisionTask:
    return RevisionTask()
