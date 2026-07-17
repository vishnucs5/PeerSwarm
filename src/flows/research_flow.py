"""
Research Flow — CrewAI Flow state machine with quality loop.
"""
from __future__ import annotations

import asyncio
from typing import Literal
from uuid import uuid4

from src.config import get_settings
from src.flows.state import ResearchState
from src.models.quality import QualityGateResult
from src.models.research import ResearchFinding
from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from crewai.flow import Flow, listen, router, start
    CREWAI_FLOW_AVAILABLE = True
except ImportError:
    class Flow:
        def __class_getitem__(cls, item):
            return cls
        def __init__(self, **kwargs):
            self.state = kwargs.get('state')

    def _noop(x=None, **_kwargs):
        return lambda f: f
    start = listen = router = _noop
    CREWAI_FLOW_AVAILABLE = False


class ResearchFlow(Flow[ResearchState]):
    """
    End-to-end research flow with quality loop.

    Flow:
      plan -> parallel_research -> analyze -> quality_gate
        ^                          |          |
        |---- revise_research -----|          |
        |---- revise_analysis ----------------|
        v                          |          |
      write_report <--------------------------|
        |
      finalize
    """

    def __init__(self, question: str, **kwargs):
        super().__init__()
        self.state.question = question
        self.state.run_id = kwargs.get("run_id", str(uuid4())[:12])
        self.state.trace_id = kwargs.get("trace_id", "")
        self.state.max_iterations = kwargs.get("max_iterations", get_settings().quality.max_iterations)
        self.state.tags = kwargs.get("tags", [])

        from src.crew.tasks import (
            create_analysis_task,
            create_critique_task,
            create_planning_task,
            create_research_task,
            create_revision_task,
            create_writing_task,
        )

        self.planning = create_planning_task()
        self.researcher_a = create_research_task("researcher_a")
        self.researcher_b = create_research_task("researcher_b")
        self.researcher_c = create_research_task("researcher_c")
        self.analysis = create_analysis_task()
        self.critique = create_critique_task()
        self.revision = create_revision_task()
        self.writing = create_writing_task()

        settings = get_settings()
        self.quality_threshold = kwargs.get("quality_threshold", settings.quality.threshold)
        self.hard_gate_threshold = kwargs.get("hard_gate_threshold", settings.quality.hard_gate_threshold)
        self.max_iterations = self.state.max_iterations

        # Cost tracking
        from src.utils.cost_tracker import get_model_cost
        self._cost_tracker = get_model_cost
        self._costs_by_model: dict[str, float] = {}

    def _track_cost(self, model: str, prompt_tokens: int, completion_tokens: int):
        """Track cost for an LLM call."""
        cost = self._cost_tracker(model, prompt_tokens, completion_tokens)
        self._costs_by_model[model] = self._costs_by_model.get(model, 0) + cost
        total = sum(self._costs_by_model.values())
        self.state.token_usage.cost_estimate = round(total, 4)

    def _track_agent_usage(self, task_obj) -> None:
        """Read _last_usage from task's agent and record cost."""
        agent = getattr(task_obj, 'agent', None)
        if agent is None:
            return
        usage = getattr(agent, '_last_usage', None)
        if usage:
            self._track_cost(
                agent.model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            self.state.token_usage.add(
                agent=agent.role,
                model=agent.model,
                prompt=usage.get("prompt_tokens", 0),
                completion=usage.get("completion_tokens", 0),
            )
            agent._last_usage = None

    # ── STEP 1: Planning ────────────────────────────────────────────────

    @start()
    def plan(self):
        """Decompose question into research plan."""
        self.state.current_step = "planning"
        logger.info(f"[{self.state.run_id}] Planning: {self.state.question[:60]}...")
        plan = self.planning.execute(self.state.question)
        self._track_agent_usage(self.planning)
        self.state.plan = plan
        logger.info(f"[{self.state.run_id}] Plan: {len(plan.sub_questions)} sub-questions")
        return plan

    # ── STEP 2: Parallel Research ──────────────────────────────────────

    @listen(plan)
    async def parallel_research(self):
        """Run all 3 researchers in parallel."""
        self.state.current_step = "researching"
        self.state.iteration += 1
        logger.info(f"[{self.state.run_id}] Research iteration {self.state.iteration}")

        plan = self.state.plan
        if not plan:
            logger.warning("No plan available, skipping research")
            return None

        tasks = []
        for sq in plan.sub_questions:
            agent_map = {
                "researcher_a": self.researcher_a,
                "researcher_b": self.researcher_b,
                "researcher_c": self.researcher_c,
            }
            task_fn = agent_map.get(sq.assigned_researcher)
            if task_fn:
                tasks.append(asyncio.to_thread(
                    task_fn.execute, sq,
                ))

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"[{self.state.run_id}] Parallel research error: {e}")
            results = []

        findings_map: dict[str, list[ResearchFinding]] = {
            "researcher_a": [],
            "researcher_b": [],
            "researcher_c": [],
        }
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Researcher error: {result}")
                continue
            for finding in result:
                key = finding.researcher
                findings_map.setdefault(key, []).append(finding)

        self.state.findings = findings_map
        total = sum(len(v) for v in findings_map.values())
        logger.info(f"[{self.state.run_id}] Research complete: {total} total findings")
        return findings_map

    # ── STEP 3: Analysis / Synthesis ───────────────────────────────────

    @listen(parallel_research)
    def analyze(self):
        """Synthesize findings into coherent analysis."""
        self.state.current_step = "analyzing"
        findings = self.state.get_all_findings()
        plan = self.state.plan

        if not findings:
            logger.warning(f"[{self.state.run_id}] No findings to analyze")
            from src.models.research import Synthesis
            self.state.synthesis = Synthesis(
                question=self.state.question,
                plan_id=plan.id if plan else "",
            )
            return self.state.synthesis

        synthesis = self.analysis.execute(findings, plan)
        self._track_agent_usage(self.analysis)
        self.state.synthesis = synthesis
        clusters = len(synthesis.clusters) if hasattr(synthesis, 'clusters') else 0
        insights = len(synthesis.key_insights) if hasattr(synthesis, 'key_insights') else 0
        logger.info(f"[{self.state.run_id}] Analysis: {clusters} clusters, {insights} insights")
        return synthesis

    # ── STEP 4: Quality Gate ──────────────────────────────────────────

    @listen(analyze)
    def quality_gate(self):
        """Evaluate synthesis quality and produce routing decision."""
        self.state.current_step = "evaluating"
        findings = self.state.get_all_findings()
        synthesis = self.state.synthesis

        if not synthesis:
            logger.warning(f"[{self.state.run_id}] No synthesis to evaluate")
            from src.models.quality import QualityGateResult, QualityScore
            result = QualityGateResult(
                passed=False,
                score=QualityScore(factual_accuracy=5, source_quality=5,
                                    logical_coherence=5, completeness=5, clarity=5,
                                    overall=5.0, iteration=self.state.iteration),
                action="revise_analysis",
                reason="No synthesis available",
                iteration=self.state.iteration,
            )
            return result

        previous_score = self.state.quality_score
        result = self.critique.execute(
            synthesis=synthesis,
            findings=findings,
            previous_score=previous_score,
            quality_threshold=self.quality_threshold,
            hard_gate_threshold=int(self.hard_gate_threshold),
            max_iterations=self.max_iterations,
        )
        self._track_agent_usage(self.critique)
        self.state.quality_score = result.score
        logger.info(f"[{self.state.run_id}] Quality gate: {result.score.overall}/10 -> {result.action}")
        return result

    # ── STEP 5: Routing ───────────────────────────────────────────────

    @router(quality_gate)
    def route_quality(self, result: QualityGateResult) -> Literal[
        "write", "revise_research", "revise_analysis", "revise_write", "max_iterations"
    ]:
        """Route to next step based on quality evaluation."""
        if result.action == "write":
            return "write"

        if self.state.iteration >= self.max_iterations:
            logger.warning(f"[{self.state.run_id}] Max iterations ({self.max_iterations}) reached")
            return "max_iterations"

        if result.action == "revise_research":
            return "revise_research"
        if result.action == "revise_analysis":
            return "revise_analysis"
        if result.action == "revise_write":
            return "revise_write"

        return "revise_analysis"

    # ── STEP 6a: Revise Research ─────────────────────────────────────

    @listen("revise_research")
    def perform_revise_research(self):
        """Conduct targeted additional research."""
        self.state.current_step = "revising_research"
        score = self.state.quality_score
        logger.info(f"[{self.state.run_id}] Revising research based on critic feedback")

        result = self.revision.execute(
            target="researcher_a",
            quality_result=self._current_quality_result(),
            findings=self.state.findings,
            current_synthesis=self.state.synthesis,
            plan=self.state.plan,
        )
        if result.get("revised"):
            self.state.findings = result["findings"]
            logger.info(f"[{self.state.run_id}] Research revised, re-analyzing...")
            return self.analyze()
        return result

    # ── STEP 6b: Revise Analysis ─────────────────────────────────────

    @listen("revise_analysis")
    def perform_revise_analysis(self):
        """Re-analyze with critic's focus areas."""
        self.state.current_step = "revising_analysis"
        logger.info(f"[{self.state.run_id}] Revising analysis based on critic feedback")

        result = self.revision.execute(
            target="analyst",
            quality_result=self._current_quality_result(),
            findings=self.state.findings,
            current_synthesis=self.state.synthesis,
            plan=self.state.plan,
        )
        if result.get("revised") and result.get("synthesis"):
            self.state.synthesis = result["synthesis"]
            logger.info(f"[{self.state.run_id}] Analysis revised, re-evaluating...")
            return self.quality_gate()
        return result

    # ── STEP 7a: Write Report ────────────────────────────────────────

    @listen("write")
    def write_report(self):
        """Write final research report."""
        log_msg = f"[{self.state.run_id}] Writing final report..."
        return self._write_report(
            self.writing.execute, "writing", logger.info, log_msg
        )

    @listen("max_iterations")
    def write_with_warning(self):
        """Write report with quality warning banner."""
        score = self.state.quality_score
        log_msg = f"[{self.state.run_id}] Writing report with quality warning (score: {score.overall if score else 'N/A'})"
        logger.warning(log_msg)
        return self._write_report(
            self.writing.execute_with_warning, "writing_warning", logger.warning, log_msg
        )

    def _write_report(self, execution_fn, step: str, log_fn, log_msg: str):
        """Shared write logic for normal and warning report paths."""
        self.state.current_step = step
        log_fn(log_msg)

        output_dir = get_settings().storage.output_dir
        output_path = output_dir / f"{self.state.run_id}.md"

        report = execution_fn(
            synthesis=self.state.synthesis,
            quality_score=self.state.quality_score,
            output_path=output_path,
        )
        self._track_agent_usage(self.writing)
        self.state.current_step = "completed"
        logger.info(f"[{self.state.run_id}] Report saved to {output_path}")
        return report

    # ── Helpers ──────────────────────────────────────────────────────

    # ── STEP 6c: Revise Writing ─────────────────────────────────────

    @listen("revise_write")
    def perform_revise_writing(self):
        """Revise writing based on critic feedback (falls back to analysis revision)."""
        logger.info(f"[{self.state.run_id}] Revising writing based on critic feedback")
        return self.perform_revise_analysis()

    def _current_quality_result(self) -> QualityGateResult:
        """Build a QualityGateResult from current state."""
        from src.models.quality import QualityGateResult
        score = self.state.quality_score
        return QualityGateResult(
            passed=False,
            score=score or self._default_score(),
            action="revise_analysis",
            reason="Quality below threshold",
            iteration=self.state.iteration,
            max_iterations=self.max_iterations,
        )

    def _default_score(self):
        from src.models.quality import QualityScore
        return QualityScore(
            factual_accuracy=5, source_quality=5, logical_coherence=5,
            completeness=5, clarity=5, overall=5.0,
            iteration=self.state.iteration,
        )


