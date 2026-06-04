"""End-to-end integration tests with a real Neo4j instance via testcontainers.

These tests are SLOW (image pull, container start). They are skipped
if Docker is not available. To run them explicitly:

    pytest -m requires_docker
    pytest -m "not requires_docker"  # exclude them

The session-scoped fixture starts a single Neo4j container for the
entire test session and cleans it up at the end.
"""
import os
import uuid

import pytest
import pytest_asyncio

from src.domain.knowledge_graph.entities.concept import Concept
from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation
from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.infrastructure.persistence.neo4j.neo4j_knowledge_graph_repository import (
    Neo4jKnowledgeGraphRepository,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.requires_docker,
]


def _docker_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


if not _docker_available():
    pytest.skip("Docker not available", allow_module_level=True)


@pytest.fixture(scope="session")
def neo4j_container():
    from testcontainers.neo4j import Neo4jContainer

    container = Neo4jContainer("neo4j:5.26-community")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest_asyncio.fixture
async def neo4j_repo(neo4j_container):
    """Fresh driver + repository connected to the test container.

    Wipes the database before each test to guarantee isolation.
    The repository is configured with 3-dim vectors to match the
    small synthetic embeddings used in these tests.
    """
    from neo4j import AsyncGraphDatabase

    uri = neo4j_container.get_connection_url()
    user = "neo4j"
    password = neo4j_container.password

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        await driver.execute_query(
            "MATCH (n) DETACH DELETE n",
        )
    except Exception:
        pass

    repo = Neo4jKnowledgeGraphRepository(driver, vector_dimensions=3)
    try:
        yield repo
    finally:
        await driver.close()


def _make_concept(
    name: str = "ML",
    course_id: str = "course-1",
    topic_id: str = "topic-1",
) -> Concept:
    return Concept(
        id=str(uuid.uuid4()),
        name=name,
        description=f"Description of {name}",
        embedding=[0.1, 0.2, 0.3],
        source_topic_id=topic_id,
        source_course_id=course_id,
        metadata={"source": "test"},
    )


def _make_relation(
    source: Concept,
    target: Concept,
    rel_type: RelationType = RelationType.PREREQUISITE_OF,
    weight: float = 0.8,
) -> ConceptRelation:
    return ConceptRelation(
        id=str(uuid.uuid4()),
        source_concept_id=source.id,
        target_concept_id=target.id,
        relation_type=rel_type,
        weight=weight,
    )


class TestConceptRoundTrip:
    async def test_upsert_then_find(self, neo4j_repo):
        concept = _make_concept("Neural Networks")

        await neo4j_repo.upsert_concept(concept)
        loaded = await neo4j_repo.find_concept_by_id(concept.id)

        assert loaded is not None
        assert loaded.id == concept.id
        assert loaded.name == "Neural Networks"
        assert loaded.description == concept.description
        assert loaded.embedding == [0.1, 0.2, 0.3]
        assert loaded.source_topic_id == "topic-1"
        assert loaded.source_course_id == "course-1"
        assert loaded.metadata == {"source": "test"}

    async def test_upsert_is_idempotent(self, neo4j_repo):
        concept = _make_concept("Idempotent")

        await neo4j_repo.upsert_concept(concept)
        await neo4j_repo.upsert_concept(concept)
        await neo4j_repo.upsert_concept(concept)

        concepts = await neo4j_repo.list_concepts_by_course("course-1")
        matching = [c for c in concepts if c.id == concept.id]
        assert len(matching) == 1

    async def test_upsert_updates_existing_node(self, neo4j_repo):
        concept = _make_concept("Original")
        await neo4j_repo.upsert_concept(concept)

        concept.update_description("Updated description")
        await neo4j_repo.upsert_concept(concept)

        loaded = await neo4j_repo.find_concept_by_id(concept.id)
        assert loaded is not None
        assert loaded.description == "Updated description"


class TestListByCourse:
    async def test_returns_only_concepts_for_course(self, neo4j_repo):
        a = _make_concept("A", course_id="course-1")
        b = _make_concept("B", course_id="course-1")
        c = _make_concept("C", course_id="course-2")

        for concept in (a, b, c):
            await neo4j_repo.upsert_concept(concept)

        result = await neo4j_repo.list_concepts_by_course("course-1")

        names = {c.name for c in result}
        assert names == {"A", "B"}


