"""
Metrics and evaluation utilities for quality assessment.
"""

from __future__ import annotations

from typing import Any

from src.models.quality import QualityDimension, QualityScore
from src.utils.logger import get_logger

logger = get_logger(__name__)


_DIMENSION_MAP = {
    "factual_accuracy": QualityDimension.FACTUAL_ACCURACY,
    "source_quality": QualityDimension.SOURCE_QUALITY,
    "logical_coherence": QualityDimension.LOGICAL_COHERENCE,
    "completeness": QualityDimension.COMPLETENESS,
    "clarity": QualityDimension.CLARITY,
}


def _get_dimension_values(score: QualityScore) -> dict[str, int]:
    """Extract dimension scores as dict."""
    return {
        "factual_accuracy": score.factual_accuracy,
        "source_quality": score.source_quality,
        "logical_coherence": score.logical_coherence,
        "completeness": score.completeness,
        "clarity": score.clarity,
    }


def compute_weighted_score(
    scores: dict[str, int], weights: dict[str, float] | None = None
) -> float:
    """Compute weighted average of dimension scores."""
    default_weights = {
        "factual_accuracy": 0.30,
        "source_quality": 0.20,
        "logical_coherence": 0.20,
        "completeness": 0.15,
        "clarity": 0.15,
    }
    w = weights or default_weights
    total_weight = sum(w.get(k, 0) for k in scores)
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(scores[k] * w.get(k, 0) for k in scores)
    return round(weighted_sum / total_weight, 1)


def compute_improvement_score(current: QualityScore, previous: QualityScore | None) -> float:
    """Compute improvement between iterations."""
    if previous is None:
        return 0.0
    return round(current.overall - previous.overall, 1)


def get_failing_dimensions(score: QualityScore, threshold: int = 6) -> list[QualityDimension]:
    """Get dimensions below threshold."""
    dims = _get_dimension_values(score)
    return [_DIMENSION_MAP[k] for k, v in dims.items() if v < threshold]


def score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 9.0:
        return "A"
    if score >= 8.0:
        return "A-"
    if score >= 7.0:
        return "B+"
    if score >= 6.5:
        return "B"
    if score >= 6.0:
        return "B-"
    if score >= 5.5:
        return "C+"
    if score >= 5.0:
        return "C"
    if score >= 4.0:
        return "D"
    return "F"


def score_to_color(score: float) -> str:
    """Get a color hex for a score."""
    if score >= 8:
        return "#22c55e"  # green
    if score >= 6:
        return "#eab308"  # yellow
    if score >= 4:
        return "#f97316"  # orange
    return "#ef4444"  # red


def format_score_summary(score: QualityScore) -> str:
    """Format a quality score as a readable summary string."""
    lines = [
        f"Quality Score: {score.overall}/10 ({score_to_grade(score.overall)})",
        "",
        "Dimension Scores:",
    ]
    dims = _get_dimension_values(score)
    for dim_key, val in dims.items():
        bar = "█" * val + "░" * (10 - val)
        dim_label = dim_key.replace("_", " ").title()
        lines.append(f"  {dim_label:<20} {val:>2}/10 {bar}")

    if score.hard_gate_failures:
        lines.append(f"\nHard Gate Failures ({len(score.hard_gate_failures)}):")
        for f in score.hard_gate_failures:
            lines.append(f"  ✗ {f.dimension.value}: {f.score} < {f.threshold}")

    if score.issues:
        lines.append(f"\nIssues ({len(score.issues)}):")
        for issue in score.issues:
            lines.append(f"  • {issue}")

    if score.suggestions:
        lines.append(f"\nSuggestions ({len(score.suggestions)}):")
        for s in score.suggestions:
            lines.append(f"  -> {s}")

    return "\n".join(lines)


def score_to_dict(score: QualityScore) -> dict[str, Any]:
    """Convert QualityScore to a serializable dict."""
    return {
        "overall": score.overall,
        "dimensions": _get_dimension_values(score),
        "grade": score_to_grade(score.overall),
        "hard_gate_failures": [
            {"dimension": f.dimension.value, "score": f.score, "threshold": f.threshold}
            for f in score.hard_gate_failures
        ],
        "issues": score.issues,
        "suggestions": score.suggestions,
        "iteration": score.iteration,
        "confidence": score.confidence,
        "improved": score.improved_from_previous,
    }
