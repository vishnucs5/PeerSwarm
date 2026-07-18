"""
Research domain models: plans, findings, synthesis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class ResearchStatus(str, Enum):
    PLANNING = "planning"
    RESEARCHING = "researching"
    ANALYZING = "analyzing"
    EVALUATING = "evaluating"
    REVISING = "revising"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubQuestionPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchStrategy(str, Enum):
    ACADEMIC_DEEP = "academic_deep"  # Focus on papers, technical depth
    INDUSTRY_SURVEY = "industry_survey"  # Focus on reports, market data
    COMPARATIVE = "comparative"  # Compare approaches, methods
    HISTORICAL = "historical"  # Trace evolution over time
    GAP_ANALYSIS = "gap_analysis"  # Find what's missing


class SubQuestion(BaseModel):
    """A single sub-question in the research plan."""

    id: str = Field(default_factory=lambda: f"sq_{str(uuid4())[:8]}")
    question: str
    rationale: str
    priority: SubQuestionPriority = SubQuestionPriority.MEDIUM
    strategy: ResearchStrategy = ResearchStrategy.ACADEMIC_DEEP
    assigned_researcher: Literal["researcher_a", "researcher_b", "researcher_c"] = "researcher_a"
    expected_evidence: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    success_criteria: str = ""
    depends_on: list[str] = Field(default_factory=list)  # sub-question IDs


class ResearchPlan(BaseModel):
    """Complete research plan from PI agent."""

    id: str = Field(default_factory=lambda: f"plan_{str(uuid4())[:8]}")
    original_question: str
    sub_questions: list[SubQuestion] = Field(default_factory=list)
    overall_strategy: str = ""
    risk_assessment: dict[str, str] = Field(default_factory=dict)
    success_criteria: list[str] = Field(default_factory=list)
    estimated_iterations: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("sub_questions")
    @classmethod
    def validate_sub_questions(cls, v: list[SubQuestion]) -> list[SubQuestion]:
        if len(v) < 2:
            raise ValueError("Research plan must have at least 2 sub-questions")
        if len(v) > 6:
            raise ValueError("Research plan cannot exceed 6 sub-questions")
        return v


class EvidenceType(str, Enum):
    ACADEMIC_PAPER = "academic_paper"
    INDUSTRY_REPORT = "industry_report"
    BLOG_POST = "blog_post"
    NEWS_ARTICLE = "news_article"
    DOCUMENTATION = "documentation"
    CODE_REPOSITORY = "code_repository"
    DATASET = "dataset"
    PERSONAL_KNOWLEDGE = "personal_knowledge"
    EXPERT_OPINION = "expert_opinion"


class ResearchFinding(BaseModel):
    """A single research finding from a researcher agent."""

    id: str = Field(default_factory=lambda: f"find_{str(uuid4())[:8]}")
    sub_question_id: str
    researcher: Literal["researcher_a", "researcher_b", "researcher_c"]
    claim: str
    evidence: str
    evidence_type: EvidenceType
    source: str  # URL, DOI, title, etc.
    citation: str | None = None  # Formatted citation
    confidence: float = Field(default=0.8, ge=0, le=1)
    relevance: float = Field(default=0.8, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FindingCluster(BaseModel):
    """Cluster of related findings identified by Analyst."""

    id: str = Field(default_factory=lambda: f"cluster_{str(uuid4())[:8]}")
    theme: str
    findings: list[ResearchFinding] = Field(default_factory=list)
    summary: str = ""
    contradictions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)


class Synthesis(BaseModel):
    """Synthesized analysis from Analyst agent."""

    id: str = Field(default_factory=lambda: f"syn_{str(uuid4())[:8]}")
    question: str
    plan_id: str
    executive_summary: str = ""
    clusters: list[FindingCluster] = Field(default_factory=list)
    unified_narrative: str = ""
    key_insights: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
    all_findings: list[ResearchFinding] = Field(default_factory=list)
    citations: dict[str, str] = Field(default_factory=dict)  # key -> formatted citation
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1


class ReportSection(BaseModel):
    """Section in the final report."""

    id: str = Field(default_factory=lambda: f"sec_{str(uuid4())[:8]}")
    title: str
    content: str
    citations: list[str] = Field(default_factory=list)
    order: int = 0


class FinalReport(BaseModel):
    """Final research report from Writer agent."""

    id: str = Field(default_factory=lambda: f"rpt_{str(uuid4())[:8]}")
    synthesis_id: str
    title: str
    executive_summary: str
    sections: list[ReportSection] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    quality_score: float | None = None
    markdown: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1
