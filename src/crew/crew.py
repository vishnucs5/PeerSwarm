"""
Crew builder — assembles agents and tasks into a CrewAI Crew.
"""
from __future__ import annotations

from typing import Any

from src.config import get_model_for_agent
from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from crewai import Crew, Process
    CREWAI_AVAILABLE = True
except ImportError:
    Crew = object
    Process = object
    CREWAI_AVAILABLE = False


class ResearchCrew:
    """
    Assembles all research agents and tasks into a CrewAI Crew.
    The Crew handles sequential execution; the Flow handles routing/quality loop.
    """

    def __init__(self, verbose: bool = True, memory: bool = True):
        self.verbose = verbose
        self.memory = memory
        self._agents: dict[str, Any] = {}
        self._tasks: dict[str, Any] = {}

    # ── Agent Factory ──────────────────────────────────────────────────

    def _get_agent(self, role: str) -> Any:
        """Get or create a CrewAI Agent."""
        if role not in self._agents:
            from src.crew.agents import (
                AcademicResearcherAgent,
                AnalystAgent,
                CriticAgent,
                KBResearcherAgent,
                PlannerAgent,
                WebResearcherAgent,
                WriterAgent,
            )

            agent_classes = {
                "planner": PlannerAgent,
                "researcher_a": AcademicResearcherAgent,
                "researcher_b": WebResearcherAgent,
                "researcher_c": KBResearcherAgent,
                "analyst": AnalystAgent,
                "critic": CriticAgent,
                "writer": WriterAgent,
            }

            agent_class = agent_classes.get(role)
            if not agent_class:
                raise ValueError(f"Unknown agent role: {role}")

            python_agent = agent_class(model=get_model_for_agent(role), verbose=self.verbose)
            self._agents[role] = python_agent

        return self._agents[role]

    def to_crewai_agent(self, python_agent: Any) -> Any:
        """Wrap a Python agent as a CrewAI Agent."""
        if not CREWAI_AVAILABLE:
            return None

        from src.crew.agents.base import CrewAIAgentWrapper
        wrapper = CrewAIAgentWrapper(python_agent)
        return wrapper.to_crewai_agent()

    # ── Task Factory ───────────────────────────────────────────────────

    def _get_task(self, task_name: str) -> Any:
        from src.crew.tasks import (
            create_analysis_task,
            create_critique_task,
            create_planning_task,
            create_research_task,
            create_writing_task,
        )

        factories = {
            "planning": create_planning_task,
            "research_a": lambda: create_research_task("researcher_a"),
            "research_b": lambda: create_research_task("researcher_b"),
            "research_c": lambda: create_research_task("researcher_c"),
            "analysis": create_analysis_task,
            "critique": create_critique_task,
            "writing": create_writing_task,
        }

        factory = factories.get(task_name)
        if not factory:
            raise ValueError(f"Unknown task: {task_name}")
        return factory()

    # ── Build Crew ─────────────────────────────────────────────────────

    def build_crew(self, flow: Any) -> Any | None:
        """
        Build a CrewAI Crew from the flow's agents and tasks.
        Used for CrewAI-native execution (alternative to Flow-based).
        """
        if not CREWAI_AVAILABLE:
            logger.warning("CrewAI not installed. Use Flow-based execution instead.")
            return None

        planner = self._get_agent("planner")
        researcher_a = self._get_agent("researcher_a")
        researcher_b = self._get_agent("researcher_b")
        researcher_c = self._get_agent("researcher_c")
        analyst = self._get_agent("analyst")
        critic = self._get_agent("critic")
        writer = self._get_agent("writer")

        planning_task = self._get_task("planning")
        research_a_task = self._get_task("research_a")
        research_b_task = self._get_task("research_b")
        research_c_task = self._get_task("research_c")
        analysis_task = self._get_task("analysis")
        critique_task = self._get_task("critique")
        writing_task = self._get_task("writing")

        crew = Crew(
            agents=[
                self.to_crewai_agent(planner),
                self.to_crewai_agent(researcher_a),
                self.to_crewai_agent(researcher_b),
                self.to_crewai_agent(researcher_c),
                self.to_crewai_agent(analyst),
                self.to_crewai_agent(critic),
                self.to_crewai_agent(writer),
            ],
            tasks=[
                planning_task.to_crewai_task(self.to_crewai_agent(planner)),
                research_a_task.to_crewai_task(self.to_crewai_agent(researcher_a)),
                research_b_task.to_crewai_task(self.to_crewai_agent(researcher_b)),
                research_c_task.to_crewai_task(self.to_crewai_agent(researcher_c)),
                analysis_task.to_crewai_task(self.to_crewai_agent(analyst)),
                critique_task.to_crewai_task(self.to_crewai_agent(critic)),
                writing_task.to_crewai_task(self.to_crewai_agent(writer)),
            ],
            process=Process.sequential,
            verbose=self.verbose,
            memory=self.memory,
        )
        logger.info("CrewAI Crew assembled with 7 agents and 7 tasks")
        return crew

    # ── Hybrid Execution ───────────────────────────────────────────────

    def run_flow(self, question: str, **kwargs) -> Any:
        """
        Primary execution method: runs the CrewAI Flow directly.
        This is the recommended approach as it includes the quality loop.
        """
        from src.flows.research_flow import ResearchFlow

        flow = ResearchFlow(
            question=question,
            max_iterations=kwargs.get("max_iterations"),
            quality_threshold=kwargs.get("quality_threshold"),
            tags=kwargs.get("tags", []),
        )
        flow.kickoff()
        return flow.state

    def run_crew(self, question: str) -> Any:
        """
        Alternative execution: runs the standard CrewAI Crew.
        This does NOT include the quality loop but uses CrewAI's built-in process.
        """
        crew = self.build_crew(None)
        if not crew:
            return None

        result = crew.kickoff(inputs={"question": question})
        logger.info("CrewAI Crew execution complete")
        return result


def build_research_crew() -> ResearchCrew:
    """Create a ResearchCrew instance."""
    return ResearchCrew()


def run_crew_research(question: str, **kwargs) -> Any:
    """Convenience: build crew and run."""
    crew = build_research_crew()
    return crew.run_flow(question, **kwargs)
