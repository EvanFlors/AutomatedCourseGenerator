"""Smoke tests: verify the domain layer is importable and minimally functional.

These tests guard against runtime import errors and broken package wiring.
They run with no external dependencies (DB, network, LLM).
"""
import pytest


class TestDomainImports:
    def test_import_course_entity(self):
        from src.domain.course.entities.course import Course

        assert Course is not None

    def test_import_module_entity(self):
        from src.domain.course.entities.module import Module

        assert Module is not None

    def test_import_topic_entity(self):
        from src.domain.course.entities.topic import Topic

        assert Topic is not None

    def test_import_content_block_entity(self):
        from src.domain.course.entities.content_block import ContentBlock

        assert ContentBlock is not None

    def test_import_block_type_enum(self):
        from src.domain.course.enums.block_type import BlockType

        assert BlockType is not None

    def test_import_course_repository_port(self):
        from src.domain.course.repositories.course_repository import CourseRepository

        assert CourseRepository is not None

    def test_import_concept_entity(self):
        from src.domain.knowledge_graph.entities.concept import Concept

        assert Concept is not None

    def test_import_concept_relation_entity(self):
        from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation

        assert ConceptRelation is not None

    def test_import_relation_type_enum(self):
        from src.domain.knowledge_graph.value_objects.relation_type import RelationType

        assert RelationType is not None

    def test_import_knowledge_graph_repository_port(self):
        from src.domain.knowledge_graph.repositories.knowledge_graph_repository import (
            KnowledgeGraphRepository,
        )

        assert KnowledgeGraphRepository is not None

    def test_import_generation_value_objects(self):
        from src.domain.generation.value_objects.job_status import JobStatus
        from src.domain.generation.value_objects.source_type import SourceType

        assert SourceType is not None
        assert JobStatus is not None

    def test_import_generation_entities(self):
        from src.domain.generation.entities.course_generation_job import (
            CourseGenerationJob,
        )
        from src.domain.generation.entities.course_source import CourseSource
        from src.domain.generation.entities.extracted_concept import ExtractedConcept
        from src.domain.generation.entities.extracted_relation import (
            ExtractedRelation,
        )
        from src.domain.generation.entities.extraction_result import ExtractionResult

        assert CourseSource is not None
        assert ExtractedConcept is not None
        assert ExtractedRelation is not None
        assert ExtractionResult is not None
        assert CourseGenerationJob is not None

    def test_import_generation_ports(self):
        from src.domain.generation.repositories.chunking_service import (
            ChunkingService,
            TextChunk,
        )
        from src.domain.generation.repositories.concept_extraction_agent import (
            ConceptExtractionAgent,
        )
        from src.domain.generation.repositories.course_generation_job_repository import (
            CourseGenerationJobRepository,
        )
        from src.domain.generation.repositories.embedding_service import (
            EmbeddingService,
        )
        from src.domain.generation.repositories.relation_classification_agent import (
            RelationClassificationAgent,
        )
        from src.domain.generation.repositories.text_extraction_repository import (
            TextExtractionRepository,
        )

        assert TextExtractionRepository is not None
        assert ChunkingService is not None
        assert TextChunk is not None
        assert ConceptExtractionAgent is not None
        assert RelationClassificationAgent is not None
        assert EmbeddingService is not None
        assert CourseGenerationJobRepository is not None

    def test_generation_public_api(self):
        from src.domain.generation import (
            ChunkingService,
            ConceptExtractionAgent,
            CourseGenerationJob,
            CourseGenerationJobRepository,
            CourseSource,
            EmbeddingService,
            ExtractionResult,
            RelationClassificationAgent,
            TextChunk,
            TextExtractionRepository,
        )

        classes = [
            CourseSource,
            ExtractionResult,
            CourseGenerationJob,
            TextExtractionRepository,
            ChunkingService,
            TextChunk,
            ConceptExtractionAgent,
            RelationClassificationAgent,
            EmbeddingService,
            CourseGenerationJobRepository,
        ]
        assert all(cls is not None for cls in classes)


class TestExceptionImports:
    @pytest.mark.parametrize(
        "import_path",
        [
            "src.domain.shared.exceptions.domain_exception.DomainException",
            "src.domain.shared.exceptions.validation_error.ValidationError",
            "src.domain.shared.exceptions.not_found_error.NotFoundError",
            "src.domain.shared.exceptions.conflict_error.ConflictError",
            "src.domain.shared.exceptions.generation_error.GenerationError",
        ],
    )
    def test_direct_import_path(self, import_path):
        module_path, class_name = import_path.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        assert cls is not None
        assert issubclass(cls, Exception)

    def test_public_exceptions_package_import(self):
        from src.domain.shared.exceptions import (
            ConflictError,
            DomainException,
            GenerationError,
            NotFoundError,
            ValidationError,
        )

        assert all(
            cls is not None
            for cls in [
                DomainException,
                ValidationError,
                NotFoundError,
                ConflictError,
                GenerationError,
            ]
        )


