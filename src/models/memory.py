"""
Pydantic models for memory and knowledge storage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token usage tracking for a research run."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    provider: str = "openai"
    model: str = "gpt-4o"
    cost_estimate: float = 0.0


class MemoryType(str, Enum):
    """Type of memory entry."""

    RESEARCH_FINDING = "research_finding"
    SYNTHESIS = "synthesis"
    REPORT = "report"
    ENTITY = "entity"
    RELATION = "relation"
    USER_QUESTION = "user_question"
    FEEDBACK = "feedback"


class EntityType(str, Enum):
    """Entity types in knowledge graph."""

    CONCEPT = "concept"
    PERSON = "person"
    ORGANIZATION = "organization"
    PAPER = "paper"
    METHOD = "method"
    DATASET = "dataset"
    METRIC = "metric"
    DOMAIN = "domain"
    TECHNOLOGY = "technology"


class RelationType(str, Enum):
    """Relation types in knowledge graph."""

    RELATED_TO = "related_to"
    CITES = "cites"
    USES = "uses"
    COMPARES = "compares"
    EXTENDS = "extends"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    PART_OF = "part_of"
    INSTANCE_OF = "instance_of"
    SUBCLASS_OF = "subclass_of"


class MemoryEntry(BaseModel):
    """Unified memory entry for vector and graph storage."""

    id: str = Field(default_factory=lambda: str(uuid4())[:12])
    type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    source_run_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1

    # For entities
    entity_type: EntityType | None = None
    entity_name: str | None = None
    entity_aliases: list[str] = Field(default_factory=list)

    # For relations
    subject_id: str | None = None
    object_id: str | None = None
    relation_type: RelationType | None = None
    relation_weight: float = Field(default=1.0, ge=0, le=1)


class SearchQuery(BaseModel):
    """Query for memory search."""

    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    memory_types: list[MemoryType] | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    min_score: float = Field(default=0.3, ge=0, le=1)
    include_embeddings: bool = False


class SearchResult(BaseModel):
    """Result from memory search."""

    entry: MemoryEntry
    score: float = Field(ge=0, le=1)
    matched_text: str | None = None


class SearchResponse(BaseModel):
    """Response from memory search."""

    results: list[SearchResult] = Field(default_factory=list)
    total: int = 0
    query: SearchQuery
    took_ms: float = 0


class Entity(BaseModel):
    """Knowledge graph entity."""

    id: str = Field(default_factory=lambda: str(uuid4())[:12])
    name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    source_run_ids: list[str] = Field(default_factory=list)
    mention_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Relation(BaseModel):
    """Knowledge graph relation."""

    id: str = Field(default_factory=lambda: str(uuid4())[:12])
    subject_id: str
    object_id: str
    type: RelationType
    weight: float = Field(default=1.0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)  # finding IDs
    source_run_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GraphQuery(BaseModel):
    """Query for knowledge graph traversal."""

    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: EntityType | None = None
    relation_types: list[RelationType] | None = None
    max_depth: int = Field(default=2, ge=1, le=4)
    limit: int = Field(default=50, ge=1, le=200)


class GraphPath(BaseModel):
    """Path in knowledge graph."""

    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0, le=1)


class RunRecord(BaseModel):
    """Record of a research run for history."""

    id: str = Field(default_factory=lambda: str(uuid4())[:12])
    question: str
    status: str
    plan: dict[str, Any] | None = None
    quality_score: dict[str, Any] | None = None
    final_report_id: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    duration_seconds: float = 0
    iterations: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    # For search/filtering
    tags: list[str] = Field(default_factory=list)
    domain: str | None = None
