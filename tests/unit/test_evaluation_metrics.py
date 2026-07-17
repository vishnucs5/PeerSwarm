"""
Tests for evaluation metrics.
"""
from __future__ import annotations

from src.evaluation.metrics import (
    compute_weighted_score, score_to_grade, score_to_color,
    format_score_summary, score_to_dict, get_failing_dimensions,
)
from src.models.quality import QualityScore, QualityDimension


class TestComputeWeightedScore:
    def test_default_weights(self):
        scores = {
            "factual_accuracy": 8,
            "source_quality": 7,
            "logical_coherence": 9,
            "completeness": 6,
            "clarity": 8,
        }
        result = compute_weighted_score(scores)
        assert 6.0 <= result <= 10.0

    def test_custom_weights(self):
        scores = {"factual_accuracy": 10, "source_quality": 10}
        weights = {"factual_accuracy": 1.0, "source_quality": 0.0}
        result = compute_weighted_score(scores, weights)
        assert result == 10.0


class TestScoreToGrade:
    def test_a_grade(self):
        assert score_to_grade(9.5) == "A"

    def test_b_plus_grade(self):
        assert score_to_grade(7.5) == "B+"

    def test_f_grade(self):
        assert score_to_grade(3.0) == "F"


class TestScoreToColor:
    def test_green(self):
        assert score_to_color(9.0) == "#22c55e"

    def test_yellow(self):
        assert score_to_color(7.0) == "#eab308"

    def test_red(self):
        assert score_to_color(2.0) == "#ef4444"


class TestFormatScoreSummary:
    def test_format_full(self, passing_quality_score):
        summary = format_score_summary(passing_quality_score)
        assert "Quality Score: 8.0/10" in summary
        assert "Factual Accuracy" in summary

    def test_format_with_failures(self, failing_quality_score):
        summary = format_score_summary(failing_quality_score)
        assert "Hard Gate Failures" in summary


class TestScoreToDict:
    def test_conversion(self, passing_quality_score):
        d = score_to_dict(passing_quality_score)
        assert d["overall"] == 8.0
        assert d["grade"] == "A-"
        assert "dimensions" in d


class TestGetFailingDimensions:
    def test_no_failures(self, passing_quality_score):
        failing = get_failing_dimensions(passing_quality_score)
        assert failing == []

    def test_with_failures(self, failing_quality_score):
        failing = get_failing_dimensions(failing_quality_score)
        assert len(failing) >= 1