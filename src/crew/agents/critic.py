"""
Critic agent - evaluates research quality and produces quality scores with routing directives.
"""

from __future__ import annotations

import json
from typing import Any

from src.config import get_model_for_agent
from src.crew.agents.base import AgentContext, BaseAgent
from src.models.quality import (
    QualityGateResult,
    QualityScore,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a Quality Critic evaluating research synthesis quality.
Score each dimension from 0 (worst) to 10 (best). Consider:
- factual_accuracy: Are claims supported by evidence?
- source_quality: Are sources credible and diverse?
- logical_coherence: Is the narrative well-structured?
- completeness: Are all aspects covered?
- clarity: Is the writing clear and accessible?

Also list specific issues and actionable suggestions.
Output valid JSON:
{
  "factual_accuracy": 0-10,
  "source_quality": 0-10,
  "logical_coherence": 0-10,
  "completeness": 0-10,
  "clarity": 0-10,
  "issues": ["string"],
  "suggestions": ["string"],
  "confidence": 0.0-1.0
}"""


class CriticAgent(BaseAgent):
    """Critic agent that evaluates quality and routes revisions."""

    def __init__(self, model: str | None = None, verbose: bool = False):
        from src.tools.citation_tool import get_citation_tool
        from src.tools.self_evaluation import get_evaluation_tool

        super().__init__(
            role="Quality Critic",
            goal="Evaluate research quality across multiple dimensions and provide actionable revision directives",
            backstory="""You are an exacting research quality reviewer with expertise in 
evaluating academic and technical work. You assess factual accuracy, source quality, 
logical coherence, completeness, and clarity. You set high standards and can 
identify subtle issues. You route failures to the right agents for targeted fixes.""",
            tools=[
                get_evaluation_tool(),
                get_citation_tool(),
            ],
            model=model or get_model_for_agent("critic"),
            verbose=verbose,
        )

    def execute(self, context: AgentContext, **kwargs) -> QualityScore:
        """Evaluate synthesis quality and produce score."""
        synthesis = kwargs.get("synthesis", None)
        previous_score = kwargs.get("previous_score", None)
        findings = kwargs.get("findings", [])

        logger.info(f"Evaluating quality (iteration {context.iteration})")

        if not synthesis:
            score = QualityScore(
                factual_accuracy=5,
                source_quality=5,
                logical_coherence=5,
                completeness=5,
                clarity=5,
                overall=5.0,
                issues=["No synthesis provided to evaluate"],
                suggestions=["Generate a synthesis document first"],
                iteration=context.iteration,
                confidence=0.5,
            )
            return score

        score = self._llm_evaluate(synthesis, findings, context)
        if score is None:
            scores = self._evaluate_dimensions(synthesis, findings)
            issues = self._identify_issues(synthesis, scores)
            suggestions = self._generate_suggestions(synthesis, scores, issues)
            score = QualityScore(
                factual_accuracy=scores["factual_accuracy"],
                source_quality=scores["source_quality"],
                logical_coherence=scores["logical_coherence"],
                completeness=scores["completeness"],
                clarity=scores["clarity"],
                overall=self._compute_overall(scores),
                issues=issues,
                suggestions=suggestions,
                iteration=context.iteration,
                confidence=self._compute_confidence(scores),
                improved_from_previous=self._check_improvement(
                    self._compute_overall(scores),
                    previous_score.overall if previous_score else None,
                ),
                previous_overall=previous_score.overall if previous_score else None,
            )

        logger.info(f"Quality score: {score.overall}/10 (iteration {context.iteration})")
        return score

    def _llm_evaluate(
        self, synthesis: Any, findings: list[Any], context: AgentContext
    ) -> QualityScore | None:
        """Evaluate via LLM with fallback to None (use heuristic)."""
        summary = (
            synthesis.executive_summary
            if hasattr(synthesis, "executive_summary")
            else str(synthesis)
        )
        clusters_summary = []
        if hasattr(synthesis, "clusters"):
            for c in synthesis.clusters:
                clusters_summary.append(
                    f"{c.theme}: {len(c.findings)} findings - {c.summary[:200]}"
                )
        findings_summary = "\n".join(f"- {f.claim[:200]}" for f in findings[:10])

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Executive summary:\n{summary[:1000]}\n\n"
                    f"Clusters:\n{chr(10).join(clusters_summary[:5])}\n\n"
                    f"Findings:\n{findings_summary[:2000]}"
                ),
            },
        ]
        try:
            content, usage = self._llm_completion(messages, context)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            content = content.strip()
            data = json.loads(content)
            dims = {
                "factual_accuracy": data.get("factual_accuracy", 7),
                "source_quality": data.get("source_quality", 7),
                "logical_coherence": data.get("logical_coherence", 7),
                "completeness": data.get("completeness", 7),
                "clarity": data.get("clarity", 7),
            }
            dims = {k: max(0, min(10, v)) for k, v in dims.items()}
            overall = self._compute_overall(dims)
            return QualityScore(
                factual_accuracy=dims["factual_accuracy"],
                source_quality=dims["source_quality"],
                logical_coherence=dims["logical_coherence"],
                completeness=dims["completeness"],
                clarity=dims["clarity"],
                overall=overall,
                issues=data.get("issues", [])[:5],
                suggestions=data.get("suggestions", [])[:5],
                iteration=context.iteration,
                confidence=min(1.0, max(0.0, data.get("confidence", 0.8))),
            )
        except Exception as e:
            logger.warning(f"LLM evaluation failed ({e}), using heuristic fallback")
            return None

    def _evaluate_dimensions(self, synthesis: Any, findings: list[Any]) -> dict[str, int]:
        """Score each quality dimension."""
        scores = {}

        num_findings = len(findings) if findings else 0
        num_clusters = len(synthesis.clusters) if hasattr(synthesis, "clusters") else 0

        factual_accuracy = 7
        if num_findings >= 8:
            factual_accuracy = 8
        elif num_findings < 3:
            factual_accuracy = 4
        if hasattr(synthesis, "contradictions") and synthesis.contradictions:
            factual_accuracy = max(3, factual_accuracy - 2)
        scores["factual_accuracy"] = factual_accuracy

        source_quality = 7
        if hasattr(synthesis, "citations") and len(synthesis.citations) >= 5:
            source_quality = 8
        elif hasattr(synthesis, "citations") and len(synthesis.citations) < 2:
            source_quality = 4
        scores["source_quality"] = source_quality

        logical_coherence = 7
        if num_clusters >= 3:
            logical_coherence = 8
        elif num_clusters < 2:
            logical_coherence = 5
        if hasattr(synthesis, "executive_summary") and len(synthesis.executive_summary) > 50:
            logical_coherence = min(9, logical_coherence + 1)
        scores["logical_coherence"] = logical_coherence

        completeness = 7
        if hasattr(synthesis, "key_insights") and len(synthesis.key_insights) >= 3:
            completeness = 8
        else:
            completeness = 5
        if hasattr(synthesis, "limitations") and synthesis.limitations:
            completeness = min(9, completeness + 1)
        scores["completeness"] = completeness

        clarity = 7
        if hasattr(synthesis, "executive_summary") and synthesis.executive_summary:
            clarity = 8 if len(synthesis.executive_summary) > 100 else 6
        scores["clarity"] = clarity

        return scores

    def _compute_overall(self, scores: dict[str, int]) -> float:
        """Compute weighted overall score."""
        weights = {
            "factual_accuracy": 0.30,
            "source_quality": 0.20,
            "logical_coherence": 0.20,
            "completeness": 0.15,
            "clarity": 0.15,
        }
        overall = sum(scores[dim] * weights[dim] for dim in scores)
        return round(overall, 1)

    def _compute_confidence(self, scores: dict[str, int]) -> float:
        """Compute confidence in evaluation."""
        variance = max(scores.values()) - min(scores.values())
        if variance <= 1:
            return 0.9
        if variance <= 3:
            return 0.75
        return 0.6

    def _check_improvement(self, current: float, previous: float | None) -> bool:
        """Check if quality improved from previous iteration."""
        if previous is None:
            return False
        return current > previous

    def _identify_issues(self, synthesis: Any, scores: dict[str, int]) -> list[str]:
        """Identify specific quality issues."""
        issues = []

        if scores["factual_accuracy"] < 7:
            issues.append("Factual accuracy needs improvement - verify claims against sources")
        if scores["source_quality"] < 7:
            issues.append("Source quality is low - add more academic and credible sources")
        if scores["logical_coherence"] < 7:
            issues.append("Logical flow could be improved - restructure for better narrative")
        if scores["completeness"] < 7:
            issues.append("Research is incomplete - address more sub-questions or evidence gaps")
        if scores["clarity"] < 7:
            issues.append("Clarity needs improvement - simplify language and add structure")

        if hasattr(synthesis, "evidence_gaps") and synthesis.evidence_gaps:
            for gap in synthesis.evidence_gaps[:2]:
                issues.append(f"Evidence gap: {gap}")

        if hasattr(synthesis, "contradictions") and synthesis.contradictions:
            for c in synthesis.contradictions[:2]:
                issues.append(f"Contradiction: {c}")

        return issues[:5]

    def _generate_suggestions(
        self, synthesis: Any, scores: dict[str, int], issues: list[str]
    ) -> list[str]:
        """Generate actionable suggestions for improvement."""
        suggestions = []

        if scores["factual_accuracy"] < 7:
            suggestions.append("Cross-reference all factual claims with primary sources")
        if scores["source_quality"] < 7:
            suggestions.append("Include more peer-reviewed sources and verify URLs still active")
        if scores["logical_coherence"] < 7:
            suggestions.append("Add clearer topic sentences and transition paragraphs")
        if scores["completeness"] < 7:
            suggestions.append("Identify and address the most critical evidence gaps")
        if scores["clarity"] < 7:
            suggestions.append("Use simpler sentence structures and add examples")

        return suggestions[:5]

    def route_quality(self, score: QualityScore, max_iterations: int = 3) -> QualityGateResult:
        """Route to next action based on quality score."""
        hard_gate_threshold = 6
        overall_threshold = 8

        failure_dimensions = []
        for dim, value in score.dimension_scores.items():
            if value < hard_gate_threshold:
                failure_dimensions.append(dim)

        if score.iteration >= max_iterations:
            return QualityGateResult(
                passed=True,
                score=score,
                action="write",
                reason=f"Max iterations ({max_iterations}) reached",
                iteration=score.iteration,
                max_iterations=max_iterations,
                failing_dimensions=failure_dimensions,
            )

        if failure_dimensions:
            dim_to_action = {
                "factual_accuracy": "revise_research",
                "source_quality": "revise_research",
                "logical_coherence": "revise_analysis",
                "completeness": "revise_analysis",
                "clarity": "revise_write",
            }
            failed_dim = failure_dimensions[0]
            action = dim_to_action.get(failed_dim, "revise_analysis")
            return QualityGateResult(
                passed=False,
                score=score,
                action=action,
                reason=f"Hard gate failure: {failed_dim} = {score.dimension_scores[failed_dim]}",
                iteration=score.iteration,
                max_iterations=max_iterations,
                failing_dimensions=failure_dimensions,
            )

        if score.overall >= overall_threshold:
            return QualityGateResult(
                passed=True,
                score=score,
                action="write",
                reason=f"Quality threshold met: {score.overall}/{overall_threshold}",
                iteration=score.iteration,
                max_iterations=max_iterations,
                failing_dimensions=[],
            )

        priority_to_action = {
            "research": "revise_research",
            "analysis": "revise_analysis",
            "writing": "revise_write",
        }
        action = priority_to_action.get(score.revision_priority, "revise_analysis")
        return QualityGateResult(
            passed=False,
            score=score,
            action=action,
            reason=f"Below threshold: {score.overall}/{overall_threshold}, routing to {action}",
            iteration=score.iteration,
            max_iterations=max_iterations,
            failing_dimensions=[],
        )


def create_critic_agent(model: str | None = None, verbose: bool = False) -> CriticAgent:
    return CriticAgent(model=model, verbose=verbose)