class TestDomainComposition:
    def test_can_build_full_course_hierarchy(self):
        from src.domain.course.entities.content_block import ContentBlock
        from src.domain.course.entities.course import Course
        from src.domain.course.entities.module import Module
        from src.domain.course.entities.topic import Topic
        from src.domain.course.enums.block_type import BlockType

        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "Hello world"},
        )
        topic = Topic(title="Topic 1", order=0, blocks=[block])
        module = Module(title="Module 1", order=0, topics=[topic])
        course = Course(
            title="Smoke Course",
            description="End-to-end smoke test",
            modules=[module],
        )

        assert course.id is not None
        assert len(course.modules) == 1
        assert len(course.modules[0].topics) == 1
        assert len(course.modules[0].topics[0].blocks) == 1
        assert course.modules[0].topics[0].blocks[0].payload["text"] == "Hello world"

    def test_can_build_knowledge_graph(self):
        from src.domain.knowledge_graph.entities.concept import Concept
        from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation
        from src.domain.knowledge_graph.value_objects.relation_type import RelationType

        a = Concept(name="Supervised Learning", source_course_id="c-1")
        b = Concept(name="Linear Regression", source_course_id="c-1")
        rel = ConceptRelation(
            source_concept_id=a.id,
            target_concept_id=b.id,
            relation_type=RelationType.PREREQUISITE_OF,
        )

        assert a.id != b.id
        assert rel.source_concept_id == a.id
        assert rel.target_concept_id == b.id
        assert rel.relation_type == RelationType.PREREQUISITE_OF

    def test_can_build_generation_job_lifecycle(self):
        from src.domain.generation.entities.course_generation_job import (
            CourseGenerationJob,
        )
        from src.domain.generation.entities.course_source import CourseSource
        from src.domain.generation.value_objects.job_status import JobStatus
        from src.domain.generation.value_objects.source_type import SourceType
        from src.domain.shared.exceptions import ValidationError

        source = CourseSource(source_type=SourceType.TEXT, content="hello")
        job = CourseGenerationJob(course_id="course-smoke-1", sources=[source])
        assert job.status == JobStatus.PENDING
        assert len(job.sources) == 1

        job.mark_running()
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

        job.mark_completed(concepts_extracted=2, relations_extracted=1)
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.duration_seconds is not None

        with pytest.raises(ValidationError):
            job.add_source(CourseSource(source_type=SourceType.TEXT, content="too late"))

    def test_can_build_extraction_result(self):
        from src.domain.generation.entities.extracted_concept import ExtractedConcept
        from src.domain.generation.entities.extracted_relation import (
            ExtractedRelation,
        )
        from src.domain.generation.entities.extraction_result import ExtractionResult
        from src.domain.knowledge_graph.value_objects.relation_type import RelationType

        a = ExtractedConcept(name="Backpropagation", confidence=0.9)
        b = ExtractedConcept(name="Gradient Descent", confidence=0.85)
        result = ExtractionResult(
            concepts=[a, b],
            relations=[
                ExtractedRelation(
                    source_name=a.name,
                    target_name=b.name,
                    relation_type=RelationType.PREREQUISITE_OF,
                    weight=0.8,
                )
            ],
        )

        assert len(result.concepts) == 2
        assert len(result.relations) == 1

        merged = result.merge(
            ExtractionResult(
                concepts=[a, ExtractedConcept(name="Learning Rate", confidence=0.7)],
                relations=[],
            )
        )
        assert len(merged.concepts) == 3
        assert len(merged.relations) == 1

    def test_domain_has_no_infrastructure_dependencies(self):
        import ast
        import os
        from pathlib import Path

        domain_root = Path(__file__).resolve().parents[2] / "src" / "domain"
        forbidden = ["sqlalchemy", "alembic", "neo4j", "fastapi", "google"]

        violations = []
        for py_file in domain_root.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in forbidden:
                            violations.append(f"{py_file.relative_to(domain_root)}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    top = (node.module or "").split(".")[0]
                    if top in forbidden:
                        violations.append(f"{py_file.relative_to(domain_root)}: imports {node.module}")

        assert not violations, (
            "Domain layer must not depend on infrastructure:\n"
            + "\n".join(violations)
        )
