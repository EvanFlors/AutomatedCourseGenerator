"""Neo4j implementation of the KnowledgeGraphRepository port.

Cypher queries use UNWIND for batch operations and parameterized queries
to prevent injection. The repository accepts a session-like object so
it can be unit-tested by mocking the session API.
"""
from typing import Any, Protocol

from src.domain.knowledge_graph.entities.concept import Concept
from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation
from src.domain.knowledge_graph.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from src.domain.knowledge_graph.value_objects.relation_type import RelationType


class _AsyncSessionLike(Protocol):
    """Minimal session API used by this repository.

    Compatible with `neo4j.AsyncSession`. Allows unit tests to inject
    a mock that records calls without requiring a live database.
    """

    async def run(self, query: str, **parameters: Any) -> Any: ...
    async def close(self) -> None: ...
    async def __aenter__(self) -> "_AsyncSessionLike": ...
    async def __aexit__(self, *args: Any) -> None: ...


class _AsyncDriverLike(Protocol):
    def session(self, *args: Any, **kwargs: Any) -> _AsyncSessionLike: ...


class Neo4jKnowledgeGraphRepository(KnowledgeGraphRepository):
    """Adapter that persists concepts and relations in Neo4j.

    Graph schema (created lazily on first use):
        - (:Concept {id, name, description, source_topic_id, source_course_id,
                     embedding, metadata_json})
        - (:Course {id})                  (referenced by Concept)
        - (:Topic {id})                   (referenced by Concept)
        - (:Concept)-[r:REL_TYPE]->(:Concept)

    Vector index:
        - `concept_embedding` on `Concept.embedding`
          dimensions default to 768 to match Gemini's
          `text-embedding-004`. Override via the
          `vector_dimensions` constructor argument.
    """

    def __init__(self, driver: _AsyncDriverLike, *, vector_dimensions: int = 768):
        self._driver = driver
        self._initialized = False
        self._vector_dimensions = vector_dimensions

    async def _ensure_schema(self, session: _AsyncSessionLike) -> None:
        if self._initialized:
            return

        await session.run(
            "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS "
            "FOR (c:Concept) REQUIRE c.id IS UNIQUE"
        )
        await session.run(
            "CREATE INDEX concept_course_id IF NOT EXISTS "
            "FOR (c:Concept) ON (c.source_course_id)"
        )
        await session.run(
            "CREATE INDEX concept_topic_id IF NOT EXISTS "
            "FOR (c:Concept) ON (c.source_topic_id)"
        )
        await session.run(
            "CREATE INDEX concept_course_name IF NOT EXISTS "
            "FOR (c:Concept) ON (c.source_course_id, c.name)"
        )
        await session.run(
            "CREATE VECTOR INDEX concept_embedding IF NOT EXISTS "
            "FOR (c:Concept) ON (c.embedding) "
            "OPTIONS {indexConfig: {"
            "`vector.dimensions`: $vector_dimensions, "
            "`vector.similarity_function`: 'cosine'"
            "}}",
            vector_dimensions=self._vector_dimensions,
        )
        self._initialized = True

    async def upsert_concept(self, concept: Concept) -> None:
        await self.upsert_concepts([concept])

    async def upsert_concepts(self, concepts: list[Concept]) -> None:
        if not concepts:
            return
        rows = [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "source_topic_id": c.source_topic_id,
                "source_course_id": c.source_course_id,
                "embedding": c.embedding,
                "metadata_json": _json_dumps(c.metadata),
            }
            for c in concepts
        ]
        async with self._driver.session() as session:
            await self._ensure_schema(session)
            await session.run(
                """
                UNWIND $rows AS row
                MERGE (c:Concept {id: row.id})
                SET c.name = row.name,
                    c.description = row.description,
                    c.source_topic_id = row.source_topic_id,
                    c.source_course_id = row.source_course_id,
                    c.embedding = row.embedding,
                    c.metadata_json = row.metadata_json
                """,
                rows=rows,
            )

    async def find_concept_by_id(self, concept_id: str) -> Concept | None:
        async with self._driver.session() as session:
            await self._ensure_schema(session)
            result = await session.run(
                "MATCH (c:Concept {id: $id}) RETURN c",
                id=concept_id,
            )
            record = await result.single()
            await result.consume()
            if record is None:
                return None
            return _concept_from_node(record["c"])

    async def list_concepts_by_course(self, course_id: str) -> list[Concept]:
        async with self._driver.session() as session:
            await self._ensure_schema(session)
            result = await session.run(
                "MATCH (c:Concept {source_course_id: $course_id}) "
                "RETURN c ORDER BY c.name",
                course_id=course_id,
            )
            records = await _collect_records(result)
            return [_concept_from_node(r["c"]) for r in records]

    async def delete_concept(self, concept_id: str) -> None:
        async with self._driver.session() as session:
            await self._ensure_schema(session)
            await session.run(
                "MATCH (c:Concept {id: $id}) "
                "DETACH DELETE c",
                id=concept_id,
            )

    async def create_relation(self, relation: ConceptRelation) -> None:
        await self.create_relations([relation])

    async def create_relations(self, relations: list[ConceptRelation]) -> None:
        if not relations:
            return
        groups: dict[RelationType, list[dict[str, Any]]] = {}
        for rel in relations:
            groups.setdefault(rel.relation_type, []).append(
                {
                    "id": rel.id,
                    "source_id": rel.source_concept_id,
                    "target_id": rel.target_concept_id,
                    "weight": rel.weight,
                    "metadata_json": _json_dumps(rel.metadata),
                }
            )

        async with self._driver.session() as session:
            await self._ensure_schema(session)
            for rel_type, rows in groups.items():
                await session.run(
                    f"""
                    UNWIND $rows AS row
                    MATCH (a:Concept {{id: row.source_id}})
                    MATCH (b:Concept {{id: row.target_id}})
                    MERGE (a)-[r:{rel_type.value}]->(b)
                    SET r.id = row.id,
                        r.weight = row.weight,
                        r.metadata_json = row.metadata_json
                    """,
                    rows=rows,
                )

    async def delete_relations_for_concept(self, concept_id: str) -> None:
        async with self._driver.session() as session:
            await self._ensure_schema(session)
            await session.run(
                "MATCH (c:Concept {id: $id})-[r]-() DELETE r",
                id=concept_id,
            )

    async def get_graph_for_course(
        self,
        course_id: str,
        *,
        skip: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Concept], list[ConceptRelation]]:
        async with self._driver.session() as session:
            await self._ensure_schema(session)
            if limit is None:
                concept_result = await session.run(
                    "MATCH (c:Concept {source_course_id: $course_id}) "
                    "RETURN c ORDER BY c.name",
                    course_id=course_id,
                )
            else:
                concept_result = await session.run(
                    "MATCH (c:Concept {source_course_id: $course_id}) "
                    "RETURN c ORDER BY c.name "
                    "SKIP $skip LIMIT $limit",
                    course_id=course_id,
                    skip=skip,
                    limit=limit,
                )
            concept_records = await _collect_records(concept_result)
            concepts = [_concept_from_node(r["c"]) for r in concept_records]
            concept_ids = [c.id for c in concepts]

            if not concept_ids:
                return [], []

            relation_result = await session.run(
                """
                MATCH (a:Concept)-[r]->(b:Concept)
                WHERE a.id IN $ids AND b.id IN $ids
                RETURN a.id AS source_id,
                       b.id AS target_id,
                       type(r) AS relation_type,
                       r.id AS relation_id,
                       r.weight AS weight,
                       r.metadata_json AS metadata_json
                """,
                ids=concept_ids,
            )
            relation_records = await _collect_records(relation_result)
            relations = [_relation_from_record(r) for r in relation_records]

        return concepts, relations


