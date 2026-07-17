"""
PI (Planner) agent - decomposes research questions into structured plans.
"""
from __future__ import annotations

import json

from src.config import get_model_for_agent
from src.crew.agents.base import AgentContext, BaseAgent
from src.models.research import ResearchPlan, ResearchStrategy, SubQuestion, SubQuestionPriority
from src.utils.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are the Principal Investigator (PI), an expert research planner.
You decompose complex questions into structured, actionable research plans.

Your process:
1. Analyze the main question for scope, depth, and domain
2. Identify 3-5 key sub-questions that cover different aspects
3. Assign appropriate research strategies to each sub-question
4. Define success criteria and risk factors

Output valid JSON matching this schema:
{
  "original_question": "string",
  "sub_questions": [
    {
      "question": "string",
      "rationale": "string",
      "priority": "HIGH|MEDIUM|LOW",
      "strategy": "ACADEMIC_DEEP|INDUSTRY_SURVEY|GAP_ANALYSIS|COMPARATIVE|HISTORICAL",
      "assigned_researcher": "researcher_a|researcher_b|researcher_c",
      "search_terms": ["string"],
      "success_criteria": "string"
    }
  ],
  "overall_strategy": "string",
  "risk_assessment": {"key": "value"},
  "success_criteria": ["string"],
  "estimated_iterations": 1
}"""


class PlannerAgent(BaseAgent):
    """PI agent that creates research plans."""

    def __init__(self, model: str | None = None, verbose: bool = False):
        from src.tools.knowledge_base import get_kb_tool
        kb = get_kb_tool()
        super().__init__(
            role="Principal Investigator",
            goal="Decompose research questions into structured, actionable plans with 3-5 sub-questions",
            backstory="""You are a senior research director with decades of experience designing 
research studies across multiple domains. You excel at breaking down complex questions 
into manageable, well-scoped sub-questions. You understand research methodology deeply 
and can identify the right approach for each sub-question.""",
            tools=[kb],
            model=model or get_model_for_agent("planner"),
            verbose=verbose,
        )

    def execute(self, context: AgentContext, **kwargs) -> ResearchPlan:
        """Create a research plan from the question."""
        question = context.question
        logger.info(f"Planning research for: {question[:80]}...")

        plan = self._llm_plan(question, context)

        logger.info(f"Created research plan with {len(plan.sub_questions)} sub-questions")
        return plan

    def _llm_plan(self, question: str, context: AgentContext) -> ResearchPlan:
        """Generate a research plan via LLM with fallback to heuristic."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Research question: {question}\n\nProduce a structured ResearchPlan in JSON."},
        ]
        try:
            content, usage = self._llm_completion(messages, context)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            content = content.strip()
            data = json.loads(content)
            for sq in data.get("sub_questions", []):
                if "priority" in sq:
                    sq["priority"] = sq["priority"].lower()
                if "strategy" in sq:
                    sq["strategy"] = sq["strategy"].lower()
            return ResearchPlan.model_validate(data)
        except Exception as e:
            logger.warning(f"LLM plan failed ({e}), using heuristic fallback")
            return self._heuristic_plan(question)

    def _heuristic_plan(self, question: str) -> ResearchPlan:
        """Fallback heuristic plan generation."""
        return ResearchPlan(
            original_question=question,
            sub_questions=[
                SubQuestion(
                    question=f"What is the current state of research on {question}?",
                    rationale="Establish baseline understanding of the topic",
                    priority=SubQuestionPriority.HIGH,
                    strategy=ResearchStrategy.ACADEMIC_DEEP,
                    assigned_researcher="researcher_a",
                    search_terms=[question],
                    success_criteria="Find 3+ recent papers or sources",
                ),
                SubQuestion(
                    question=f"What are the key developments and trends in {question}?",
                    rationale="Identify recent progress and emerging directions",
                    priority=SubQuestionPriority.HIGH,
                    strategy=ResearchStrategy.INDUSTRY_SURVEY,
                    assigned_researcher="researcher_b",
                    search_terms=[f"latest developments {question}", f"trends in {question}"],
                    success_criteria="Identify 3+ key trends or milestones",
                ),
            ],
            overall_strategy=f"Multi-faceted research combining academic literature review with industry analysis for: {question}",
            risk_assessment={
                "scope_creep": "Question may be too broad - focus on core aspects",
                "source_quality": "Verify credibility of non-academic sources",
            },
            success_criteria=[
                "All sub-questions answered with evidence",
                "Citations from credible sources",
                "Clear synthesis with actionable insights",
            ],
            estimated_iterations=1,
        )


def create_planner_agent(model: str | None = None, verbose: bool = False) -> PlannerAgent:
    return PlannerAgent(model=model, verbose=verbose)
