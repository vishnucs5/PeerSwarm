"""
Writing task - Writer produces final research report.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.crew.agents.base import AgentContext
from src.crew.agents.writer import WriterAgent
from src.models.quality import QualityScore
from src.models.research import FinalReport, Synthesis
from src.utils.exporters import export_markdown
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WritingTask:
    """Task that produces the final research report."""

    def __init__(self, writer_agent: WriterAgent):
        self.agent = writer_agent

    def execute(self, synthesis: Synthesis, quality_score: QualityScore | None = None,
                context: AgentContext | None = None,
                output_path: Path | None = None) -> FinalReport:
        """Write the final report and optionally save to file."""
        ctx = context or AgentContext(question=synthesis.question)
        report = self.agent.execute(ctx, synthesis=synthesis, quality_score=quality_score)

        if output_path:
            output_path = export_markdown(report, output_path)
            self._log_report(report, output_path)
        else:
            self._log_report(report)

        return report

    def execute_with_warning(self, synthesis: Synthesis,
                              quality_score: QualityScore,
                              context: AgentContext | None = None,
                              output_path: Path | None = None) -> FinalReport:
        """Write report with a quality warning banner."""
        report = self.execute(synthesis, quality_score, context, output_path)

        warning = (
            "\n\n> ⚠️ **Quality Warning:** This report was generated after reaching "
            f"the maximum number of revision iterations. "
            f"Quality score: {quality_score.overall}/10. "
            "Consider running additional research for higher quality.\n"
        )
        report.markdown += warning

        logger.warning(f"Report written with quality warning (score: {quality_score.overall})")
        return report

    def _log_report(self, report: FinalReport, output_path: Path | None = None):
        sections = len(report.sections) if hasattr(report, 'sections') else 0
        refs = len(report.references) if hasattr(report, 'references') else 0
        path_str = f" -> {output_path}" if output_path else ""
        logger.info(f"Report generated: {sections} sections, {refs} references{path_str}")

        # Save structured report data as JSON alongside markdown
        json_path = output_path.with_suffix('.json') if output_path else None
        if json_path:
            json_path.write_text(report.model_dump_json(indent=2))

    def to_crewai_task(self, crewai_agent) -> Any:
        try:
            from crewai import Task as CrewTask
            return CrewTask(
                description="""Write a comprehensive research report from the synthesis.

1. Executive summary (100-200 words)
2. 4-6 main sections with inline citations
3. Key takeaways
4. Limitations and future work
5. Full reference list

Use proper APA-style citations throughout.""",
                agent=crewai_agent,
                expected_output="""A complete FinalReport with:
- Markdown-formatted report
- Properly structured sections
- APA-style citations
- Clear writing suitable for the target audience""",
            )
        except ImportError:
            return None


def create_writing_task(writer: WriterAgent | None = None) -> WritingTask:
    if writer is None:
        from src.crew.agents import create_writer_agent
        writer = create_writer_agent()
    return WritingTask(writer)
