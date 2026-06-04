"""Integration tests for CourseGenerationService.

These tests wire the real `CourseGenerationService` to
in-memory fakes for every port. They verify the orchestration
logic end-to-end without touching Postgres, Neo4j, or Gemini.
"""
import pytest

from src.application.services.course_generation_service import (
    CourseGenerationService,
)
from src.domain.generation.entities.course_generation_job import CourseGenerationJob
from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.generation.entities.extracted_relation import ExtractedRelation
from src.domain.generation.value_objects.job_status import JobStatus
from src.domain.generation.value_objects.source_type import SourceType
from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from tests.integration.application.generation_fakes import (
    FakeChunkingService,
    FakeConceptAgent,
    FakeEmbeddingService,
    FakeKnowledgeGraphRepository,
    FakeRelationAgent,
    FakeTextExtractionRepository,
    InMemoryJobRepository,
)

pytestmark = pytest.mark.asyncio


def _make_service(
    *,
    concepts_per_chunk: list[list[ExtractedConcept]] | None = None,
    relations_per_call: list[list[ExtractedRelation]] | None = None,
    chunk_size: int = 100,
) -> tuple[CourseGenerationService, dict]:
    text_extraction = FakeTextExtractionRepository()
    chunking = FakeChunkingService(chunk_size=chunk_size)
    concept_agent = FakeConceptAgent(concepts_per_chunk=concepts_per_chunk)
    relation_agent = FakeRelationAgent(relations_per_call=relations_per_call)
    embedding_service = FakeEmbeddingService()
    knowledge_graph = FakeKnowledgeGraphRepository()
    job_repo = InMemoryJobRepository()
    service = CourseGenerationService(
        text_extraction=text_extraction,
        chunking=chunking,
        concept_agent=concept_agent,
        relation_agent=relation_agent,
        embedding_service=embedding_service,
        knowledge_graph=knowledge_graph,
        job_repository=job_repo,
        concurrency=2,
    )
    return service, {
        "text_extraction": text_extraction,
        "chunking": chunking,
        "concept_agent": concept_agent,
        "relation_agent": relation_agent,
        "embedding_service": embedding_service,
        "knowledge_graph": knowledge_graph,
        "job_repo": job_repo,
    }


def _make_text_source(content: str = "Machine learning is a subfield of AI.") -> CourseSource:
    return CourseSource(source_type=SourceType.TEXT, content=content)


class TestHappyPath:
    async def test_marks_job_completed_on_success(self):
        service, fakes = _make_service()
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source()],
        )

        result = await service.run(job)

        assert result.status == JobStatus.COMPLETED
        assert result.error_message is None

    async def test_persists_job_at_each_stage(self):
        service, fakes = _make_service()
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source()],
        )

        await service.run(job)

        saved_states = [j.status for j in fakes["job_repo"].history]
        assert JobStatus.PENDING in saved_states
        assert JobStatus.RUNNING in saved_states
        assert JobStatus.COMPLETED in saved_states

    async def test_extracts_text_for_each_source(self):
        service, fakes = _make_service()
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[
                _make_text_source("Source 1"),
                _make_text_source("Source 2"),
            ],
        )

        await service.run(job)

        assert len(fakes["text_extraction"].calls) == 2

    async def test_chunks_extracted_text(self):
        service, fakes = _make_service(
            chunk_size=30,
        )
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source("a" * 100)],
        )

        await service.run(job)

        assert fakes["chunking"].calls
        assert fakes["concept_agent"].calls
        for chunk in fakes["concept_agent"].calls:
            assert len(chunk.text) <= 30


class TestConceptPersistence:
    async def test_upserts_extracted_concepts_to_graph(self):
        service, fakes = _make_service(
            concepts_per_chunk=[
                [
                    ExtractedConcept(name="ML", description="Machine Learning"),
                    ExtractedConcept(name="AI"),
                ],
            ],
        )
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source()],
        )

        await service.run(job)

        assert len(fakes["knowledge_graph"].upserted_concepts) == 2
        names = {c.name for c in fakes["knowledge_graph"].upserted_concepts}
        assert names == {"ML", "AI"}
        for c in fakes["knowledge_graph"].upserted_concepts:
            assert c.source_course_id == "c-1"

    async def test_deduplicates_concepts_across_chunks(self):
        service, fakes = _make_service(
            chunk_size=50,
        )
        text = "ML DL and RL are topics. " * 3
        fakes["concept_agent"]._queue = [
            [ExtractedConcept(name="ML"), ExtractedConcept(name="DL")],
            [ExtractedConcept(name="ML"), ExtractedConcept(name="RL")],
        ]
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source(text)],
        )

        await service.run(job)

        names = {c.name for c in fakes["knowledge_graph"].upserted_concepts}
        assert {"ML", "DL", "RL"}.issubset(names)
        assert all(not n.startswith("Concept from") for n in names)

    async def test_concepts_carry_embeddings(self):
        service, fakes = _make_service(
            concepts_per_chunk=[
                [ExtractedConcept(name="ML")],
            ],
        )
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source()],
        )

        await service.run(job)

        assert fakes["embedding_service"].calls == ["ML"]
        for c in fakes["knowledge_graph"].upserted_concepts:
            assert c.embedding is not None
            assert len(c.embedding) == 4


