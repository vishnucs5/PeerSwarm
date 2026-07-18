"""
ChromaDB vector store for research findings.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Any

import chromadb
from chromadb import ClientAPI, Collection
from chromadb.config import Settings as ChromaSettings

from src.config import get_settings
from src.models.memory import (
    MemoryEntry,
    MemoryType,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Input validation constants
MAX_QUERY_LENGTH = 2000
MAX_FILTERS = 10
MAX_FILTER_KEY_LENGTH = 100
MAX_FILTER_VALUE_LENGTH = 500
DANGEROUS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>.*?</iframe>",
    r"data:text/html",
    r"vbscript:",
]


def sanitize_string(value: str, max_length: int | None = None) -> str:
    """Sanitize string input by removing dangerous patterns and limiting length."""
    if not isinstance(value, str):
        return str(value)

    if max_length and len(value) > max_length:
        value = value[:max_length]

    sanitized = value
    for pattern in DANGEROUS_PATTERNS:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    sanitized = html.escape(sanitized)
    return sanitized


def validate_search_query(query: SearchQuery) -> SearchQuery:
    """Validate and sanitize search query."""
    if not query.query or not query.query.strip():
        raise ValueError("Search query cannot be empty")

    if len(query.query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH}")

    sanitized_query = sanitize_string(query.query, MAX_QUERY_LENGTH)

    sanitized_filters = {}
    if query.filters:
        if len(query.filters) > MAX_FILTERS:
            raise ValueError(f"Maximum {MAX_FILTERS} filters allowed")
        for key, value in query.filters.items():
            if len(key) > MAX_FILTER_KEY_LENGTH:
                raise ValueError(f"Filter key exceeds maximum length of {MAX_FILTER_KEY_LENGTH}")
            if isinstance(value, str) and len(value) > MAX_FILTER_VALUE_LENGTH:
                raise ValueError(
                    f"Filter value exceeds maximum length of {MAX_FILTER_VALUE_LENGTH}"
                )
            sanitized_key = sanitize_string(key, MAX_FILTER_KEY_LENGTH)
            sanitized_value = (
                sanitize_string(value, MAX_FILTER_VALUE_LENGTH) if isinstance(value, str) else value
            )
            sanitized_filters[sanitized_key] = sanitized_value

    return SearchQuery(
        query=sanitized_query,
        top_k=query.top_k,
        memory_types=query.memory_types,
        filters=sanitized_filters,
        min_score=query.min_score,
        include_embeddings=query.include_embeddings,
    )


class VectorStore:
    """ChromaDB vector store for research memory."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ):
        settings = get_settings()

        self.host = host or settings.storage.chroma_host
        self.port = port or settings.storage.chroma_port
        self.persist_dir = persist_dir or str(settings.storage.chroma_persist_dir)
        self.collection_name = collection_name or settings.storage.chroma_collection_name

        self._client: ClientAPI | None = None
        self._collection: Collection | None = None

    @property
    def client(self) -> ClientAPI:
        """Get or create ChromaDB client."""
        if self._client is None:
            self._client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self) -> Collection:
        """Get or create collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def verify_connection(self) -> bool:
        """Verify database connection."""
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False

    def close(self):
        """Close connection."""
        self._client = None
        self._collection = None

    # Memory operations
    def add_entry(self, entry: MemoryEntry) -> bool:
        """Add a memory entry."""
        try:
            self.collection.add(
                ids=[entry.id],
                documents=[entry.content],
                metadatas=[
                    {
                        "type": entry.type.value,
                        "source_run_id": entry.source_run_id or "",
                        "tags": ",".join(entry.tags),
                        "entity_type": entry.entity_type.value if entry.entity_type else "",
                        "entity_name": entry.entity_name or "",
                        "subject_id": entry.subject_id or "",
                        "object_id": entry.object_id or "",
                        "relation_type": entry.relation_type.value if entry.relation_type else "",
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat(),
                        "version": entry.version,
                    }
                ],
                embeddings=[entry.embedding] if entry.embedding else None,
            )
            return True
        except Exception as e:
            logger.error(f"Error adding entry {entry.id}: {e}")
            return False

    def add_entries(self, entries: list[MemoryEntry]) -> int:
        """Batch add memory entries."""
        if not entries:
            return 0

        try:
            self.collection.add(
                ids=[e.id for e in entries],
                documents=[e.content for e in entries],
                metadatas=[
                    {
                        "type": e.type.value,
                        "source_run_id": e.source_run_id or "",
                        "tags": ",".join(e.tags),
                        "entity_type": e.entity_type.value if e.entity_type else "",
                        "entity_name": e.entity_name or "",
                        "subject_id": e.subject_id or "",
                        "object_id": e.object_id or "",
                        "relation_type": e.relation_type.value if e.relation_type else "",
                        "created_at": e.created_at.isoformat(),
                        "updated_at": e.updated_at.isoformat(),
                        "version": e.version,
                    }
                    for e in entries
                ],
            )
            # If entries have mixed embeddings, re-add with embeddings preserved
            if not all(e.embedding for e in entries) and any(e.embedding for e in entries):
                self.collection.delete(ids=[e.id for e in entries if e.embedding])
                for e in [e for e in entries if e.embedding]:
                    self.collection.add(
                        ids=[e.id],
                        documents=[e.content],
                        metadatas=[
                            {
                                k: v
                                for k, v in {
                                    "type": e.type.value,
                                    "source_run_id": e.source_run_id or "",
                                    "tags": ",".join(e.tags),
                                    "entity_type": e.entity_type.value if e.entity_type else "",
                                    "entity_name": e.entity_name or "",
                                    "subject_id": e.subject_id or "",
                                    "object_id": e.object_id or "",
                                    "relation_type": e.relation_type.value
                                    if e.relation_type
                                    else "",
                                    "created_at": e.created_at.isoformat(),
                                    "updated_at": e.updated_at.isoformat(),
                                    "version": e.version,
                                }.items()
                                if v
                            }
                        ],
                        embeddings=[e.embedding],
                    )
            return len(entries)
        except Exception as e:
            logger.error(f"Error adding entries: {e}")
            return 0

    def update_entry(self, entry: MemoryEntry) -> bool:
        """Update a memory entry."""
        try:
            now = datetime.now(UTC)
            new_version = entry.version + 1

            self.collection.update(
                ids=[entry.id],
                documents=[entry.content],
                metadatas=[
                    {
                        "type": entry.type.value,
                        "source_run_id": entry.source_run_id or "",
                        "tags": ",".join(entry.tags),
                        "entity_type": entry.entity_type.value if entry.entity_type else "",
                        "entity_name": entry.entity_name or "",
                        "subject_id": entry.subject_id or "",
                        "object_id": entry.object_id or "",
                        "relation_type": entry.relation_type.value if entry.relation_type else "",
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": now.isoformat(),
                        "version": new_version,
                    }
                ],
                embeddings=[entry.embedding] if entry.embedding else None,
            )
            return True
        except Exception as e:
            logger.error(f"Error updating entry {entry.id}: {e}")
            return False

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        """Get a memory entry by ID."""
        try:
            result = self.collection.get(
                ids=[entry_id], include=["documents", "metadatas", "embeddings"]
            )
            if result["ids"]:
                return self._result_to_entry(result, 0)
        except Exception as e:
            logger.error(f"Error getting entry {entry_id}: {e}")
        return None

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        try:
            self.collection.delete(ids=[entry_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting entry {entry_id}: {e}")
            return False

    def delete_run_entries(self, run_id: str) -> int:
        """Delete all entries for a research run."""
        try:
            # First get all IDs for the run
            result = self.collection.get(
                where={"source_run_id": run_id},
                include=["metadatas"],
            )
            if result["ids"]:
                self.collection.delete(ids=result["ids"])
                return len(result["ids"])
            return 0
        except Exception as e:
            logger.error(f"Error deleting run entries: {e}")
            return 0

    def search(self, query: SearchQuery) -> SearchResponse:
        """Search memory entries with input validation."""
        try:
            # Validate and sanitize query
            validated_query = validate_search_query(query)

            where = {}
            if validated_query.memory_types:
                where["type"] = {"$in": [t.value for t in validated_query.memory_types]}

            if validated_query.filters:
                for key, value in validated_query.filters.items():
                    where[key] = value

            result = self.collection.query(
                query_texts=[validated_query.query],
                n_results=validated_query.top_k,
                where=where if where else None,
                include=["documents", "metadatas", "distances", "embeddings"]
                if validated_query.include_embeddings
                else ["documents", "metadatas", "distances"],
            )

            results = []
            if result["ids"] and result["ids"][0]:
                for i, entry_id in enumerate(result["ids"][0]):
                    entry = self._query_result_to_entry(result, i)
                    if entry:
                        score = 1 - result["distances"][0][i] if result["distances"] else 1.0
                        min_score = (
                            validated_query.min_score
                            if validated_query.min_score is not None
                            else 0.0
                        )
                        if score >= min_score:
                            matched_text = self._extract_matched_text(
                                entry.content, validated_query.query
                            )
                            results.append(
                                SearchResult(
                                    entry=entry,
                                    score=score,
                                    matched_text=matched_text,
                                )
                            )

            return SearchResponse(
                results=results,
                total=len(results),
                query=validated_query,
                took_ms=0,  # Would need timing
            )
        except ValueError as e:
            logger.warning(f"Invalid search query: {e}")
            return SearchResponse(results=[], total=0, query=query)
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return SearchResponse(results=[], total=0, query=query)

    def search_by_run(
        self,
        run_id: str,
        query: str,
        top_k: int = 10,
        memory_types: list[MemoryType] | None = None,
    ) -> SearchResponse:
        """Search within a specific research run."""
        search_query = SearchQuery(
            query=query,
            top_k=top_k,
            memory_types=memory_types,
            filters={"source_run_id": run_id},
        )
        return self.search(search_query)

    def get_entries_by_type(
        self,
        memory_type: MemoryType,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """Get all entries of a specific type."""
        try:
            where = {"type": memory_type.value}
            if run_id:
                where["source_run_id"] = run_id

            result = self.collection.get(
                where=where,
                limit=limit,
                include=["documents", "metadatas", "embeddings"],
            )

            entries = []
            if result["ids"]:
                for i in range(len(result["ids"])):
                    entry = self._result_to_entry(result, i)
                    if entry:
                        entries.append(entry)
            return entries
        except Exception as e:
            logger.error(f"Error getting entries by type: {e}")
            return []

    def get_run_stats(self, run_id: str) -> dict[str, int]:
        """Get statistics for a research run."""
        try:
            result = self.collection.get(
                where={"source_run_id": run_id},
                include=["metadatas"],
            )

            stats = {"total": len(result["ids"]) if result["ids"] else 0}
            if result["metadatas"]:
                for meta in result["metadatas"]:
                    mtype = meta.get("type", "unknown")
                    stats[mtype] = stats.get(mtype, 0) + 1

            return stats
        except Exception as e:
            logger.error(f"Error getting run stats: {e}")
            return {"total": 0}

    def get_all_runs(self) -> list[str]:
        """Get all unique run IDs."""
        try:
            result = self.collection.get(
                include=["metadatas"],
            )
            run_ids = set()
            if result["metadatas"]:
                for meta in result["metadatas"]:
                    run_id = meta.get("source_run_id")
                    if run_id:
                        run_ids.add(run_id)
            return sorted(list(run_ids))
        except Exception as e:
            logger.error(f"Error getting all runs: {e}")
            return []

    def _result_to_entry(self, result: dict[str, Any], index: int) -> MemoryEntry | None:
        """Convert query result to MemoryEntry."""
        try:
            meta = result["metadatas"][index] if result["metadatas"] else {}
            return MemoryEntry(
                id=result["ids"][index],
                type=MemoryType(meta.get("type", "research_finding")),
                content=result["documents"][index] if result["documents"] else "",
                metadata={},
                embedding=result["embeddings"][index] if result.get("embeddings") else None,
                source_run_id=meta.get("source_run_id") or None,
                tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                entity_type=meta.get("entity_type") or None,
                entity_name=meta.get("entity_name") or None,
                subject_id=meta.get("subject_id") or None,
                object_id=meta.get("object_id") or None,
                relation_type=meta.get("relation_type") or None,
                created_at=datetime.fromisoformat(meta["created_at"])
                if meta.get("created_at")
                else datetime.now(UTC),
                updated_at=datetime.fromisoformat(meta["updated_at"])
                if meta.get("updated_at")
                else datetime.now(UTC),
                version=meta.get("version", 1),
            )
        except Exception as e:
            logger.error(f"Error converting result to entry: {e}")
            return None

    def _query_result_to_entry(self, result: dict[str, Any], index: int) -> MemoryEntry | None:
        """Convert query result to MemoryEntry."""
        try:
            meta = result["metadatas"][0][index] if result["metadatas"] else {}
            return MemoryEntry(
                id=result["ids"][0][index],
                type=MemoryType(meta.get("type", "research_finding")),
                content=result["documents"][0][index] if result["documents"] else "",
                metadata={},
                embedding=result["embeddings"][0][index] if result.get("embeddings") else None,
                source_run_id=meta.get("source_run_id") or None,
                tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                entity_type=meta.get("entity_type") or None,
                entity_name=meta.get("entity_name") or None,
                subject_id=meta.get("subject_id") or None,
                object_id=meta.get("object_id") or None,
                relation_type=meta.get("relation_type") or None,
                created_at=datetime.fromisoformat(meta["created_at"])
                if meta.get("created_at")
                else datetime.now(UTC),
                updated_at=datetime.fromisoformat(meta["updated_at"])
                if meta.get("updated_at")
                else datetime.now(UTC),
                version=meta.get("version", 1),
            )
        except Exception as e:
            logger.error(f"Error converting query result to entry: {e}")
            return None

    def _extract_matched_text(self, content: str, query: str, window: int = 100) -> str | None:
        """Extract text around query match."""
        query_lower = query.lower()
        content_lower = content.lower()

        idx = content_lower.find(query_lower)
        if idx == -1:
            # Try partial word matches
            words = query_lower.split()
            for word in words:
                idx = content_lower.find(word)
                if idx != -1:
                    break

        if idx == -1:
            return content[:window] + "..." if len(content) > window else content

        start = max(0, idx - window // 2)
        end = min(len(content), idx + len(query) + window // 2)

        if start > 0:
            prefix = "..."
        else:
            prefix = ""

        if end < len(content):
            suffix = "..."
        else:
            suffix = ""

        return f"{prefix}{content[start:end]}{suffix}"


# Global instance
_vs: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get global vector store instance."""
    global _vs
    if _vs is None:
        _vs = VectorStore()
    return _vs
