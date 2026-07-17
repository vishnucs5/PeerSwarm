"""
Tests for memory models and API models.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.models.memory import (
    MemoryEntry, Entity, Relation, SearchResult,
    MemoryType, EntityType, RelationType,
)
from src.models.api import (
    ResearchRequest, ResearchResponse, JobStatus, JobResult,
    JobListResponse, HealthResponse, ErrorResponse, StreamEvent,
)


class TestMemoryModels:
    def test_memory_entry(self):
        entry = MemoryEntry(
            type=MemoryType.RESEARCH_FINDING,
            content="RAG combines retrieval and generation",
        )
        assert entry.type == MemoryType.RESEARCH_FINDING
        assert entry.content.startswith("RAG")
        assert entry.id is not None

    def test_entity(self):
        e = Entity(name="RAG", type=EntityType.CONCEPT)
        assert e.name == "RAG"
        assert e.type == EntityType.CONCEPT
        assert e.id is not None

    def test_relation(self):
        r = Relation(
            subject_id="entity_001",
            object_id="entity_002",
            type=RelationType.RELATED_TO,
        )
        assert r.subject_id == "entity_001"
        assert r.object_id == "entity_002"
        assert r.type == RelationType.RELATED_TO

    def test_search_result(self):
        entry = MemoryEntry(type=MemoryType.RESEARCH_FINDING, content="test")
        r = SearchResult(entry=entry, score=0.95)
        assert r.score == 0.95
        assert r.entry.content == "test"


class TestAPIModels:
    def test_research_request_valid(self):
        req = ResearchRequest(question="What is RAG? Explain the concept in detail.")
        assert req.question == "What is RAG? Explain the concept in detail."
        assert req.tags == []
        assert req.priority == "normal"

    def test_research_request_too_short(self):
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ResearchRequest(question="Short")

    def test_research_response(self):
        resp = ResearchResponse(job_id="job_001", status="queued", message="OK")
        assert resp.job_id == "job_001"

    def test_job_status(self):
        now = datetime.now(timezone.utc)
        js = JobStatus(
            job_id="job_001", question="Test?", status="queued",
            started_at=now, updated_at=now,
        )
        assert js.status == "queued"
        assert js.progress == 0.0

    def test_job_result(self):
        now = datetime.now(timezone.utc)
        jr = JobResult(
            job_id="job_001", question="Test?",
            duration_seconds=10.5, iterations=2,
            created_at=now, completed_at=now,
        )
        assert jr.duration_seconds == 10.5

    def test_job_list_response(self):
        now = datetime.now(timezone.utc)
        job = JobStatus(
            job_id="job_001", question="Test?", status="completed",
            started_at=now, updated_at=now,
        )
        resp = JobListResponse(jobs=[job], total=1)
        assert resp.total == 1
        assert len(resp.jobs) == 1

    def test_health_response(self):
        resp = HealthResponse(status="healthy")
        assert resp.status == "healthy"
        assert resp.version == "0.1.0"

    def test_error_response(self):
        resp = ErrorResponse(error="Not found")
        assert resp.error == "Not found"

    def test_stream_event(self):
        ev = StreamEvent(event="update", data={"key": "value"})
        assert ev.event == "update"
        assert ev.data["key"] == "value"