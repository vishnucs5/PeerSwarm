"""
Neo4j knowledge graph for entities and relationships.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

from neo4j import Driver, GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable

from src.config import get_settings
from src.models.memory import Entity, Relation
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeGraph:
    """Neo4j knowledge graph for research entities and relationships."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        settings = get_settings()

        self.uri = uri or settings.storage.neo4j_uri
        self.user = user or settings.storage.neo4j_user
        self.password = password or settings.storage.neo4j_password
        self.database = database or settings.storage.neo4j_database

        self._driver: Driver | None = None

    @property
    def driver(self) -> Driver:
        """Get or create Neo4j driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
        return self._driver

    def close(self):
        """Close the driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None

    @contextmanager
    def session(self) -> Session:
        """Get a session context manager."""
        session = self.driver.session(database=self.database)
        try:
            yield session
        finally:
            session.close()

    def verify_connection(self) -> bool:
        """Verify database connection."""
        try:
            with self.session() as session:
                session.run("RETURN 1")
            return True
        except ServiceUnavailable:
            return False

    def initialize_schema(self):
        """Create indexes and constraints."""
        with self.session() as session:
            # Constraints
            session.run("""
                CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
            """)

            session.run("""
                CREATE CONSTRAINT relation_id_unique IF NOT EXISTS
                FOR ()-[r:RELATES]->() REQUIRE r.id IS UNIQUE
            """)

            # Indexes
            session.run("""
                CREATE INDEX entity_name_idx IF NOT EXISTS
                FOR (e:Entity) ON (e.name)
            """)

            session.run("""
                CREATE INDEX entity_type_idx IF NOT EXISTS
                FOR (e:Entity) ON (e.type)
            """)

            session.run("""
                CREATE INDEX relation_type_idx IF NOT EXISTS
                FOR ()-[r:RELATES]->() ON (r.type)
            """)

            session.run("""
                CREATE INDEX entity_source_idx IF NOT EXISTS
                FOR (e:Entity) ON (e.source_run_id)
            """)

            logger.info("Knowledge graph schema initialized")

    # Entity operations
    def upsert_entity(self, entity: Entity) -> bool:
        """Insert or update an entity."""
        try:
            with self.session() as session:
                session.run(
                    """
                    MERGE (e:Entity {id: $id})
                    SET e.name = $name,
                        e.type = $type,
                        e.description = $description,
                        e.source_run_id = $source_run_id,
                        e.confidence = $confidence,
                        e.updated_at = $updated_at
                    """,
                    id=entity.id,
                    name=entity.name,
                    type=entity.type,
                    description=entity.description,
                    source_run_id=entity.source_run_ids[0] if entity.source_run_ids else "",
                    confidence=entity.properties.get("confidence", 1.0)
                    if entity.properties
                    else 1.0,
                    updated_at=datetime.now(UTC).isoformat(),
                )
            return True
        except Exception as e:
            logger.error(f"Error upserting entity {entity.id}: {e}")
            return False

    def upsert_entities(self, entities: list[Entity]) -> int:
        """Batch upsert entities."""
        count = 0
        for entity in entities:
            if self.upsert_entity(entity):
                count += 1
        return count

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        try:
            with self.session() as session:
                result = session.run(
                    "MATCH (e:Entity {id: $id}) RETURN e",
                    id=entity_id,
                )
                record = result.single()
                if record:
                    node = record["e"]
                    return Entity(
                        id=node["id"],
                        name=node["name"],
                        type=node["type"],
                        description=node.get("description", ""),
                        source_run_ids=[node.get("source_run_id", "")]
                        if node.get("source_run_id")
                        else [],
                        properties={"confidence": node.get("confidence", 1.0)},
                    )
        except Exception as e:
            logger.error(f"Error getting entity {entity_id}: {e}")
        return None

    def search_entities(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """Search entities by name/description."""
        try:
            with self.session() as session:
                cypher = """
                    MATCH (e:Entity)
                    WHERE (e.name CONTAINS $query OR e.description CONTAINS $query)
                """
                params = {"query": query, "limit": limit}

                if entity_types:
                    cypher += " AND e.type IN $types"
                    params["types"] = entity_types

                cypher += " RETURN e LIMIT $limit"

                result = session.run(cypher, params)
                entities = []
                for record in result:
                    node = record["e"]
                    entities.append(
                        Entity(
                            id=node["id"],
                            name=node["name"],
                            type=node["type"],
                            description=node.get("description", ""),
                            source_run_ids=[node.get("source_run_id", "")]
                            if node.get("source_run_id")
                            else [],
                            properties={"confidence": node.get("confidence", 1.0)},
                        )
                    )
                return entities
        except Exception as e:
            logger.error(f"Error searching entities: {e}")
            return []

    def get_entities_for_run(self, run_id: str) -> list[Entity]:
        """Get all entities from a research run."""
        try:
            with self.session() as session:
                result = session.run(
                    "MATCH (e:Entity {source_run_id: $run_id}) RETURN e",
                    run_id=run_id,
                )
                entities = []
                for record in result:
                    node = record["e"]
                    entities.append(
                        Entity(
                            id=node["id"],
                            name=node["name"],
                            type=node["type"],
                            description=node.get("description", ""),
                            source_run_ids=[node.get("source_run_id", "")]
                            if node.get("source_run_id")
                            else [],
                            properties={"confidence": node.get("confidence", 1.0)},
                        )
                    )
                return entities
        except Exception as e:
            logger.error(f"Error getting entities for run {run_id}: {e}")
            return []

    # Relationship operations
    def upsert_relation(self, relation: Relation) -> bool:
        """Insert or update a relationship."""
        try:
            with self.session() as session:
                session.run(
                    """
                    MATCH (source:Entity {id: $source_id})
                    MATCH (target:Entity {id: $target_id})
                    MERGE (source)-[r:RELATES {id: $id}]->(target)
                    SET r.type = $type,
                        r.description = $description,
                        r.confidence = $confidence,
                        r.source_run_id = $source_run_id,
                        r.updated_at = $updated_at
                    """,
                    id=relation.id,
                    source_id=relation.subject_id,
                    target_id=relation.object_id,
                    type=relation.type.value,
                    description=relation.evidence[0] if relation.evidence else "",
                    confidence=relation.weight,
                    source_run_id=relation.source_run_ids[0] if relation.source_run_ids else "",
                    updated_at=datetime.now(UTC).isoformat(),
                )
            return True
        except Exception as e:
            logger.error(f"Error upserting relation {relation.id}: {e}")
            return False

    def upsert_relations(self, relations: list[Relation]) -> int:
        """Batch upsert relations."""
        count = 0
        for relation in relations:
            if self.upsert_relation(relation):
                count += 1
        return count

    def get_relations(
        self,
        entity_id: str,
        relation_types: list[str] | None = None,
        direction: str = "both",
    ) -> list[Relation]:
        """Get relations for an entity."""
        try:
            with self.session() as session:
                if direction == "outgoing":
                    cypher = "MATCH (source:Entity {id: $id})-[r:RELATES]->(target:Entity) RETURN r, source.id as source_id, target.id as target_id"
                elif direction == "incoming":
                    cypher = "MATCH (source:Entity)-[r:RELATES]->(target:Entity {id: $id}) RETURN r, source.id as source_id, target.id as target_id"
                else:
                    cypher = "MATCH (source:Entity)-[r:RELATES]-(target:Entity) WHERE source.id = $id OR target.id = $id RETURN r, source.id as source_id, target.id as target_id"

                params = {"id": entity_id}
                if relation_types:
                    cypher = cypher.replace("RETURN", "WHERE r.type IN $types RETURN")
                    params["types"] = relation_types

                result = session.run(cypher, params)
                relations = []
                for record in result:
                    rel = record["r"]
                    relations.append(
                        Relation(
                            id=rel["id"],
                            subject_id=record["source_id"],
                            object_id=record["target_id"],
                            type=rel["type"],
                            weight=rel.get("confidence", 1.0),
                            evidence=[rel.get("description", "")] if rel.get("description") else [],
                            source_run_ids=[rel.get("source_run_id", "")]
                            if rel.get("source_run_id")
                            else [],
                        )
                    )
                return relations
        except Exception as e:
            logger.error(f"Error getting relations for {entity_id}: {e}")
            return []

    def get_subgraph(
        self,
        entity_ids: list[str],
        depth: int = 2,
    ) -> tuple[list[Entity], list[Relation]]:
        """Get subgraph around entities."""
        try:
            with self.session() as session:
                # Get entities
                entity_result = session.run(
                    f"""
                    MATCH (e:Entity) WHERE e.id IN $ids
                    OPTIONAL MATCH (e)-[r:RELATES*1..{max(1, min(depth, 10))}]-(connected)
                    RETURN DISTINCT e, connected
                    """,
                    ids=entity_ids,
                )

                entities = []
                seen_ids = set()
                for record in entity_result:
                    for node in [record["e"], record["connected"]]:
                        if node and node["id"] not in seen_ids:
                            seen_ids.add(node["id"])
                            entities.append(
                                Entity(
                                    id=node["id"],
                                    name=node["name"],
                                    type=node["type"],
                                    description=node.get("description", ""),
                                    source_run_ids=[node.get("source_run_id", "")]
                                    if node.get("source_run_id")
                                    else [],
                                    properties={"confidence": node.get("confidence", 1.0)},
                                )
                            )

                # Get relations
                rel_result = session.run(
                    """
                    MATCH (source:Entity)-[r:RELATES]->(target:Entity) 
                    WHERE source.id IN $ids OR target.id IN $ids
                    RETURN DISTINCT r, source.id as source_id, target.id as target_id
                    """,
                    ids=entity_ids,
                )

                relations = []
                for record in rel_result:
                    rel = record["r"]
                    relations.append(
                        Relation(
                            id=rel["id"],
                            subject_id=record["source_id"],
                            object_id=record["target_id"],
                            type=rel["type"],
                            weight=rel.get("confidence", 1.0),
                            evidence=[rel.get("description", "")] if rel.get("description") else [],
                            source_run_ids=[rel.get("source_run_id", "")]
                            if rel.get("source_run_id")
                            else [],
                        )
                    )

                return entities, relations
        except Exception as e:
            logger.error(f"Error getting subgraph: {e}")
            return [], []

    def delete_run_data(self, run_id: str) -> bool:
        """Delete all data for a research run."""
        try:
            with self.session() as session:
                session.run(
                    "MATCH (e:Entity {source_run_id: $run_id}) DETACH DELETE e",
                    run_id=run_id,
                )
            logger.info(f"Deleted knowledge graph data for run {run_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting run data: {e}")
            return False

    def get_stats(self) -> dict[str, int]:
        """Get graph statistics."""
        try:
            with self.session() as session:
                entity_count = session.run("MATCH (e:Entity) RETURN count(e) as c").single()["c"]
                relation_count = session.run(
                    "MATCH ()-[r:RELATES]->() RETURN count(r) as c"
                ).single()["c"]
                return {"entities": entity_count, "relations": relation_count}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"entities": 0, "relations": 0}


# Global instance
_kg: KnowledgeGraph | None = None


def get_knowledge_graph() -> KnowledgeGraph:
    """Get global knowledge graph instance."""
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
    return _kg
