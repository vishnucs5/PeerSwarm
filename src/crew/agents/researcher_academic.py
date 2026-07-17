"""
Academic researcher agent - searches for academic papers and technical literature.
"""
from __future__ import annotations

from src.config import get_model_for_agent
from src.crew.agents.base import AgentContext, BaseAgent
from src.models.research import EvidenceType, ResearchFinding
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AcademicResearcherAgent(BaseAgent):
    """Researcher A - focuses on academic sources."""

    def __init__(self, model: str | None = None, verbose: bool = False):
        from src.tools.arxiv_tool import get_arxiv_tool
        from src.tools.knowledge_base import get_kb_tool
        from src.tools.pdf_reader import get_pdf_reader_tool

        super().__init__(
            role="Academic Researcher",
            goal="Find and analyze academic papers, technical reports, and scholarly sources",
            backstory="""You are an expert academic researcher with access to arXiv and other 
scholarly databases. You excel at finding relevant papers, extracting key findings, 
and assessing the credibility of academic sources. You carefully read PDFs and 
distill complex technical information into clear, usable findings.""",
            tools=[
                get_arxiv_tool(),
                get_pdf_reader_tool(),
                get_kb_tool(),
            ],
            model=model or get_model_for_agent("researcher_a"),
            verbose=verbose,
        )

    def execute(self, context: AgentContext, **kwargs) -> list[ResearchFinding]:
        """Execute academic research for a sub-question."""
        sub_question = kwargs.get("sub_question", "")
        search_terms = kwargs.get("search_terms", [sub_question])

        logger.info(f"Academic researching: {sub_question[:60]}...")

        from src.tools.arxiv_tool import get_arxiv_tool
        arxiv = get_arxiv_tool()

        findings = []
        for term in search_terms[:2]:
            results = arxiv.search(term, max_results=5)
            for r in results:
                if len(findings) >= 8:
                    break

                confidence = 0.7
                if r.doi:
                    confidence += 0.15
                if r.journal_ref:
                    confidence += 0.15

                finding = ResearchFinding(
                    sub_question_id=kwargs.get("sub_question_id", ""),
                    researcher="researcher_a",
                    claim=r.title,
                    evidence=r.summary[:2000],
                    evidence_type=EvidenceType.ACADEMIC_PAPER,
                    source=r.id,
                    citation=f"{', '.join(r.authors[:3])}{' et al.' if len(r.authors) > 3 else ''} ({r.published.year if r.published else 'n.d.'})",
                    confidence=min(confidence, 1.0),
                    relevance=0.85,
                    tags=r.categories[:3],
                    metadata={
                        "title": r.title,
                        "authors": r.authors,
                        "year": r.published.year if r.published else None,
                        "doi": r.doi,
                        "pdf_url": r.pdf_url,
                        "categories": r.categories,
                    },
                )
                findings.append(finding)

        logger.info(f"Academic research found {len(findings)} findings")
        return findings


def create_academic_researcher(model: str | None = None, verbose: bool = False) -> AcademicResearcherAgent:
    return AcademicResearcherAgent(model=model, verbose=verbose)
