"""
Tests for quality models.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.quality import (
    QualityScore, QualityGateResult, QualityDimension,
    RevisionDirective, HardGateFailure,
)


class TestQualityScore:
    def test_create_valid(self):
        score = QualityScore(
            factual_accuracy=8, source_quality=7,
            logical_coherence=9, completeness=6, clarity=8,
            overall=7.6, iteration=1,
        )
        assert score.factual_accuracy == 8

    def test_overall_computed(self):
        score = QualityScore(
            factual_accuracy=8, source_quality=8,
            logical_coherence=8, completeness=8, clarity=8,
            iteration=1,
        )
        assert score.overall == 8.0

    def test_hard_gate_failure_manual(self):
        failure = HardGateFailure(
            dimension=QualityDimension.FACTUAL_ACCURACY,
            score=5, threshold=6,
            reason="Below threshold",
        )
        assert failure.dimension == QualityDimension.FACTUAL_ACCURACY
        assert failure.score == 5

    def test_out_of_range_score(self):
        with pytest.raises(ValidationError):
            QualityScore(
                factual_accuracy=11, source_quality=7,
                logical_coherence=8, completeness=7, clarity=8,
                overall=7.0, iteration=1,
            )

    def test_negative_score(self):
        with pytest.raises(ValidationError):
            QualityScore(
                factual_accuracy=-1, source_quality=7,
                logical_coherence=8, completeness=7, clarity=8,
                overall=7.0, iteration=1,
            )

    def test_revision_priority_research(self):
        score = QualityScore(
            factual_accuracy=4, source_quality=8,
            logical_coherence=8, completeness=8, clarity=8,
            iteration=1,
        )
        assert score.revision_priority in ("research", "analysis", "writing", "none")


class TestQualityGateResult:
    def test_create_passing(self, passing_quality_score):
        result = QualityGateResult(
            passed=True,
            score=passing_quality_score,
            action="write",
            reason="All good",
            iteration=1,
        )
        assert result.passed is True
        assert result.action == "write"

    def test_create_failing(self, failing_quality_score):
        result = QualityGateResult(
            passed=False,
            score=failing_quality_score,
            action="revise_analysis",
            reason="Low score",
            iteration=1,
        )
        assert result.passed is False


class TestQualityDimension:
    def test_values(self):
        assert QualityDimension.FACTUAL_ACCURACY.value == "factual_accuracy"
        assert QualityDimension.SOURCE_QUALITY.value == "source_quality"
        assert QualityDimension.LOGICAL_COHERENCE.value == "logical_coherence"
        assert QualityDimension.COMPLETENESS.value == "completeness"
        assert QualityDimension.CLARITY.value == "clarity"


class TestRevisionDirective:
    def test_create(self):
        directive = RevisionDirective(
            target_agent="analyst",
            specific_issues=["Factual accuracy below threshold (5/10)"],
            required_evidence=["Recent peer-reviewed papers"],
            suggested_approach="Verify claims with more recent sources",
        )
        assert directive.target_agent == "analyst"
        assert len(directive.specific_issues) == 1


class TestHardGateFailure:
    def test_create(self):
        failure = HardGateFailure(
            dimension=QualityDimension.FACTUAL_ACCURACY,
            score=4, threshold=6,
            reason="Too low",
        )
        assert failure.score == 4
        assert failure.threshold == 6