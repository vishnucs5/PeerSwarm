"""
Tasks package exports.
"""
from src.crew.tasks.analysis_task import AnalysisTask, create_analysis_task
from src.crew.tasks.critique_task import CritiqueTask, create_critique_task
from src.crew.tasks.planning_task import PlanningTask, create_planning_task
from src.crew.tasks.research_tasks import (
    AcademicResearchTask,
    KBResearchTask,
    WebResearchTask,
    create_research_task,
)
from src.crew.tasks.revision_task import RevisionTask, create_revision_task
from src.crew.tasks.writing_task import WritingTask, create_writing_task

__all__ = [
    "PlanningTask",
    "create_planning_task",
    "AcademicResearchTask",
    "WebResearchTask",
    "KBResearchTask",
    "create_research_task",
    "AnalysisTask",
    "create_analysis_task",
    "CritiqueTask",
    "create_critique_task",
    "RevisionTask",
    "create_revision_task",
    "WritingTask",
    "create_writing_task",
]