def run_research(
    question: str,
    max_iterations: int | None = None,
    quality_threshold: float | None = None,
    tags: list[str] | None = None,
) -> ResearchState:
    """Run the full research flow and return final state."""
    settings = get_settings()
    inputs = {
        "question": question,
        "run_id": str(uuid4())[:12],
        "max_iterations": max_iterations or settings.quality.max_iterations,
        "quality_threshold": quality_threshold or settings.quality.threshold,
        "tags": tags or [],
    }
    flow = ResearchFlow(**inputs)
    flow.kickoff(inputs=inputs)

    state = flow.state
    duration = state.duration_seconds if hasattr(state, 'duration_seconds') else 0
    score = state.quality_score.overall if state.quality_score else 0
    total_findings = len(state.get_all_findings()) if hasattr(state, 'get_all_findings') else 0

    cost_str = f", cost=${state.token_usage.cost_estimate:.4f}" if state.token_usage.cost_estimate else ""
    logger.info(f"Research complete: {score}/10, {total_findings} findings, "
                f"{duration}s, {state.iteration} iterations{cost_str}")
    return state


async def run_research_async(
    question: str,
    max_iterations: int | None = None,
    quality_threshold: float | None = None,
    tags: list[str] | None = None,
) -> ResearchState:
    """Run the research flow asynchronously."""
    return await asyncio.to_thread(run_research, question, max_iterations, quality_threshold, tags)
