"""
Integration tests requiring Docker services: ChromaDB, Neo4j, Redis.
Skip if services are not available.
"""

from __future__ import annotations

import socket

import pytest

from src.models.memory import (
    Entity,
    EntityType,
    MemoryEntry,
    MemoryType,
    Relation,
    RelationType,
    RunRecord,
    SearchQuery,
)

SERVICE_PORTS = {
    "chromadb": 8001,
    "neo4j_bolt": 7687,
    "redis": 6379,
}


def _check_port(host: str = "localhost", port: int = 8001, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _services_available(required: list[str] | None = None) -> bool:
    """Check if required Docker services are running."""
    checks = required or list(SERVICE_PORTS.keys())
    for service in checks:
        port = SERVICE_PORTS.get(service)
        if port and not _check_port(port=port):
            return False
    return True


docker_required = pytest.mark.skipif(
    not _services_available(),
    reason="Docker services not available (chromadb:8001, neo4j:7687, redis:6379)",
)


# ── ChromaDB Integration Tests ──────────────────────────────────────


@pytest.mark.slow
@docker_required
class TestChromaDBIntegration:
    def test_connect_and_store(self):
        from src.memory.vector_store import VectorStore

        store = VectorStore()
        entry = MemoryEntry(
            type=MemoryType.RESEARCH_FINDING,
            content="RAG combines retrieval and generation for LLMs.",
            metadata={"source": "test"},
            source_run_id="test_run_123",
        )
        ok = store.add_entry(entry)
        assert ok is True

        query = SearchQuery(query="retrieval augmented generation", top_k=5)
        results = store.search(query)
        assert len(results.results) > 0
        assert any("RAG" in r.entry.content for r in results.results)

        # Cleanup
        store.delete_entry(entry.id)

    def test_delete_document(self):
        from src.memory.vector_store import VectorStore

        store = VectorStore()
        entry = MemoryEntry(
            type=MemoryType.RESEARCH_FINDING,
            content="Delete me",
            metadata={},
            source_run_id="test_run_123",
        )
        ok = store.add_entry(entry)
        assert ok is True
        assert store.delete_entry(entry.id) is True

    def test_get_stats(self):
        from src.memory.vector_store import VectorStore

        store = VectorStore()
        stats = store.get_run_stats("test_run_123")
        assert isinstance(stats, dict)


# ── Neo4j Integration Tests ────────────────────────────────────────


@pytest.mark.slow
@docker_required
class TestNeo4jIntegration:
    def test_add_and_query_entity(self):
        from src.memory.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        entity = Entity(
            id="ent_rag_test",
            name="Retrieval Augmented Generation (RAG)",
            type=EntityType.CONCEPT,
            description="A method to enhance LLMs with external knowledge",
            source_run_ids=["test_run_123"],
            confidence=0.95,
        )
        ok = kg.upsert_entity(entity)
        assert ok is True

        results = kg.search_entities("RAG", limit=5)
        assert len(results) > 0
        assert any("Retrieval Augmented Generation" in e.name for e in results)

        # Cleanup
        kg.delete_run_data("test_run_123")

    def test_add_relation(self):
        from src.memory.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        src = Entity(
            id="rag_ent", name="RAG", type=EntityType.CONCEPT, source_run_ids=["test_run_123"]
        )
        tgt = Entity(
            id="llm_ent", name="LLM", type=EntityType.CONCEPT, source_run_ids=["test_run_123"]
        )
        kg.upsert_entity(src)
        kg.upsert_entity(tgt)

        relation = Relation(
            subject_id="rag_ent",
            object_id="llm_ent",
            type=RelationType.RELATED_TO,
            source_run_ids=["test_run_123"],
            weight=0.9,
        )
        ok = kg.upsert_relation(relation)
        assert ok is True

        # Cleanup
        kg.delete_run_data("test_run_123")

    def test_get_stats(self):
        from src.memory.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        stats = kg.get_stats()
        assert isinstance(stats, dict)


# ── Redis Integration Tests ─────────────────────────────────────────


@pytest.mark.slow
@docker_required
class TestRedisIntegration:
    def test_set_and_get(self):
        import redis

        r = redis.Redis(host="localhost", port=6379, db=0)
        r.set("test_key", "test_value")
        assert r.get("test_key") == b"test_value"
        r.delete("test_key")

    def test_queue_push_pop(self):
        import redis

        r = redis.Redis(host="localhost", port=6379, db=0)
        r.lpush("test_queue", "item1")
        r.lpush("test_queue", "item2")
        assert r.rpop("test_queue") == b"item1"
        assert r.rpop("test_queue") == b"item2"


# ── Full Pipeline Integration ───────────────────────────────────────


@pytest.mark.slow
@docker_required
class TestFullPipelineIntegration:
    """End-to-end flow with real storage backends."""

    def test_vector_to_sqlite_flow(self):
        """Store findings in vector store, then list from history."""
        import uuid

        from src.memory.history import RunHistory
        from src.memory.vector_store import VectorStore

        run_id = f"test_integration_run_{uuid.uuid4().hex[:8]}"

        vs = VectorStore()
        entry = MemoryEntry(
            type=MemoryType.RESEARCH_FINDING,
            content="Test finding about RAG",
            source_run_id=run_id,
            metadata={},
        )
        ok = vs.add_entry(entry)
        assert ok is True

        history = RunHistory()
        record = RunRecord(
            id=run_id,
            question="Integration test",
            status="completed",
        )
        ok = history.create_run(record)
        assert ok is True

        run = history.get_run(run_id)
        assert run is not None
        assert run.status == "completed"

        # Cleanup
        vs.delete_entry(entry.id)
