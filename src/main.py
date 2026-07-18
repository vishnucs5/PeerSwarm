"""
Multi-Agent Research Lab — CLI entry point.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from src.utils.logger import configure_logging, get_logger

app = typer.Typer(
    name="research-lab",
    help="Multi-Agent Research Lab — AI-powered research with quality loops",
    add_completion=False,
)

logger = get_logger(__name__)


@app.command()
def run(
    question: str = typer.Argument(..., help="Research question to investigate"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path for report"),
    max_iterations: int = typer.Option(
        3, "--max-iterations", "-i", help="Maximum quality loop iterations"
    ),
    quality_threshold: float = typer.Option(
        8.0, "--threshold", "-t", help="Quality threshold (0-10)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output results as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Run a full research cycle on a question."""
    if verbose:
        configure_logging(level="DEBUG")
    else:
        configure_logging(level="INFO")

    logger.info(f"Starting research: {question[:80]}...")

    from src.flows.research_flow import run_research

    state = run_research(
        question=question,
        max_iterations=max_iterations,
        quality_threshold=quality_threshold,
    )

    score = state.quality_score.overall if state.quality_score else 0
    findings_count = len(state.get_all_findings()) if hasattr(state, "get_all_findings") else 0

    if json_output:
        result = {
            "question": question,
            "run_id": state.run_id,
            "status": state.current_step,
            "iterations": state.iteration,
            "quality_score": score,
            "total_findings": findings_count,
        }
        print(json.dumps(result, indent=2))
    else:
        from src.evaluation.metrics import format_score_summary

        if state.quality_score:
            print("\n" + "=" * 50)
            print(format_score_summary(state.quality_score))
            print("=" * 50 + "\n")

        print(f"Run ID: {state.run_id}")
        print(f"Question: {question}")
        print(f"Iterations: {state.iteration}")
        print(f"Findings: {findings_count}")
        print(f"Status: {state.current_step}")
        print(f"Output: {output or getattr(state, '_output_path', 'N/A')}")


@app.command()
def plan(
    question: str = typer.Argument(..., help="Research question to plan"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Generate a research plan without executing it."""
    configure_logging(level="WARNING")

    from src.crew.tasks import create_planning_task

    planning = create_planning_task()
    plan = planning.execute(question)

    if json_output:
        print(plan.model_dump_json(indent=2))
    else:
        print(f"\nResearch Plan: {question}\n")
        for i, sq in enumerate(plan.sub_questions, 1):
            print(f"  {i}. [{sq.assigned_researcher}] {sq.question}")
            print(f"     Priority: {sq.priority.value}")
            print(f"     Strategy: {sq.strategy.value}")
            print(f"     Terms: {', '.join(sq.search_terms)}")
            print()
        print(f"Risk Assessment: {json.dumps(plan.risk_assessment, indent=2)}")
        print(f"Success Criteria: {[f'{i + 1}. {c}' for i, c in enumerate(plan.success_criteria)]}")


@app.command()
def evaluate(
    report_path: Path = typer.Argument(..., help="Path to report file"),
):
    """Evaluate an existing research report."""
    configure_logging(level="INFO")

    from src.evaluation import get_evaluator

    evaluator = get_evaluator()
    score = evaluator.evaluate_report(report_path)

    if score:
        from src.evaluation.metrics import format_score_summary

        print("\n" + "=" * 50)
        print(format_score_summary(score))
        print("=" * 50 + "\n")
    else:
        print("Failed to evaluate report.")


@app.command()
def list_reports(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of reports to list"),
):
    """List recent research reports."""
    configure_logging(level="WARNING")

    from src.memory import get_run_history

    history = get_run_history()
    runs = history.list_runs(limit=limit)

    if not runs:
        print("No research runs found.")
        return

    print(f"\nRecent Research Runs (last {len(runs)}):\n")
    for i, run in enumerate(runs, 1):
        score = ""
        if run.quality_score:
            overall = run.quality_score.get("overall", "?")
            score = f" [Quality: {overall}/10]"
        print(f"  {i}. [{run.status}] {run.question[:70]}...{score}")
        print(
            f"     ID: {run.id}  |  Iterations: {run.iterations}  |  {run.created_at.strftime('%Y-%m-%d %H:%M') if run.created_at else 'N/A'}"
        )
        print()


@app.command()
def stats():
    """Show research system statistics."""
    configure_logging(level="WARNING")

    from src.memory import get_run_history

    history = get_run_history()
    stats = history.get_stats()

    print("\n" + "=" * 50)
    print("Research Lab Statistics")
    print("=" * 50)
    for key, value in stats.items():
        print(f"  {key.replace('_', ' ').title():<30} {value}")
    print("=" * 50 + "\n")


@app.command()
def version():
    """Show version information."""
    print("Multi-Agent Research Lab v0.1.0")
    print("Python:", sys.version.split()[0])


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
