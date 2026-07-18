"""
Knowledge base researcher agent - retrieves prior research and internal knowledge.
"""

from __future__ import annotations

from src.config import get_model_for_agent
from src.crew.agents.base import AgentContext, BaseAgent
from src.models.research import EvidenceType, ResearchFinding
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KBResearcherAgent(BaseAgent):
    """Researcher C - focuses on internal knowledge base and prior research."""

    def __init__(self, model: str | None = None, verbose: bool = False):
        from src.tools.knowledge_base import get_kb_tool

        super().__init__(
            role="Knowledge Base Researcher",
            goal="Retrieve and synthesize prior research findings and knowledge graph entities",
            backstory="""You are an expert at navigating internal knowledge stores. You search 
past research runs in the vector database, explore entity relationships in the 
knowledge graph, and find relevant prior work. You connect current questions to 
existing knowledge and identify what has already been established.""",
            tools=[get_kb_tool()],
            model=model or get_model_for_agent("researcher_c"),
            verbose=verbose,
        )

    def execute(self, context: AgentContext, **kwargs) -> list[ResearchFinding]:
        """Execute KB research for a sub-question."""
        sub_question = kwargs.get("sub_question", "")

        logger.info(f"KB researching: {sub_question[:60]}...")

        from src.tools.knowledge_base import get_kb_tool

        kb = get_kb_tool()

        findings = []

        vector_results = kb.search(sub_question, top_k=5)
        for result in vector_results[:3]:
            finding = ResearchFinding(
                sub_question_id=kwargs.get("sub_question_id", ""),
                researcher="researcher_c",
                claim=result.entry.entity_name or "Prior research finding",
                evidence=result.entry.content[:2000],
                evidence_type=EvidenceType.KNOWLEDGE_BASE,
                source=f"kb_entry_{result.entry.id}",
                citation=f"[KB: {result.entry.type.value}]",
                confidence=min(result.score, 0.95),
                relevance=result.score,
                tags=result.entry.tags,
                metadata={
                    "source_run_id": result.entry.source_run_id,
                    "entry_type": result.entry.type.value,
                    "similarity_score": result.score,
                    "matched_text": result.matched_text,
                },
            )
            findings.append(finding)

        history_results = kb.get_history(sub_question, limit=3)
        for h in history_results:
            finding = ResearchFinding(
                sub_question_id=kwargs.get("sub_question_id", ""),
                researcher="researcher_c",
                claim=f"Prior research: {h['question'][:100]}",
                evidence=f"Previous research run on related topic with quality score {h.get('quality_score', {}).get('overall', 'N/A')}",
                evidence_type=EvidenceType.PERSONAL_KNOWLEDGE,
                source=f"run_{h['id']}",
                confidence=0.7,
                relevance=0.6,
                tags=[],
                metadata={
                    "run_id": h["id"],
                    "previous_question": h["question"],
                    "previous_status": h["status"],
                },
            )
            findings.append(finding)

        logger.info(f"KB research found {len(findings)} findings")
        return findings


def create_kb_researcher(model: str | None = None, verbose: bool = False) -> KBResearcherAgent:
    return KBResearcherAgent(model=model, verbose=verbose)