def _json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload or {})


def _json_loads(payload: Any) -> dict:
    import json

    if not payload:
        return {}
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {}
    return {}


async def _collect_records(result: Any) -> list[dict[str, Any]]:
    """Collect all records from a neo4j AsyncResult, supporting both
    real drivers and test fakes.

    The real driver doesn't expose a `fetch_all` method; the only way
    to iterate is via `async for`. The fakes (used in unit tests)
    implement `fetch_all` for convenience, so we prefer it when present.
    """
    if hasattr(result, "fetch_all"):
        records = await result.fetch_all()
        await result.consume()
        return list(records)

    records: list[dict[str, Any]] = []
    async for record in result:
        records.append(record.data() if hasattr(record, "data") else dict(record))
    await result.consume()
    return records


def _concept_from_node(node: Any) -> Concept:
    """Build a Concept from a Neo4j node (dict-like)."""
    props = dict(node)
    embedding = props.get("embedding")
    if embedding is not None:
        embedding = list(embedding)
        if not embedding:
            embedding = None
    return Concept(
        id=props["id"],
        name=props.get("name", ""),
        description=props.get("description"),
        embedding=embedding,
        source_topic_id=props.get("source_topic_id"),
        source_course_id=props.get("source_course_id"),
        metadata=_json_loads(props.get("metadata_json")),
    )


def _relation_from_record(record: Any) -> ConceptRelation:
    relation_type_str = record["relation_type"]
    return ConceptRelation(
        id=record["relation_id"],
        source_concept_id=record["source_id"],
        target_concept_id=record["target_id"],
        relation_type=RelationType(relation_type_str),
        weight=record.get("weight", 1.0) or 1.0,
        metadata=_json_loads(record.get("metadata_json")),
    )
