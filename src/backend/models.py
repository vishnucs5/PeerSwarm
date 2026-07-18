from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    researching = "researching"
    analyzing = "analyzing"
    evaluating = "evaluating"
    writing = "writing"
    completed = "completed"
    failed = "failed"


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class ResearchRequest(BaseModel):
    question: str
    max_iterations: int = Field(default=3, ge=1, le=5)
    quality_threshold: float = Field(default=8.0, ge=5.0, le=10.0)
    tags: list[str] = Field(default_factory=list)
    priority: Priority = Priority.normal


class QualityDimensions(BaseModel):
    accuracy: float = 0.0
    completeness: float = 0.0
    clarity: float = 0.0
    relevance: float = 0.0
    depth: float = 0.0


class QualityScore(BaseModel):
    overall: float = 0.0
    dimensions: QualityDimensions = Field(default_factory=QualityDimensions)


class ResearchSection(BaseModel):
    title: str
    content: str
    citations: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    question: str
    job_id: str
    executive_summary: str = ""
    key_takeaways: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    sections: list[ResearchSection] = Field(default_factory=list)
    report_markdown: str = ""
    report: dict[str, Any] = Field(default_factory=dict)
    quality_score: QualityScore | None = None
    duration_seconds: float = 0.0
    iterations: int = 0
    status: JobStatus = JobStatus.queued


class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    question: str
    status: JobStatus = JobStatus.queued
    iteration: int = 0
    max_iterations: int = 3
    quality_score: QualityScore | None = None
    error: str | None = None
    tags: list[str] = Field(default_factory=list)
    priority: Priority = Priority.normal
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    result: ResearchResult | None = None
    duration_seconds: float = 0.0


class HealthResponse(BaseModel):
    status: str = "ok"
    uptime_seconds: float = 0.0
    version: str = "0.1.0"
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
