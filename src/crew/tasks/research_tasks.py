"""
Research tasks for all 3 researcher agents.
"""
from __future__ import annotations

from typing import Any, Literal

from src.crew.agents.base import AgentContext
from src.crew.agents.researcher_academic import AcademicResearcherAgent
from src.crew.agents.researcher_kb import KBResearcherAgent
from src.crew.agents.researcher_web import WebResearcherAgent
from src.models.research import ResearchFinding, SubQuestion
from src.utils.logger import get_logger

logger = get_logger(__name__)

ResearcherType = Literal["researcher_a", "researcher_b", "researcher_c"]


class AcademicResearchTask:
    """Task for Researcher A - searches academic sources like ArXiv."""

    def __init__(self, agent: AcademicResearcherAgent):
        self.agent = agent

    def execute(self, sub_question: SubQuestion, context: AgentContext | None = None,
                **kwargs) -> list[ResearchFinding]:
        ctx = context or AgentContext(question=sub_question.question)
        findings = self.agent.execute(ctx, sub_question=sub_question.question,
                                       sub_question_id=sub_question.id,
                                       search_terms=sub_question.search_terms)
        logger.info(f"[Academic] Sub-Q '{sub_question.question[:50]}': {len(findings)} findings")
        return findings

    def to_crewai_task(self, crewai_agent) -> Any:
        try:
            from crewai import Task as CrewTask
            return CrewTask(
                description="Search academic databases (ArXiv) for evidence on the assigned sub-question. "
                            "Extract key claims, assess source quality, and return structured findings.",
                agent=crewai_agent,
                expected_output="List of ResearchFinding objects with claims, evidence, and source metadata",
            )
        except ImportError:
            return None


class WebResearchTask:
    """Task for Researcher B - searches web/industry sources."""

    def __init__(self, agent: WebResearcherAgent):
        self.agent = agent

    def execute(self, sub_question: SubQuestion, context: AgentContext | None = None,
                **kwargs) -> list[ResearchFinding]:
        ctx = context or AgentContext(question=sub_question.question)
        findings = self.agent.execute(ctx, sub_question=sub_question.question,
                                       sub_question_id=sub_question.id,
                                       search_terms=sub_question.search_terms)
        logger.info(f"[Web] Sub-Q '{sub_question.question[:50]}': {len(findings)} findings")
        return findings

    def to_crewai_task(self, crewai_agent) -> Any:
        try:
            from crewai import Task as CrewTask
            return CrewTask(
                description="Search web/industry sources (blogs, news, reports) for evidence on the assigned sub-question.",
                agent=crewai_agent,
                expected_output="List of ResearchFinding objects with claims, evidence, and source URLs",
            )
        except ImportError:
            return None


class KBResearchTask:
    """Task for Researcher C - searches internal knowledge base."""

    def __init__(self, agent: KBResearcherAgent):
        self.agent = agent

    def execute(self, sub_question: SubQuestion, context: AgentContext | None = None,
                **kwargs) -> list[ResearchFinding]:
        ctx = context or AgentContext(question=sub_question.question)
        findings = self.agent.execute(ctx, sub_question=sub_question.question,
                                       sub_question_id=sub_question.id)
        logger.info(f"[KB] Sub-Q '{sub_question.question[:50]}': {len(findings)} findings")
        return findings

    def to_crewai_task(self, crewai_agent) -> Any:
        try:
            from crewai import Task as CrewTask
            return CrewTask(
                description="Search the internal knowledge base, knowledge graph, and prior run history for relevant findings.",
                agent=crewai_agent,
                expected_output="List of ResearchFinding objects from prior research and stored knowledge",
            )
        except ImportError:
            return None


def create_research_task(researcher_type: ResearcherType) -> Any:
    """Factory to create the appropriate research task."""
    from src.crew.agents import (
        create_academic_researcher,
        create_kb_researcher,
        create_web_researcher,
    )
    if researcher_type == "researcher_a":
        return AcademicResearchTask(create_academic_researcher())
    if researcher_type == "researcher_b":
        return WebResearchTask(create_web_researcher())
    if researcher_type == "researcher_c":
        return KBResearchTask(create_kb_researcher())
    raise ValueError(f"Unknown researcher type: {researcher_type}")
