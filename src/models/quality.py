"""
Quality evaluation models for the Critic agent and quality gates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class QualityDimension(str, Enum):
    """Quality evaluation dimensions."""

    FACTUAL_ACCURACY = "factual_accuracy"
    SOURCE_QUALITY = "source_quality"
    LOGICAL_COHERENCE = "logical_coherence"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"


class HardGateFailure(BaseModel):
    """A hard gate failure in quality evaluation."""

    dimension: QualityDimension
    score: int = Field(ge=0, le=10)
    threshold: int = Field(ge=0, le=10)
    reason: str
    affected_sections: list[str] = Field(default_factory=list)


class QualityScore(BaseModel):
    """Quality evaluation score from Critic agent."""

    id: str = Field(default_factory=lambda: f"qs_{str(uuid4())[:8]}")

    # Dimension scores (0-10)
    factual_accuracy: int = Field(ge=0, le=10)
    source_quality: int = Field(ge=0, le=10)
    logical_coherence: int = Field(ge=0, le=10)
    completeness: int = Field(ge=0, le=10)
    clarity: int = Field(ge=0, le=10)

    # Computed (auto-calculated from dimensions if not provided)
    overall: float = Field(default=0.0, ge=0, le=10)

    # Hard gates
    hard_gate_failures: list[HardGateFailure] = Field(default_factory=list)
    hard_gate_threshold: int = Field(default=6, ge=0, le=10)

    # Qualitative feedback
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)

    # Routing
    revision_priority: Literal["research", "analysis", "writing", "none"] = "none"

    # Meta
    confidence: float = Field(default=0.8, ge=0, le=1)
    iteration: int = Field(default=0, ge=0)
    improved_from_previous: bool = False
    previous_overall: float | None = None

    # Traceability
    synthesis_id: str = ""
    evaluator: str = "critic"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def dimension_scores(self) -> dict[str, int]:
        """Get dict of dimension scores."""
        return {
            "factual_accuracy": self.factual_accuracy,
            "source_quality": self.source_quality,
            "logical_coherence": self.logical_coherence,
            "completeness": self.completeness,
            "clarity": self.clarity,
        }

    @model_validator(mode="after")
    def compute_overall(self) -> QualityScore:
        if self.overall == 0.0:
            dims = [
                self.factual_accuracy,
                self.source_quality,
                self.logical_coherence,
                self.completeness,
                self.clarity,
            ]
            self.overall = round(sum(dims) / len(dims), 1)
        return self

    @field_validator("hard_gate_failures", mode="after")
    @classmethod
    def detect_hard_gates(cls, v: list[HardGateFailure], info: Any) -> list[HardGateFailure]:
        data = info.data
        threshold = data.get("hard_gate_threshold", 6)
        failures = []

        for dim_name, score in [
            ("factual_accuracy", data.get("factual_accuracy", 0)),
            ("source_quality", data.get("source_quality", 0)),
            ("logical_coherence", data.get("logical_coherence", 0)),
            ("completeness", data.get("completeness", 0)),
            ("clarity", data.get("clarity", 0)),
        ]:
            if score < threshold:
                failures.append(
                    HardGateFailure(
                        dimension=QualityDimension(dim_name),
                        score=score,
                        threshold=threshold,
                        reason=f"{dim_name.replace('_', ' ').title()} score {score} below hard gate threshold {threshold}",
                    )
                )
        return failures

    @field_validator("revision_priority", mode="after")
    @classmethod
    def determine_priority(cls, v: str, info: Any) -> str:
        data = info.data
        failures = data.get("hard_gate_failures", [])

        if failures:
            # Map failed dimension to agent
            dim_to_agent = {
                QualityDimension.FACTUAL_ACCURACY: "research",
                QualityDimension.SOURCE_QUALITY: "research",
                QualityDimension.LOGICAL_COHERENCE: "analysis",
                QualityDimension.COMPLETENESS: "analysis",
                QualityDimension.CLARITY: "writing",
            }
            for failure in failures:
                return dim_to_agent.get(failure.dimension, "analysis")

        return v


class RevisionDirective(BaseModel):
    """Directive for targeted revision."""

    id: str = Field(default_factory=lambda: f"rev_{str(uuid4())[:8]}")
    target_agent: Literal["researcher_a", "researcher_b", "researcher_c", "analyst", "writer"]
    specific_issues: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    suggested_approach: str = ""
    max_tokens: int = Field(default=4000, ge=500, le=8000)
    quality_score_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QualityGateResult(BaseModel):
    """Result of quality gate evaluation."""

    passed: bool
    score: QualityScore
    directive: RevisionDirective | None = None
    action: Literal["write", "revise_research", "revise_analysis", "revise_write", "max_iterations"]
    reason: str = ""
    failing_dimensions: list[QualityDimension] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 3
