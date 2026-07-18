"""
Writer agent - produces final research reports from synthesis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.config import get_model_for_agent
from src.crew.agents.base import AgentContext, BaseAgent
from src.models.research import FinalReport
from src.utils.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are an award-winning technical writer producing research reports.
Given a research synthesis, write a comprehensive markdown report with:
1. Executive summary
2. Main sections covering each theme
3. Key takeaways
4. Limitations and future work
5. References

Output the full report as a markdown string. Be thorough and cite findings."""


class WriterAgent(BaseAgent):
    """Writer agent that produces final research reports."""

    def __init__(self, model: str | None = None, verbose: bool = False):
        from src.tools.citation_tool import get_citation_tool
        from src.tools.knowledge_base import get_kb_tool

        super().__init__(
            role="Research Writer",
            goal="Produce clear, well-structured research reports with proper citations",
            backstory="""You are an award-winning technical writer who excels at transforming 
complex research into clear, engaging reports. You structure content logically, 
cite sources properly, and ensure every claim is supported. You write executive 
summaries that capture key insights and produce reports that are both rigorous 
and accessible.""",
            tools=[
                get_citation_tool(),
                get_kb_tool(),
            ],
            model=model or get_model_for_agent("writer"),
            verbose=verbose,
        )

    def execute(self, context: AgentContext, **kwargs) -> FinalReport:
        """Write the final research report."""
        synthesis = kwargs.get("synthesis", None)
        quality_score = kwargs.get("quality_score", None)

        logger.info(f"Writing report for: {context.question[:60]}...")

        if not synthesis:
            return FinalReport(
                synthesis_id="",
                title=f"Research Report: {context.question}",
                question=context.question,
                executive_summary="No synthesis available to write report.",
                sections=[],
                key_takeaways=[],
                limitations=["Synthesis was not generated"],
                future_work=["Begin with proper research and analysis"],
                references=[],
                markdown=f"# Research Report\n\n**Question:** {context.question}\n\n*No content generated.*",
            )

        sections = self._build_sections(synthesis)
        citations = self._gather_citations(synthesis)
        markdown = self._llm_write(context.question, synthesis, context) or self._generate_markdown(
            context.question, synthesis, sections, quality_score
        )

        report = FinalReport(
            synthesis_id=synthesis.id if hasattr(synthesis, "id") else "",
            title=self._generate_title(context.question),
            question=context.question,
            executive_summary=synthesis.executive_summary
            if hasattr(synthesis, "executive_summary")
            else "",
            sections=sections,
            key_takeaways=synthesis.key_insights if hasattr(synthesis, "key_insights") else [],
            limitations=synthesis.limitations if hasattr(synthesis, "limitations") else [],
            future_work=synthesis.future_work if hasattr(synthesis, "future_work") else [],
            references=citations,
            quality_score=quality_score.overall if quality_score else None,
            markdown=markdown,
        )

        logger.info(f"Report generated: {len(sections)} sections, {len(citations)} references")
        return report

    def _llm_write(self, question: str, synthesis: Any, context: AgentContext) -> str | None:
        """Generate report markdown via LLM with fallback to None."""
        summary = synthesis.executive_summary if hasattr(synthesis, "executive_summary") else ""
        clusters_text = ""
        if hasattr(synthesis, "clusters"):
            for c in synthesis.clusters:
                findings_text = "\n".join(f"  - {f.claim[:200]}" for f in c.findings[:3])
                clusters_text += f"\n### {c.theme}\n{findings_text}\n"
        insights = "\n".join(
            f"- {i}" for i in (synthesis.key_insights if hasattr(synthesis, "key_insights") else [])
        )
        limitations = "\n".join(
            f"- {l}" for l in (synthesis.limitations if hasattr(synthesis, "limitations") else [])
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Research Question: {question}\n\n"
                    f"Executive Summary: {summary[:500]}\n\n"
                    f"Themes:{clusters_text}\n\n"
                    f"Key Insights:\n{insights}\n\n"
                    f"Limitations:\n{limitations}\n\n"
                    "Write a comprehensive markdown research report."
                ),
            },
        ]
        try:
            content, usage = self._llm_completion(messages, context)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            return content.strip()
        except Exception as e:
            logger.warning(f"LLM writing failed ({e}), using heuristic fallback")
            return None

    def _generate_title(self, question: str) -> str:
        """Generate a report title from the question."""
        words = question.split()
        if len(words) <= 8:
            return f"Research Report: {question}"
        return f"Research Report: {' '.join(words[:7])}..."

    def _build_sections(self, synthesis: Any) -> list[dict[str, Any]]:
        """Build report sections from synthesis."""
        sections = []

        sections.append(
            {
                "title": "Executive Summary",
                "content": synthesis.executive_summary
                if hasattr(synthesis, "executive_summary")
                else "",
                "citations": [],
                "order": 0,
            }
        )

        if hasattr(synthesis, "clusters") and synthesis.clusters:
            for i, cluster in enumerate(synthesis.clusters):
                citations = []
                content_parts = []
                for f in cluster.findings[:3]:
                    if hasattr(f, "citation") and f.citation:
                        citations.append(f.citation)
                    content_parts.append(f"- {f.claim}")

                sections.append(
                    {
                        "title": cluster.theme,
                        "content": "\n".join(content_parts),
                        "citations": citations,
                        "order": i + 1,
                    }
                )

        sections.append(
            {
                "title": "Key Takeaways",
                "content": "\n".join(
                    f"- {i}"
                    for i in (synthesis.key_insights if hasattr(synthesis, "key_insights") else [])
                ),
                "citations": [],
                "order": len(sections) + 1,
            }
        )

        return sections

    def _gather_citations(self, synthesis: Any) -> list[str]:
        """Gather all citations."""
        citations = set()
        if hasattr(synthesis, "citations"):
            for key, value in synthesis.citations.items():
                citations.add(value)

        if hasattr(synthesis, "all_findings"):
            for f in synthesis.all_findings:
                if hasattr(f, "citation") and f.citation:
                    citations.add(f.citation)

        return sorted(list(citations))

    def _generate_markdown(
        self, question: str, synthesis: Any, sections: list[dict[str, Any]], quality_score: Any
    ) -> str:
        """Generate full markdown report."""
        lines = [
            f"# Research Report: {question}",
            "",
            f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "---",
            "",
        ]

        if quality_score:
            lines.extend(
                [
                    f"**Quality Score:** {quality_score.overall}/10",
                    "",
                ]
            )

        for section in sections:
            lines.extend(
                [
                    f"## {section['title']}",
                    "",
                    section["content"],
                    "",
                ]
            )

        citations = self._gather_citations(synthesis)
        if citations:
            lines.extend(
                [
                    "## References",
                    "",
                ]
            )
            for i, citation in enumerate(citations, 1):
                lines.append(f"{i}. {citation}")
            lines.append("")

        if hasattr(synthesis, "limitations") and synthesis.limitations:
            lines.extend(
                [
                    "## Limitations",
                    "",
                ]
            )
            for limitation in synthesis.limitations:
                lines.append(f"- {limitation}")
            lines.append("")

        if hasattr(synthesis, "future_work") and synthesis.future_work:
            lines.extend(
                [
                    "## Future Work",
                    "",
                ]
            )
            for item in synthesis.future_work:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)


def create_writer_agent(model: str | None = None, verbose: bool = False) -> WriterAgent:
    return WriterAgent(model=model, verbose=verbose)
