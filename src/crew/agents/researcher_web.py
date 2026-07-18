"""
Web researcher agent - searches for industry reports, news, and web content.
"""

from __future__ import annotations

from src.config import get_model_for_agent
from src.crew.agents.base import AgentContext, BaseAgent
from src.models.research import EvidenceType, ResearchFinding
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WebResearcherAgent(BaseAgent):
    """Researcher B - focuses on web/industry sources."""

    def __init__(self, model: str | None = None, verbose: bool = False):
        from src.tools.knowledge_base import get_kb_tool
        from src.tools.web_search import get_web_search_tool

        super().__init__(
            role="Web Researcher",
            goal="Find industry reports, news articles, blog posts, and practitioner perspectives",
            backstory="""You are an expert web researcher skilled at finding current, relevant 
information from across the internet. You search for industry reports, news articles, 
blog posts, documentation, and practitioner perspectives. You assess source credibility 
and extract actionable insights from diverse web sources.""",
            tools=[
                get_web_search_tool(),
                get_kb_tool(),
            ],
            model=model or get_model_for_agent("researcher_b"),
            verbose=verbose,
        )

    def execute(self, context: AgentContext, **kwargs) -> list[ResearchFinding]:
        """Execute web research for a sub-question."""
        sub_question = kwargs.get("sub_question", "")
        search_terms = kwargs.get("search_terms", [sub_question])

        logger.info(f"Web researching: {sub_question[:60]}...")

        from src.tools.web_search import get_web_search_tool

        web = get_web_search_tool()

        findings = []
        for term in search_terms[:2]:
            results = web.search(term, max_results=5)
            for r in results:
                if len(findings) >= 6:
                    break

                evidence_type = EvidenceType.INDUSTRY_REPORT
                if content_lower := r.content.lower():
                    if "blog" in content_lower:
                        evidence_type = EvidenceType.BLOG_POST
                    elif "news" in content_lower:
                        evidence_type = EvidenceType.NEWS_ARTICLE
                    elif "documentation" in content_lower or "doc" in content_lower:
                        evidence_type = EvidenceType.DOCUMENTATION

                finding = ResearchFinding(
                    sub_question_id=kwargs.get("sub_question_id", ""),
                    researcher="researcher_b",
                    claim=r.title,
                    evidence=r.content[:2000],
                    evidence_type=evidence_type,
                    source=r.url,
                    citation=f"[{r.title}]({r.url})",
                    confidence=min(0.5 + r.score * 0.4, 0.95),
                    relevance=0.8,
                    tags=[],
                    metadata={
                        "title": r.title,
                        "url": r.url,
                        "source_type": evidence_type.value,
                        "score": r.score,
                    },
                )
                findings.append(finding)

        logger.info(f"Web research found {len(findings)} findings")
        return findings


def create_web_researcher(model: str | None = None, verbose: bool = False) -> WebResearcherAgent:
    return WebResearcherAgent(model=model, verbose=verbose)
