"""
Evaluation package exports.
"""
from src.evaluation.evaluator import (
    BatchEvaluator,
    ResearchEvaluator,
    get_batch_evaluator,
    get_evaluator,
)
from src.evaluation.metrics import (
    compute_weighted_score,
    format_score_summary,
    get_failing_dimensions,
    score_to_color,
    score_to_dict,
    score_to_grade,
)

__all__ = [
    "compute_weighted_score",
    "score_to_grade",
    "score_to_color",
    "format_score_summary",
    "score_to_dict",
    "get_failing_dimensions",
    "ResearchEvaluator",
    "BatchEvaluator",
    "get_evaluator",
    "get_batch_evaluator",
]
