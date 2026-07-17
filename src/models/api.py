"""
API request/response models.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ResearchRequest(BaseModel):
    """Request to start a research job."""
    question: str = Field(min_length=10, max_length=2000)
    context: str | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=5)
    quality_threshold: float | None = Field(default=None, ge=0, le=10)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=10)
    priority: Literal["low", "normal", "high"] = "normal"

    @field_validator("tags")
    @classmethod
    def validate_tag_length(cls, v: list[str]) -> list[str]:
        for tag in v:
            if len(tag) > 50:
                raise ValueError("Tag exceeds maximum length of 50")
        return v


class ResearchResponse(BaseModel):
    """Response when starting a research job."""
    job_id: str
    status: Literal["queued", "running"]
    message: str
    estimated_duration_seconds: int | None = None


class JobStatus(BaseModel):
    """Current status of a research job."""
    job_id: str
    question: str
    status: Literal[
        "queued", "planning", "researching", "analyzing",
        "evaluating", "revising", "writing", "completed", "failed", "cancelled"
    ]
    current_step: str = ""
    progress: float = Field(default=0.0, ge=0, le=1)
    iteration: int = 0
    max_iterations: int = 3
    quality_score: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    cost_estimate: float = 0.0
    tags: list[str] = Field(default_factory=list)


class JobResult(BaseModel):
    """Final result of a completed research job."""
    job_id: str
    question: str
    report: dict[str, Any] | None = None
    report_markdown: str | None = None
    quality_score: dict[str, Any] | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    duration_seconds: float
    iterations: int
    created_at: datetime
    completed_at: datetime
    key_takeaways: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    executive_summary: str = ""


class JobListResponse(BaseModel):
    """Response for listing jobs."""
    jobs: list[JobStatus]
    total: int
    page: int = 1
    page_size: int = 20


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    services: dict[str, Literal["healthy", "unhealthy"]] = Field(default_factory=dict)
    uptime_seconds: float = 0


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str | None = None
    code: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StreamEvent(BaseModel):
    """Server-sent event for streaming updates."""
    event: str
    data: dict[str, Any]
    job_id: str | None = None
