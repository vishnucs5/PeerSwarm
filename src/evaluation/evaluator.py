"""
Evaluator — runs quality evaluations on research outputs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.evaluation.metrics import score_to_dict
from src.models.quality import QualityScore
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResearchEvaluator:
    """
    Evaluates research quality across multiple dimensions.
    Can run standalone evaluation on existing reports or during the flow.
    """

    def __init__(self):
        from src.crew.agents import create_critic_agent

        self.critic = create_critic_agent()

    def evaluate_report(self, report_path: Path) -> QualityScore | None:
        """Evaluate a saved report file."""
        if not report_path.exists():
            logger.error(f"Report not found: {report_path}")
            return None

        try:
            content = report_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading report: {e}")
            return None

        from src.models.research import FindingCluster, Synthesis

        synthesis = Synthesis(
            question="Evaluating saved report",
            plan_id="",
            executive_summary=content[:500],
            clusters=[FindingCluster(theme="report", findings=[])],
        )

        from src.crew.agents.base import AgentContext

        ctx = AgentContext(question=synthesis.question)
        score = self.critic.execute(ctx, synthesis=synthesis, findings=[])
        return score

    def evaluate_from_state(self, state: Any) -> QualityScore:
        """Evaluate quality from a flow state."""
        from src.crew.agents.base import AgentContext

        ctx = AgentContext(question=state.question, iteration=state.iteration)
        findings = state.get_all_findings() if hasattr(state, "get_all_findings") else []
        score = self.critic.execute(ctx, synthesis=state.synthesis, findings=findings)
        return score


class BatchEvaluator:
    """
    Batch evaluation on a test set of questions.
    Used for regression testing and benchmarking.
    """

    def __init__(self, output_dir: Path | None = None):
        settings = get_settings()
        self.output_dir = output_dir or settings.storage.output_dir / "evaluations"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_question(self, question: str) -> dict[str, Any]:
        """Run a single evaluation."""
        from src.flows.research_flow import ResearchFlow

        flow = ResearchFlow(question=question, max_iterations=1)
        flow.kickoff()

        state = flow.state
        score = state.quality_score

        result = {
            "question": question,
            "run_id": state.run_id,
            "iterations": state.iteration,
            "quality_score": score_to_dict(score) if score else None,
            "total_findings": len(state.get_all_findings())
            if hasattr(state, "get_all_findings")
            else 0,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return result

    def run_evaluation_suite(self, questions: list[str], label: str = "default") -> Path:
        """Run evaluation on a list of questions and save results."""
        results = []
        for i, question in enumerate(questions):
            logger.info(f"Evaluating [{i + 1}/{len(questions)}]: {question[:60]}...")
            try:
                result = self.evaluate_question(question)
                results.append(result)
            except Exception as e:
                logger.error(f"Error evaluating '{question[:50]}': {e}")
                results.append(
                    {
                        "question": question,
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        summary = self._compute_summary(results)
        report = {
            "label": label,
            "timestamp": datetime.now(UTC).isoformat(),
            "total": len(questions),
            "completed": sum(1 for r in results if "error" not in r),
            "failed": sum(1 for r in results if "error" in r),
            "summary": summary,
            "results": results,
        }

        output_path = (
            self.output_dir / f"eval_{label}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        )
        output_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info(f"Evaluation suite saved to {output_path}")
        return output_path

    def _compute_summary(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute summary statistics."""
        valid = [r for r in results if r.get("quality_score")]
        if not valid:
            return {"avg_quality": 0, "min_quality": 0, "max_quality": 0, "avg_iterations": 0}

        scores = [r["quality_score"]["overall"] for r in valid if r.get("quality_score")]
        iterations = [r["iterations"] for r in valid]
        findings = [r["total_findings"] for r in valid]

        return {
            "avg_quality": round(sum(scores) / len(scores), 2) if scores else 0,
            "min_quality": min(scores) if scores else 0,
            "max_quality": max(scores) if scores else 0,
            "avg_iterations": round(sum(iterations) / len(iterations), 1) if iterations else 0,
            "avg_findings": round(sum(findings) / len(findings), 1) if findings else 0,
        }


def get_evaluator() -> ResearchEvaluator:
    return ResearchEvaluator()


def get_batch_evaluator() -> BatchEvaluator:
    return BatchEvaluator()
