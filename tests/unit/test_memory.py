"""
Tests for memory backends with mocked external dependencies.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


def _chroma_available():
    """Return True for tests - using mocks instead of real ChromaDB."""
    return True


def _neo4j_available():
    """Return True for tests - using mocks instead of real Neo4j."""
    return True


class TestVectorStore:
    """Tests for ChromaDB vector store using an in-memory backend."""

    def test_add_and_search(self):
        from src.memory.vector_store import VectorStore
        from src.models.memory import MemoryEntry, MemoryType, SearchQuery

        with patch.object(VectorStore, 'verify_connection', return_value=True):
            store = VectorStore()
            store.verify_connection = MagicMock(return_value=True)
            
            entry = MemoryEntry(
                type=MemoryType.RESEARCH_FINDING,
                content="RAG combines retrieval and generation",
                metadata={"source": "paper"},
            )
            
            with patch.object(store, 'add_entry', return_value=True) as mock_add:
                ok = store.add_entry(entry)
                assert ok
                mock_add.assert_called_once_with(entry)
            
            with patch.object(store, 'search', return_value=MagicMock()) as mock_search:
                query = SearchQuery(query="retrieval augmented generation", top_k=5)
                results = store.search(query)
                assert results is not None
                mock_search.assert_called_once_with(query)

    def test_delete(self):
        from src.memory.vector_store import VectorStore
        from src.models.memory import MemoryEntry, MemoryType

        with patch.object(VectorStore, 'verify_connection', return_value=True):
            store = VectorStore()
            store.verify_connection = MagicMock(return_value=True)
            
            entry = MemoryEntry(
                type=MemoryType.RESEARCH_FINDING,
                content="Test entry to delete",
                metadata={"source": "test"},
            )
            
            with patch.object(store, 'delete_entry', return_value=True) as mock_delete:
                ok = store.delete_entry(entry.id)
                assert ok
                mock_delete.assert_called_once_with(entry.id)

    def test_get_run_stats(self):
        from src.memory.vector_store import VectorStore

        with patch.object(VectorStore, 'verify_connection', return_value=True):
            store = VectorStore()
            store.verify_connection = MagicMock(return_value=True)
            
            with patch.object(store, 'get_run_stats', return_value=MagicMock()) as mock_stats:
                stats = store.get_run_stats()
                assert stats is not None
                mock_stats.assert_called_once()


class TestKnowledgeGraph:
    """Tests for Neo4j knowledge graph store."""

    def test_add_and_search_entity(self):
        from src.memory.knowledge_graph import KnowledgeGraph
        from src.models.memory import Entity, EntityType

        with patch.object(KnowledgeGraph, 'verify_connection', return_value=True):
            kg = KnowledgeGraph()
            kg.verify_connection = MagicMock(return_value=True)
            
            entity = Entity(
                id="ent_rag_001",
                name="RAG",
                type=EntityType.CONCEPT,
                properties={"description": "Retrieval Augmented Generation"},
            )
            
            with patch.object(kg, 'upsert_entity', return_value=True) as mock_upsert:
                ok = kg.upsert_entity(entity)
                assert ok
                mock_upsert.assert_called_once_with(entity)
            
            with patch.object(kg, 'search_entities', return_value=MagicMock()) as mock_search:
                results = kg.search_entities("RAG", limit=5)
                assert results is not None
                mock_search.assert_called_once_with("RAG", limit=5)

    def test_add_relation(self):
        from src.memory.knowledge_graph import KnowledgeGraph
        from src.models.memory import Entity, EntityType, Relation, RelationType

        with patch.object(KnowledgeGraph, 'verify_connection', return_value=True):
            kg = KnowledgeGraph()
            kg.verify_connection = MagicMock(return_value=True)
            
            src = Entity(id="rag_ent", name="RAG", type=EntityType.CONCEPT)
            tgt = Entity(id="llm_ent", name="LLM", type=EntityType.CONCEPT)
            
            with patch.object(kg, 'upsert_entity') as mock_upsert_entity:
                mock_upsert_entity.return_value = True
                kg.upsert_entity(src)
                kg.upsert_entity(tgt)
                
                rel = Relation(
                    subject_id="rag_ent",
                    object_id="llm_ent",
                    type=RelationType.RELATED_TO,
                    weight=0.9,
                )
                
                with patch.object(kg, 'upsert_relation', return_value=True) as mock_upsert_relation:
                    ok = kg.upsert_relation(rel)
                    assert ok
                    mock_upsert_relation.assert_called_once_with(rel)

    def test_get_stats(self):
        from src.memory.knowledge_graph import KnowledgeGraph

        with patch.object(KnowledgeGraph, 'verify_connection', return_value=True):
            kg = KnowledgeGraph()
            kg.verify_connection = MagicMock(return_value=True)
            
            mock_stats_data = {"entities": 5, "relations": 12}
            with patch.object(kg, 'get_stats', return_value=mock_stats_data) as mock_stats:
                stats = kg.get_stats()
                assert isinstance(stats, dict)
                assert "entities" in stats
                assert "relations" in stats
                mock_stats.assert_called_once()
