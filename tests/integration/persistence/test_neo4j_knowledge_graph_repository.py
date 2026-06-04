"""Integration tests for Neo4jKnowledgeGraphRepository using a fake driver.

These tests verify the repository's behavior (Cypher queries,
parameters, mapping between domain entities and graph nodes) without
requiring a running Neo4j instance. For end-to-end tests with a real
Neo4j, see `test_neo4j_knowledge_graph_repository_real.py`.
"""
import pytest

from src.domain.knowledge_graph.entities.concept import Concept
from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation
from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.infrastructure.persistence.neo4j.neo4j_knowledge_graph_repository import (
    Neo4jKnowledgeGraphRepository,
)
from tests.integration.persistence.neo4j_fakes import (
    FakeNeo4jDriver,
    FakeNeo4jSession,
)

pytestmark = pytest.mark.asyncio


def _concept_node_props(concept: Concept) -> dict:
    import json

    return {
        "id": concept.id,
        "name": concept.name,
        "description": concept.description,
        "source_topic_id": concept.source_topic_id,
        "source_course_id": concept.source_course_id,
        "embedding": concept.embedding,
        "metadata_json": json.dumps(concept.metadata),
    }


class TestSchemaInitialization:
    async def test_creates_constraints_on_first_use(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concept = Concept(name="X")

        await repo.upsert_concept(concept)

        session = driver.find_session()
        all_queries = "\n".join(q for q, _ in session.calls)
        assert "CREATE CONSTRAINT" in all_queries
        assert "CREATE INDEX" in all_queries

    async def test_runs_schema_setup_only_once_per_repository(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concept = Concept(name="X")

        await repo.upsert_concept(concept)
        await repo.upsert_concept(concept)
        await repo.upsert_concept(concept)

        session = driver.find_session()
        constraint_calls = [
            q for q, _ in session.calls if "CREATE CONSTRAINT" in q
        ]
        assert len(constraint_calls) == 1


class TestUpsertConcept:
    async def test_sends_unwind_merge_query_with_all_fields(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concept = Concept(
            name="Machine Learning",
            description="A subfield of AI",
            embedding=[0.1, 0.2, 0.3],
            source_topic_id="t-1",
            source_course_id="c-1",
            metadata={"source": "video"},
        )

        await repo.upsert_concept(concept)

        session = driver.find_session()
        merge_call = next(
            (q, p) for q, p in session.calls if "MERGE (c:Concept" in q
        )
        query, params = merge_call

        assert "UNWIND $rows AS row" in query
        assert "MERGE (c:Concept {id: row.id})" in query
        assert len(params["rows"]) == 1
        row = params["rows"][0]
        assert row["id"] == concept.id
        assert row["name"] == "Machine Learning"
        assert row["description"] == "A subfield of AI"
        assert row["source_topic_id"] == "t-1"
        assert row["source_course_id"] == "c-1"
        assert row["embedding"] == [0.1, 0.2, 0.3]
        import json
        assert json.loads(row["metadata_json"]) == {"source": "video"}

    async def test_handles_concept_without_optional_fields(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concept = Concept(name="Minimal")

        await repo.upsert_concept(concept)

        session = driver.find_session()
        merge_call = next(
            (q, p) for q, p in session.calls if "MERGE (c:Concept" in q
        )
        _, params = merge_call

        assert len(params["rows"]) == 1
        row = params["rows"][0]
        assert row["description"] is None
        assert row["embedding"] is None
        import json
        assert json.loads(row["metadata_json"]) == {}


class TestFindConceptById:
    async def test_returns_none_when_not_found(self):
        driver = FakeNeo4jDriver(
            responses={"MATCH (c:Concept {id: $id})": []}
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.find_concept_by_id("missing")

        assert result is None

    async def test_returns_mapped_concept_when_found(self):
        concept = Concept(
            name="ML",
            description="desc",
            source_topic_id="t1",
            source_course_id="c1",
            embedding=[0.5, 0.6],
            metadata={"k": "v"},
        )
        driver = FakeNeo4jDriver(
            responses={"MATCH (c:Concept {id: $id})": [{"c": _concept_node_props(concept)}]}
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.find_concept_by_id(concept.id)

        assert result is not None
        assert result.id == concept.id
        assert result.name == "ML"
        assert result.description == "desc"
        assert result.source_topic_id == "t1"
        assert result.source_course_id == "c1"
        assert result.embedding == [0.5, 0.6]
        assert result.metadata == {"k": "v"}

    async def test_sends_query_with_id_parameter(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.find_concept_by_id("specific-id")

        session = driver.find_session()
        find_call = next(
            (q, p) for q, p in session.calls if "MATCH (c:Concept {id: $id})" in q
        )
        assert find_call[1]["id"] == "specific-id"


class TestListConceptsByCourse:
    async def test_returns_empty_list_when_no_concepts(self):
        driver = FakeNeo4jDriver(
            responses={"source_course_id: $course_id": []}
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.list_concepts_by_course("c1")

        assert result == []

    async def test_returns_all_concepts_for_course(self):
        c1 = Concept(name="A", source_course_id="course-1")
        c2 = Concept(name="B", source_course_id="course-1")
        c3 = Concept(name="C", source_course_id="other-course")
        driver = FakeNeo4jDriver(
            responses={
                "source_course_id: $course_id": [
                    {"c": _concept_node_props(c1)},
                    {"c": _concept_node_props(c2)},
                ]
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.list_concepts_by_course("course-1")

        assert len(result) == 2
        names = {c.name for c in result}
        assert names == {"A", "B"}


class TestDeleteConcept:
    async def test_sends_detach_delete_query(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.delete_concept("c-1")

        session = driver.find_session()
        delete_call = next(
            (q, p) for q, p in session.calls if "DETACH DELETE c" in q
        )
        assert delete_call[1]["id"] == "c-1"


class TestCreateRelation:
    async def test_sends_match_merge_with_dynamic_rel_type(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        relation = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.PREREQUISITE_OF,
            weight=0.8,
            metadata={"source": "llm"},
        )

        await repo.create_relation(relation)

        session = driver.find_session()
        rel_call = next(
            (q, p) for q, p in session.calls if "MERGE (a)-[r" in q
        )
        query, params = rel_call

        assert "PREREQUISITE_OF" in query
        assert "UNWIND $rows AS row" in query
        assert len(params["rows"]) == 1
        row = params["rows"][0]
        assert row["id"] == relation.id
        assert row["source_id"] == "a"
        assert row["target_id"] == "b"
        assert row["weight"] == 0.8
        import json
        assert json.loads(row["metadata_json"]) == {"source": "llm"}

    async def test_uses_each_relation_type_correctly(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        for rt in RelationType:
            driver.sessions = []
            rel = ConceptRelation(
                source_concept_id="a",
                target_concept_id="b",
                relation_type=rt,
            )
            await repo.create_relation(rel)
            session = driver.find_session()
            rel_call = next(
                (q, _) for q, _ in session.calls if "MERGE (a)-[r" in q
            )
            assert rt.value in rel_call[0]


class TestDeleteRelationsForConcept:
    async def test_sends_delete_query_matching_in_any_direction(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.delete_relations_for_concept("c-1")

        session = driver.find_session()
        delete_call = next(
            (q, p) for q, p in session.calls if "[r]-() DELETE r" in q
        )
        assert delete_call[1]["id"] == "c-1"


class TestGetGraphForCourse:
    async def test_returns_empty_when_no_concepts(self):
        driver = FakeNeo4jDriver(
            responses={"source_course_id: $course_id": []}
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        concepts, relations = await repo.get_graph_for_course("c1")

        assert concepts == []
        assert relations == []

    async def test_returns_concepts_and_relations(self):
        c1 = Concept(name="A", source_course_id="course-1", id="c-1")
        c2 = Concept(name="B", source_course_id="course-1", id="c-2")
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {source_course_id": [
                    {"c": _concept_node_props(c1)},
                    {"c": _concept_node_props(c2)},
                ],
                "MATCH (a:Concept)-[r]->(b:Concept)": [
                    {
                        "source_id": "c-1",
                        "target_id": "c-2",
                        "relation_type": "PREREQUISITE_OF",
                        "relation_id": "rel-1",
                        "weight": 0.9,
                        "metadata_json": '{"src": "llm"}',
                    },
                ],
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        concepts, relations = await repo.get_graph_for_course("course-1")

        assert len(concepts) == 2
        assert {c.id for c in concepts} == {"c-1", "c-2"}

        assert len(relations) == 1
        rel = relations[0]
        assert rel.source_concept_id == "c-1"
        assert rel.target_concept_id == "c-2"
        assert rel.relation_type == RelationType.PREREQUISITE_OF
        assert rel.weight == 0.9
        assert rel.metadata == {"src": "llm"}

    async def test_does_not_query_relations_when_no_concepts(self):
        driver = FakeNeo4jDriver(
            responses={"MATCH (c:Concept {source_course_id": []}
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.get_graph_for_course("empty-course")

        session = driver.find_session()
        relation_queries = [
            q for q, _ in session.calls
            if "MATCH (a:Concept)-[r]->(b:Concept)" in q
        ]
        assert relation_queries == []


class TestSessionLifecycle:
    async def test_session_is_closed_after_operation(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="X"))

        session = driver.find_session()
        assert session.closed is True

    async def test_creates_new_session_per_operation(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="A"))
        await repo.upsert_concept(Concept(name="B"))
        await repo.delete_concept("x")

        assert len(driver.sessions) == 3

    async def test_schema_setup_runs_only_once_per_repository(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="A"))
        await repo.upsert_concept(Concept(name="B"))
        await repo.upsert_concept(Concept(name="C"))

        first_session = driver.find_session(0)
        all_queries_across_sessions = [
            q for s in driver.sessions for q, _ in s.calls
        ]
        constraint_count = sum(
            1 for q in all_queries_across_sessions if "CREATE CONSTRAINT" in q
        )
        assert constraint_count == 1, (
            "Schema setup should run only on the first operation of the "
            f"first session. Got {constraint_count} CREATE CONSTRAINT calls."
        )
        assert any("CREATE CONSTRAINT" in q for q, _ in first_session.calls)


class TestUpsertConceptIdempotency:
    async def test_upsert_twice_with_different_data_sends_two_merges(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        first = Concept(name="ML", description="First version")
        second = Concept(
            id=first.id,
            name="ML",
            description="Updated description",
        )

        await repo.upsert_concept(first)
        await repo.upsert_concept(second)

        all_sessions_calls = [
            (q, p) for s in driver.sessions for q, p in s.calls
        ]
        merges = [(q, p) for q, p in all_sessions_calls if "MERGE (c:Concept" in q]
        assert len(merges) == 2
        assert merges[0][1]["rows"][0]["description"] == "First version"
        assert merges[1][1]["rows"][0]["description"] == "Updated description"

    async def test_upsert_serializes_nested_metadata_as_json(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concept = Concept(
            name="ML",
            metadata={
                "tags": ["supervised", "classification"],
                "provenance": {"source": "video", "chapter": 3},
            },
        )

        await repo.upsert_concept(concept)

        session = driver.find_session()
        _, params = session.find_call(substring="MERGE (c:Concept")
        import json

        decoded = json.loads(params["rows"][0]["metadata_json"])
        assert decoded == {
            "tags": ["supervised", "classification"],
            "provenance": {"source": "video", "chapter": 3},
        }


class TestFindConceptRoundTrip:
    async def test_find_concept_preserves_unicode_name(self):
        concept = Concept(
            name="Aprendizaje Supervisado 中文",
            description="ñ, é, ü",
            source_course_id="c-1",
        )
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {id: $id})": [
                    {"c": _concept_node_props(concept)}
                ]
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.find_concept_by_id(concept.id)

        assert result is not None
        assert result.name == "Aprendizaje Supervisado 中文"
        assert result.description == "ñ, é, ü"

    async def test_find_concept_with_no_optional_fields_returns_defaults(self):
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {id: $id})": [
                    {
                        "c": {
                            "id": "c-1",
                            "name": "Bare",
                            "description": None,
                            "source_topic_id": None,
                            "source_course_id": None,
                            "embedding": None,
                            "metadata_json": "",
                        }
                    }
                ]
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.find_concept_by_id("c-1")

        assert result is not None
        assert result.name == "Bare"
        assert result.description is None
        assert result.source_topic_id is None
        assert result.source_course_id is None
        assert result.embedding is None
        assert result.metadata == {}

    async def test_find_concept_with_empty_embedding_list_falls_back_to_none(self):
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {id: $id})": [
                    {
                        "c": {
                            "id": "c-1",
                            "name": "X",
                            "description": None,
                            "source_topic_id": None,
                            "source_course_id": None,
                            "embedding": [],
                            "metadata_json": "",
                        }
                    }
                ]
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.find_concept_by_id("c-1")

        assert result is not None
        assert result.embedding is None


class TestListConceptsOrdering:
    async def test_list_returns_concepts_in_drive_order(self):
        c1 = Concept(name="B", source_course_id="c-1")
        c2 = Concept(name="A", source_course_id="c-1")
        c3 = Concept(name="C", source_course_id="c-1")
        driver = FakeNeo4jDriver(
            responses={
                "source_course_id: $course_id": [
                    {"c": _concept_node_props(c1)},
                    {"c": _concept_node_props(c2)},
                    {"c": _concept_node_props(c3)},
                ]
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.list_concepts_by_course("c-1")

        assert [c.name for c in result] == ["B", "A", "C"]
        assert {c.id for c in result} == {c1.id, c2.id, c3.id}

    async def test_list_sends_query_with_course_id_parameter(self):
        driver = FakeNeo4jDriver(responses={"source_course_id: $course_id": []})
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.list_concepts_by_course("specific-course-id")

        session = driver.find_session()
        _, params = session.find_call(substring="source_course_id: $course_id")
        assert params["course_id"] == "specific-course-id"

    async def test_list_concepts_across_multiple_courses_isolated(self):
        c_a = Concept(name="A-in-1", source_course_id="course-1")
        c_b = Concept(name="B-in-1", source_course_id="course-1")
        c_c = Concept(name="C-in-2", source_course_id="course-2")
        driver = FakeNeo4jDriver(
            responses={
                "source_course_id: $course_id": [
                    {"c": _concept_node_props(c_a)},
                    {"c": _concept_node_props(c_b)},
                ]
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.list_concepts_by_course("course-1")

        assert len(result) == 2
        assert c_c not in result
        assert {c.source_course_id for c in result} == {"course-1"}


class TestRelationWeightAndMetadata:
    async def test_create_relation_with_zero_weight(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
            weight=0.0,
        )

        await repo.create_relation(rel)

        session = driver.find_session()
        _, params = session.find_call(substring="MERGE (a)-[r")
        assert params["rows"][0]["weight"] == 0.0

    async def test_create_relation_default_weight_is_one(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.BELONGS_TO,
        )

        await repo.create_relation(rel)

        session = driver.find_session()
        _, params = session.find_call(substring="MERGE (a)-[r")
        assert params["rows"][0]["weight"] == 1.0

    async def test_create_relation_with_empty_metadata_sends_empty_json(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.EXTENDS,
        )

        await repo.create_relation(rel)

        session = driver.find_session()
        _, params = session.find_call(substring="MERGE (a)-[r")
        import json

        assert json.loads(params["rows"][0]["metadata_json"]) == {}

    async def test_create_relation_sends_unique_id_per_relation(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        rel1 = ConceptRelation(
            source_concept_id="a", target_concept_id="b",
            relation_type=RelationType.PREREQUISITE_OF,
        )
        rel2 = ConceptRelation(
            source_concept_id="b", target_concept_id="c",
            relation_type=RelationType.PREREQUISITE_OF,
        )

        await repo.create_relation(rel1)
        await repo.create_relation(rel2)

        all_sessions_calls = [
            (q, p) for s in driver.sessions for q, p in s.calls
        ]
        merges = [(q, p) for q, p in all_sessions_calls if "MERGE (a)-[r" in q]
        assert merges[0][1]["rows"][0]["id"] != merges[1][1]["rows"][0]["id"]


class TestGetGraphFiltering:
    async def test_get_graph_returns_all_relations_for_course(self):
        c1 = Concept(name="A", source_course_id="c-1", id="c-1")
        c2 = Concept(name="B", source_course_id="c-1", id="c-2")
        c3 = Concept(name="C", source_course_id="c-1", id="c-3")
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {source_course_id": [
                    {"c": _concept_node_props(c1)},
                    {"c": _concept_node_props(c2)},
                    {"c": _concept_node_props(c3)},
                ],
                "MATCH (a:Concept)-[r]->(b:Concept)": [
                    {
                        "source_id": "c-1",
                        "target_id": "c-2",
                        "relation_type": "PREREQUISITE_OF",
                        "relation_id": "r-1",
                        "weight": 0.9,
                        "metadata_json": "{}",
                    },
                    {
                        "source_id": "c-2",
                        "target_id": "c-3",
                        "relation_type": "RELATED_TO",
                        "relation_id": "r-2",
                        "weight": 0.5,
                        "metadata_json": "{}",
                    },
                ],
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        concepts, relations = await repo.get_graph_for_course("c-1")

        assert len(concepts) == 3
        assert len(relations) == 2
        weights = sorted(r.weight for r in relations)
        assert weights == [0.5, 0.9]

    async def test_get_graph_passes_concept_ids_to_relation_query(self):
        c1 = Concept(name="A", source_course_id="c-1", id="c-A")
        c2 = Concept(name="B", source_course_id="c-1", id="c-B")
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {source_course_id": [
                    {"c": _concept_node_props(c1)},
                    {"c": _concept_node_props(c2)},
                ],
                "MATCH (a:Concept)-[r]->(b:Concept)": [],
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.get_graph_for_course("c-1")

        session = driver.find_session()
        rel_call = session.find_call(substring="MATCH (a:Concept)-[r]->(b:Concept)")
        assert set(rel_call[1]["ids"]) == {"c-A", "c-B"}

    async def test_get_graph_preserves_all_four_relation_types(self):
        c1 = Concept(name="A", source_course_id="c-1", id="c-A")
        c2 = Concept(name="B", source_course_id="c-1", id="c-B")
        relation_records = [
            {
                "source_id": "c-A",
                "target_id": "c-B",
                "relation_type": rt.value,
                "relation_id": f"r-{rt.name}",
                "weight": 1.0,
                "metadata_json": "{}",
            }
            for rt in RelationType
        ]
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {source_course_id": [
                    {"c": _concept_node_props(c1)},
                    {"c": _concept_node_props(c2)},
                ],
                "MATCH (a:Concept)-[r]->(b:Concept)": relation_records,
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        _, relations = await repo.get_graph_for_course("c-1")

        types_seen = {r.relation_type for r in relations}
        assert types_seen == set(RelationType)


class TestFakeDriverHelpers:
    async def test_find_call_helper_returns_matching_call(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        await repo.upsert_concept(Concept(name="X"))

        session = driver.find_session()
        query, params = session.find_call(substring="MERGE (c:Concept")

        assert "MERGE (c:Concept {id: row.id})" in query
        assert params["rows"][0]["id"] is not None

    async def test_find_call_helper_raises_with_helpful_message(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        await repo.upsert_concept(Concept(name="X"))

        session = driver.find_session()
        with pytest.raises(AssertionError, match="No recorded call matched"):
            session.find_call(substring="NONEXISTENT_QUERY_PATTERN")

    async def test_find_calls_returns_all_matches(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        await repo.upsert_concept(Concept(name="A"))
        await repo.upsert_concept(Concept(name="B"))
        await repo.upsert_concept(Concept(name="C"))

        all_merges = [
            (q, p)
            for s in driver.sessions
            for q, p in s.find_calls(substring="MERGE (c:Concept")
        ]

        assert len(all_merges) == 3

    async def test_strict_mode_raises_on_unmatched_query(self):
        driver = FakeNeo4jDriver(strict=True)
        repo = Neo4jKnowledgeGraphRepository(driver)
        concept = Concept(name="X")

        with pytest.raises(RuntimeError, match="No programmed response"):
            await repo.upsert_concept(concept)

    async def test_strict_mode_passes_when_all_queries_programmed(self):
        driver = FakeNeo4jDriver(
            responses={
                "CREATE CONSTRAINT": [],
                "CREATE INDEX": [],
                "CREATE VECTOR INDEX": [],
                "MERGE (c:Concept": [],
            },
            strict=True,
        )
        repo = Neo4jKnowledgeGraphRepository(driver)
        concept = Concept(name="X")

        await repo.upsert_concept(concept)

    async def test_queue_responses_consumed_in_order(self):
        driver = FakeNeo4jDriver(
            responses={
                "MATCH (c:Concept {id: $id})": [
                    [],
                    [{"c": _concept_node_props(Concept(id="x", name="X"))}],
                ]
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        first = await repo.find_concept_by_id("x")
        second = await repo.find_concept_by_id("x")

        assert first is None
        assert second is not None
        assert second.id == "x"
        assert second.name == "X"

    async def test_exact_query_match_takes_precedence_over_substring(self):
        exact_query = "MATCH (c:Concept {id: $id}) RETURN c"
        specific = [{"c": _concept_node_props(Concept(id="specific", name="S"))}]
        generic = [{"c": _concept_node_props(Concept(id="generic", name="G"))}]
        driver = FakeNeo4jDriver(
            responses={
                exact_query: specific,
                "MATCH (c:Concept {id: $id})": generic,
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        result = await repo.find_concept_by_id("specific")

        assert result is not None
        assert result.id == "specific"


class TestSchemaQueryShape:
    async def test_schema_setup_sends_five_statements(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="X"))

        first_session = driver.find_session(0)
        schema_calls = [
            (q, p) for q, p in first_session.calls
            if "CREATE CONSTRAINT" in q
            or "CREATE INDEX" in q
            or "CREATE VECTOR INDEX" in q
        ]
        assert len(schema_calls) == 5

    async def test_schema_setup_uses_if_not_exists_clause(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="X"))

        first_session = driver.find_session(0)
        for query, _ in first_session.calls:
            if any(
                marker in query
                for marker in ("CREATE CONSTRAINT", "CREATE INDEX", "CREATE VECTOR INDEX")
            ):
                assert "IF NOT EXISTS" in query

    async def test_schema_creates_indexes_for_both_course_and_topic(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="X"))

        first_session = driver.find_session(0)
        all_queries = "\n".join(q for q, _ in first_session.calls)
        assert "source_course_id" in all_queries
        assert "source_topic_id" in all_queries

    async def test_schema_creates_composite_index(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="X"))

        first_session = driver.find_session(0)
        composite_calls = [
            q for q, _ in first_session.calls
            if "CREATE INDEX" in q
            and "source_course_id, c.name" in q
        ]
        assert len(composite_calls) == 1

    async def test_schema_creates_vector_index(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="X"))

        first_session = driver.find_session(0)
        vector_calls = [
            q for q, _ in first_session.calls
            if "CREATE VECTOR INDEX" in q
        ]
        assert len(vector_calls) == 1
        assert "concept_embedding" in vector_calls[0]
        assert "vector.dimensions" in vector_calls[0]
        assert "cosine" in vector_calls[0]


class TestConcurrency:
    async def test_concurrent_upserts_all_succeed(self):
        import asyncio

        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concepts = [
            Concept(name=f"Concurrent-{i}", source_course_id="c-concurrent")
            for i in range(20)
        ]

        await asyncio.gather(*(repo.upsert_concept(c) for c in concepts))

        all_merges = [
            row
            for s in driver.sessions
            for q, p in s.calls
            if "UNWIND $rows AS row" in q
            for row in p["rows"]
        ]
        inserted_ids = {row["id"] for row in all_merges}
        assert inserted_ids == {c.id for c in concepts}

    async def test_concurrent_upserts_use_distinct_sessions(self):
        import asyncio

        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concepts = [Concept(name=f"S-{i}") for i in range(5)]

        await asyncio.gather(*(repo.upsert_concept(c) for c in concepts))

        assert len(driver.sessions) == 5

    async def test_concurrent_relation_creation_does_not_interleave(self):
        import asyncio

        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        a = Concept(name="A", id="a")
        b = Concept(name="B", id="b")
        relations = [
            ConceptRelation(
                source_concept_id="a",
                target_concept_id="b",
                relation_type=RelationType.PREREQUISITE_OF,
            )
            for _ in range(10)
        ]

        await asyncio.gather(*(repo.create_relation(r) for r in relations))

        all_sessions_calls = [
            (q, p) for s in driver.sessions for q, p in s.calls
        ]
        merges = [(q, p) for q, p in all_sessions_calls if "MERGE (a)-[r" in q]
        assert len(merges) == 10


class TestBatchUpsertConcepts:
    async def test_empty_list_sends_no_query(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concepts([])

        assert driver.sessions == []

    async def test_single_call_sends_one_unwind_query_with_all_concepts(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        concepts = [
            Concept(name="A", source_course_id="c-1"),
            Concept(name="B", source_course_id="c-1"),
            Concept(name="C", source_course_id="c-1"),
        ]

        await repo.upsert_concepts(concepts)

        session = driver.find_session()
        merges = [
            (q, p) for q, p in session.calls
            if "UNWIND $rows AS row" in q and "MERGE (c:Concept" in q
        ]
        assert len(merges) == 1
        assert len(merges[0][1]["rows"]) == 3
        names = {row["name"] for row in merges[0][1]["rows"]}
        assert names == {"A", "B", "C"}

    async def test_upsert_concept_delegates_to_batch(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.upsert_concept(Concept(name="Solo"))

        session = driver.find_session()
        merges = [
            (q, p) for q, p in session.calls
            if "UNWIND $rows AS row" in q
        ]
        assert len(merges) == 1
        assert len(merges[0][1]["rows"]) == 1


class TestBatchCreateRelations:
    async def test_empty_list_sends_no_query(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.create_relations([])

        assert driver.sessions == []

    async def test_groups_relations_by_type_into_separate_queries(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)
        relations = [
            ConceptRelation(
                source_concept_id="a", target_concept_id="b",
                relation_type=RelationType.PREREQUISITE_OF,
            ),
            ConceptRelation(
                source_concept_id="c", target_concept_id="d",
                relation_type=RelationType.PREREQUISITE_OF,
            ),
            ConceptRelation(
                source_concept_id="a", target_concept_id="c",
                relation_type=RelationType.RELATED_TO,
            ),
            ConceptRelation(
                source_concept_id="b", target_concept_id="d",
                relation_type=RelationType.BELONGS_TO,
            ),
        ]

        await repo.create_relations(relations)

        session = driver.find_session()
        relation_queries = [
            (q, p) for q, p in session.calls
            if "UNWIND $rows AS row" in q and "MERGE (a)-[r" in q
        ]
        assert len(relation_queries) == 3

        by_type: dict[str, list] = {}
        for q, p in relation_queries:
            for rt in RelationType:
                if rt.value in q:
                    by_type[rt.value] = p["rows"]
                    break

        assert len(by_type["PREREQUISITE_OF"]) == 2
        assert len(by_type["RELATED_TO"]) == 1
        assert len(by_type["BELONGS_TO"]) == 1

    async def test_create_relation_delegates_to_batch(self):
        driver = FakeNeo4jDriver()
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.create_relation(ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.PREREQUISITE_OF,
        ))

        session = driver.find_session()
        merges = [
            (q, p) for q, p in session.calls
            if "UNWIND $rows AS row" in q
        ]
        assert len(merges) == 1
        assert len(merges[0][1]["rows"]) == 1


class TestPagination:
    async def test_get_graph_with_limit_sends_limit_and_skip(self):
        driver = FakeNeo4jDriver(responses={"source_course_id: $course_id": []})
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.get_graph_for_course("c-1", skip=10, limit=25)

        session = driver.find_session()
        _, params = session.find_call(substring="source_course_id: $course_id")
        assert params["skip"] == 10
        assert params["limit"] == 25

    async def test_get_graph_without_pagination_omits_skip_limit(self):
        driver = FakeNeo4jDriver(responses={"source_course_id: $course_id": []})
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.get_graph_for_course("c-1")

        session = driver.find_session()
        _, params = session.find_call(substring="source_course_id: $course_id")
        assert "skip" not in params
        assert "limit" not in params

    async def test_pagination_uses_separate_query_with_keyword(self):
        driver = FakeNeo4jDriver(responses={"source_course_id: $course_id": []})
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.get_graph_for_course("c-1", limit=10)

        session = driver.find_session()
        query, _ = session.find_call(substring="source_course_id: $course_id")
        assert "SKIP" in query
        assert "LIMIT" in query

    async def test_pagination_passes_paginated_concept_ids_to_relation_query(self):
        c1 = Concept(name="A", source_course_id="c-1", id="c-A")
        c2 = Concept(name="B", source_course_id="c-1", id="c-B")
        driver = FakeNeo4jDriver(
            responses={
                "source_course_id: $course_id": [
                    {"c": _concept_node_props(c1)},
                    {"c": _concept_node_props(c2)},
                ],
                "MATCH (a:Concept)-[r]->(b:Concept)": [],
            }
        )
        repo = Neo4jKnowledgeGraphRepository(driver)

        await repo.get_graph_for_course("c-1", limit=2)

        session = driver.find_session()
        rel_call = session.find_call(substring="MATCH (a:Concept)-[r]->(b:Concept)")
        assert set(rel_call[1]["ids"]) == {"c-A", "c-B"}
