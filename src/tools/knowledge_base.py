"""
Knowledge base tools for RAG operations (search, store, entity management).
"""

from __future__ import annotations

from typing import Any

from src.memory import get_knowledge_graph, get_run_history, get_vector_store
from src.models.memory import Entity, MemoryEntry, MemoryType, Relation, SearchQuery, SearchResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeBaseTool:
    """Tool for interacting with the knowledge base (ChromaDB + Neo4j)."""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.knowledge_graph = get_knowledge_graph()
        self.history = get_run_history()

    def search(
        self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        """Search the knowledge base for relevant entries."""
        search_query = SearchQuery(query=query, top_k=top_k, filters=filters or {})
        response = self.vector_store.search(search_query)
        return response.results

    def store(
        self,
        content: str,
        metadata: dict[str, Any],
        memory_type: MemoryType = MemoryType.RESEARCH_FINDING,
        run_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str | None:
        """Store content in the knowledge base."""
        entry = MemoryEntry(
            content=content,
            type=memory_type,
            metadata=metadata,
            source_run_id=run_id,
            tags=tags or [],
        )

        success = self.vector_store.add_entry(entry)
        if success:
            logger.info(f"Stored {memory_type.value} entry in vector store: {entry.id}")
            return entry.id
        return None

    def store_findings(self, findings: list[dict[str, Any]], run_id: str) -> list[str]:
        """Store multiple research findings."""
        entry_ids = []
        for i, finding in enumerate(findings):
            entry = MemoryEntry(
                content=finding.get("content", ""),
                type=MemoryType.RESEARCH_FINDING,
                metadata={
                    "sub_question_id": finding.get("sub_question_id", ""),
                    "researcher": finding.get("researcher", ""),
                    "source": finding.get("source", ""),
                    "confidence": finding.get("confidence", 0.0),
                },
                source_run_id=run_id,
                tags=finding.get("tags", []),
            )
            if self.vector_store.add_entry(entry):
                entry_ids.append(entry.id)
        return entry_ids

    def search_by_run(self, run_id: str, query: str, top_k: int = 10) -> list[SearchResult]:
        """Search within a specific run's entries."""
        search_query = SearchQuery(
            query=query,
            top_k=top_k,
            filters={"source_run_id": run_id},
        )
        response = self.vector_store.search(search_query)
        return response.results

    def get_entities(
        self, query: str, entity_types: list[str] | None = None, limit: int = 10
    ) -> list[Entity]:
        """Search entities in knowledge graph."""
        return self.knowledge_graph.search_entities(query, entity_types, limit)

    def store_entities(self, entities: list[dict[str, Any]]) -> int:
        """Store entities in knowledge graph."""
        kg_entities = []
        for e in entities:
            kg_entities.append(
                Entity(
                    name=e["name"],
                    type=e.get("type", "concept"),
                    description=e.get("description", ""),
                    source_run_id=e.get("source_run_id", ""),
                    confidence=e.get("confidence", 1.0),
                )
            )
        return self.knowledge_graph.upsert_entities(kg_entities)

    def get_entity_relations(self, entity_id: str) -> list[Relation]:
        """Get relations for an entity."""
        return self.knowledge_graph.get_relations(entity_id)

    def get_history(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search past research runs."""
        runs = self.history.list_runs(limit=limit, order_by="created_at", order_desc=True)
        results = []
        for run in runs:
            if query.lower() in run.question.lower():
                results.append(
                    {
                        "id": run.id,
                        "question": run.question,
                        "status": run.status,
                        "created_at": run.created_at.isoformat() if run.created_at else None,
                        "quality_score": run.quality_score,
                        "iterations": run.iterations,
                    }
                )
        return results

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get details of a specific run."""
        run = self.history.get_run(run_id)
        if run:
            return {
                "id": run.id,
                "question": run.question,
                "status": run.status,
                "plan": run.plan,
                "quality_score": run.quality_score,
                "final_report_id": run.final_report_id,
                "token_usage": run.token_usage,
                "duration_seconds": run.duration_seconds,
                "iterations": run.iterations,
                "error": run.error,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
        return None

    def delete_run_data(self, run_id: str) -> dict[str, Any]:
        """Delete all data for a run."""
        vector_entries = self.vector_store.delete_run_entries(run_id)
        kg_deleted = self.knowledge_graph.delete_run_data(run_id)
        history_deleted = self.history.delete_run(run_id)
        return {
            "vector_entries_removed": vector_entries,
            "kg_data_removed": kg_deleted,
            "history_removed": history_deleted,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        try:
            vector_count = self.vector_store.collection.count()
        except Exception:
            vector_count = 0

        try:
            kg_stats = self.knowledge_graph.get_stats()
        except Exception:
            kg_stats = {"entities": 0, "relations": 0}

        try:
            history_stats = self.history.get_stats()
        except Exception:
            history_stats = {}

        return {
            "vector_store_entries": vector_count,
            "knowledge_graph": kg_stats,
            "history": history_stats,
        }


_kb_tool: KnowledgeBaseTool | None = None


def get_kb_tool() -> KnowledgeBaseTool:
    global _kb_tool
    if _kb_tool is None:
        _kb_tool = KnowledgeBaseTool()
    return _kb_tool