class TestRelations:
    async def test_create_and_get_graph(self, neo4j_repo):
        a = _make_concept("A")
        b = _make_concept("B")
        c = _make_concept("C")

        for concept in (a, b, c):
            await neo4j_repo.upsert_concept(concept)

        ab = _make_relation(a, b, RelationType.PREREQUISITE_OF)
        bc = _make_relation(b, c, RelationType.RELATED_TO, weight=0.5)
        await neo4j_repo.create_relation(ab)
        await neo4j_repo.create_relation(bc)

        concepts, relations = await neo4j_repo.get_graph_for_course("course-1")

        assert {c.id for c in concepts} == {a.id, b.id, c.id}
        assert len(relations) == 2

        by_type = {(r.source_concept_id, r.relation_type): r for r in relations}
        assert (a.id, RelationType.PREREQUISITE_OF) in by_type
        assert (b.id, RelationType.RELATED_TO) in by_type
        assert by_type[(b.id, RelationType.RELATED_TO)].weight == 0.5

    @pytest.mark.parametrize(
        "rel_type",
        list(RelationType),
    )
    async def test_all_relation_types_round_trip(self, neo4j_repo, rel_type):
        a = _make_concept("Source")
        b = _make_concept("Target")
        await neo4j_repo.upsert_concept(a)
        await neo4j_repo.upsert_concept(b)

        rel = _make_relation(a, b, rel_type)
        await neo4j_repo.create_relation(rel)

        _, relations = await neo4j_repo.get_graph_for_course("course-1")
        matching = [
            r for r in relations
            if r.source_concept_id == a.id and r.relation_type == rel_type
        ]
        assert len(matching) == 1


class TestDelete:
    async def test_delete_concept_removes_node_and_relations(self, neo4j_repo):
        a = _make_concept("A")
        b = _make_concept("B")
        await neo4j_repo.upsert_concept(a)
        await neo4j_repo.upsert_concept(b)
        await neo4j_repo.create_relation(_make_relation(a, b))

        await neo4j_repo.delete_concept(a.id)

        assert await neo4j_repo.find_concept_by_id(a.id) is None

        _, relations = await neo4j_repo.get_graph_for_course("course-1")
        assert all(r.source_concept_id != a.id for r in relations)

    async def test_delete_relations_for_concept(self, neo4j_repo):
        a = _make_concept("A")
        b = _make_concept("B")
        c = _make_concept("C")
        for concept in (a, b, c):
            await neo4j_repo.upsert_concept(concept)
        await neo4j_repo.create_relation(_make_relation(a, b))
        await neo4j_repo.create_relation(_make_relation(c, b))

        await neo4j_repo.delete_relations_for_concept(b.id)

        _, relations = await neo4j_repo.get_graph_for_course("course-1")
        assert all(
            r.source_concept_id != b.id and r.target_concept_id != b.id
            for r in relations
        )


class TestBatchOperations:
    async def test_upsert_concepts_inserts_all_in_one_call(self, neo4j_repo):
        concepts = [
            _make_concept(f"Batch-{i}", course_id="course-batch")
            for i in range(10)
        ]

        await neo4j_repo.upsert_concepts(concepts)

        loaded = await neo4j_repo.list_concepts_by_course("course-batch")
        assert {c.id for c in loaded} == {c.id for c in concepts}

    async def test_upsert_concepts_empty_list_is_noop(self, neo4j_repo):
        await neo4j_repo.upsert_concepts([])

        loaded = await neo4j_repo.list_concepts_by_course("course-1")
        assert loaded == []

    async def test_create_relations_inserts_all_in_one_call(self, neo4j_repo):
        concepts = [_make_concept(f"R-{i}") for i in range(5)]
        await neo4j_repo.upsert_concepts(concepts)

        relations = [
            _make_relation(concepts[i], concepts[i + 1], RelationType.RELATED_TO)
            for i in range(4)
        ]
        await neo4j_repo.create_relations(relations)

        _, loaded_relations = await neo4j_repo.get_graph_for_course("course-1")
        assert {r.id for r in loaded_relations} == {r.id for r in relations}

    async def test_create_relations_with_mixed_types_groups_correctly(
        self, neo4j_repo,
    ):
        a = _make_concept("A")
        b = _make_concept("B")
        c = _make_concept("C")
        d = _make_concept("D")
        await neo4j_repo.upsert_concepts([a, b, c, d])

        relations = [
            _make_relation(a, b, RelationType.PREREQUISITE_OF),
            _make_relation(c, d, RelationType.PREREQUISITE_OF),
            _make_relation(a, c, RelationType.RELATED_TO),
            _make_relation(b, d, RelationType.BELONGS_TO),
        ]
        await neo4j_repo.create_relations(relations)

        _, loaded_relations = await neo4j_repo.get_graph_for_course("course-1")
        assert {r.id for r in loaded_relations} == {r.id for r in relations}