class TestRelationPersistence:
    async def test_creates_relations_in_graph(self):
        service, fakes = _make_service(
            chunk_size=50,
        )
        text = "ML and DL are related. " * 10
        fakes["concept_agent"]._queue = [
            [ExtractedConcept(name="ML"), ExtractedConcept(name="DL")],
        ]
        fakes["relation_agent"]._queue = [
            [ExtractedRelation(
                source_name="ML",
                target_name="DL",
                relation_type=RelationType.RELATED_TO,
            )],
        ]
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source(text)],
        )

        await service.run(job)

        assert len(fakes["knowledge_graph"].created_relations) == 1
        rel = fakes["knowledge_graph"].created_relations[0]
        source_concept = next(
            c for c in fakes["knowledge_graph"].upserted_concepts if c.name == "ML"
        )
        target_concept = next(
            c for c in fakes["knowledge_graph"].upserted_concepts if c.name == "DL"
        )
        assert rel.source_concept_id == source_concept.id
        assert rel.target_concept_id == target_concept.id

    async def test_filters_relations_with_unknown_endpoints(self):
        service, fakes = _make_service(
            chunk_size=50,
        )
        text = "ML is great. " * 10
        fakes["concept_agent"]._queue = [
            [ExtractedConcept(name="ML")],
        ]
        fakes["relation_agent"]._queue = [
            [ExtractedRelation(
                source_name="ML",
                target_name="DL",
                relation_type=RelationType.RELATED_TO,
            )],
        ]
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source(text)],
        )

        await service.run(job)

        assert fakes["knowledge_graph"].created_relations == []

    async def test_deduplicates_relations_with_higher_weight_wins(self):
        service, fakes = _make_service(
            chunk_size=50,
        )
        text = "ML is a field. " * 10
        fakes["concept_agent"]._queue = [
            [ExtractedConcept(name="ML"), ExtractedConcept(name="DL")],
            [ExtractedConcept(name="ML"), ExtractedConcept(name="DL")],
        ]
        fakes["relation_agent"]._queue = [
            [ExtractedRelation(
                source_name="ML", target_name="DL",
                relation_type=RelationType.RELATED_TO, weight=0.3,
            )],
            [ExtractedRelation(
                source_name="ML", target_name="DL",
                relation_type=RelationType.RELATED_TO, weight=0.9,
            )],
        ]
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source(text)],
        )

        await service.run(job)

        relations = fakes["knowledge_graph"].created_relations
        assert len(relations) == 1
        assert relations[0].weight == 0.9


class TestFailurePath:
    async def test_marks_job_failed_when_stage_raises(self):
        service, fakes = _make_service()
        fakes["embedding_service"].embed_many = _raising_embed

        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source()],
        )

        with pytest.raises(RuntimeError, match="embedding boom"):
            await service.run(job)

        assert job.status == JobStatus.FAILED
        assert job.error_message is not None
        assert "embedding boom" in job.error_message

    async def test_persists_failed_job_in_repository(self):
        service, fakes = _make_service()
        fakes["embedding_service"].embed_many = _raising_embed

        job = CourseGenerationJob(
            course_id="c-1",
            sources=[_make_text_source()],
        )

        with pytest.raises(RuntimeError):
            await service.run(job)

        persisted = await fakes["job_repo"].find_by_id(job.id)
        assert persisted is not None
        assert persisted.status == JobStatus.FAILED
        assert persisted.error_message is not None


class TestInputValidation:
    async def test_rejects_non_job_argument(self):
        service, _ = _make_service()

        with pytest.raises(Exception):
            await service.run("not a job")

    async def test_rejects_job_with_no_sources(self):
        from src.domain.shared.exceptions.validation_error import ValidationError

        service, _ = _make_service()
        with pytest.raises(ValidationError):
            CourseGenerationJob(course_id="c", sources=[])


async def _raising_embed(_texts):
    raise RuntimeError("embedding boom")