class TestPaginationReal:
    async def test_get_graph_with_limit_returns_subset(self, neo4j_repo):
        concepts = [
            _make_concept(f"P-{i:02d}", course_id="course-pag")
            for i in range(10)
        ]
        await neo4j_repo.upsert_concepts(concepts)

        concepts_loaded, _ = await neo4j_repo.get_graph_for_course(
            "course-pag", skip=2, limit=5,
        )

        assert len(concepts_loaded) == 5
        assert {c.id for c in concepts_loaded}.issubset({c.id for c in concepts})

    async def test_get_graph_with_limit_passes_ids_to_relation_query(
        self, neo4j_repo,
    ):
        a = _make_concept("A", course_id="course-pag-rel")
        b = _make_concept("B", course_id="course-pag-rel")
        c = _make_concept("C", course_id="course-pag-rel")
        await neo4j_repo.upsert_concepts([a, b, c])
        await neo4j_repo.create_relations([
            _make_relation(a, b, RelationType.RELATED_TO),
            _make_relation(a, c, RelationType.RELATED_TO),
        ])

        concepts_loaded, relations_loaded = await neo4j_repo.get_graph_for_course(
            "course-pag-rel", limit=2,
        )

        loaded_ids = {c.id for c in concepts_loaded}
        assert len(loaded_ids) == 2
        for rel in relations_loaded:
            assert rel.source_concept_id in loaded_ids
            assert rel.target_concept_id in loaded_ids


class TestVectorIndex:
    async def test_vector_index_is_created_on_first_use(self, neo4j_container):
        from neo4j import AsyncGraphDatabase

        uri = neo4j_container.get_connection_url()
        user = "neo4j"
        password = neo4j_container.password

        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        try:
            try:
                await driver.execute_query("MATCH (n) DETACH DELETE n")
            except Exception:
                pass

            repo = Neo4jKnowledgeGraphRepository(driver, vector_dimensions=3)
            await repo.upsert_concept(_make_concept("TriggersSchema"))

            indexes, _, _ = await driver.execute_query(
                "SHOW INDEXES YIELD name, type, entityType "
                "WHERE name = 'concept_embedding' "
                "RETURN name, type, entityType"
            )
            assert len(indexes) == 1
            assert indexes[0]["name"] == "concept_embedding"
            assert indexes[0]["type"] == "VECTOR"
            assert indexes[0]["entityType"] == "NODE"
        finally:
            await driver.close()


class TestConcurrencyReal:
    async def test_concurrent_upserts_all_persist(self, neo4j_repo):
        import asyncio

        concepts = [
            _make_concept(f"Race-{i}", course_id="course-race")
            for i in range(15)
        ]

        await asyncio.gather(*(neo4j_repo.upsert_concept(c) for c in concepts))

        loaded = await neo4j_repo.list_concepts_by_course("course-race")
        assert {c.id for c in loaded} == {c.id for c in concepts}

    async def test_concurrent_upserts_with_schema_init_do_not_corrupt(
        self, neo4j_container,
    ):
        import asyncio

        from neo4j import AsyncGraphDatabase

        uri = neo4j_container.get_connection_url()
        user = "neo4j"
        password = neo4j_container.password

        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        try:
            try:
                await driver.execute_query("MATCH (n) DETACH DELETE n")
            except Exception:
                pass

            repos = [
                Neo4jKnowledgeGraphRepository(driver, vector_dimensions=3)
                for _ in range(5)
            ]
            concepts_per_repo = 4
            all_concepts = [
                _make_concept(
                    f"Race-{repo_idx}-{i}",
                    course_id=f"course-race-{repo_idx}",
                )
                for repo_idx in range(len(repos))
                for i in range(concepts_per_repo)
            ]

            await asyncio.gather(
                *(
                    repo.upsert_concept(c)
                    for repo, c in zip(
                        [r for r in repos for _ in range(concepts_per_repo)],
                        all_concepts,
                    )
                )
            )

            for repo_idx in range(len(repos)):
                loaded = await repos[repo_idx].list_concepts_by_course(
                    f"course-race-{repo_idx}"
                )
                expected_ids = {
                    c.id
                    for c in all_concepts
                    if c.source_course_id == f"course-race-{repo_idx}"
                }
                assert {c.id for c in loaded} == expected_ids
        finally:
            await driver.close()
