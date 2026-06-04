"""Application service that orchestrates the generation pipeline.

The service is a **stateless orchestrator**: it receives all
collaborators (ports) via constructor injection, runs the
pipeline stages in order, and updates a `CourseGenerationJob`
aggregate. The service is intentionally framework-agnostic — no
FastAPI, no SQLAlchemy, no Gemini SDK. All side effects go
through the injected ports.

Pipeline stages:

1. **Text extraction** — for each `CourseSource`, fetch its text.
2. **Chunking** — split each source into overlapping chunks.
3. **Concept extraction (pass 1)** — for each chunk, ask the
   `ConceptExtractionAgent` for the concepts it mentions.
4. **Relation classification (pass 2)** — for each chunk + its
   extracted concepts, ask the
   `RelationClassificationAgent` for the edges.
5. **Embedding** — for each unique concept name, ask the
   `EmbeddingService` for a vector.
6. **Persistence** — upsert concepts + relations into Neo4j and
   mark the job as completed.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from src.domain.generation.entities.course_generation_job import CourseGenerationJob
from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.generation.entities.extracted_relation import ExtractedRelation
from src.domain.generation.entities.extraction_result import ExtractionResult
from src.domain.generation.repositories.chunking_service import ChunkingService
from src.domain.generation.repositories.chunking_service import TextChunk
from src.domain.generation.repositories.concept_extraction_agent import (
    ConceptExtractionAgent,
)
from src.domain.generation.repositories.course_generation_job_repository import (
    CourseGenerationJobRepository,
)
from src.domain.generation.repositories.embedding_service import EmbeddingService
from src.domain.generation.repositories.relation_classification_agent import (
    RelationClassificationAgent,
)
from src.domain.generation.repositories.text_extraction_repository import (
    TextExtractionRepository,
)
from src.domain.knowledge_graph.entities.concept import Concept
from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation
from src.domain.knowledge_graph.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from src.domain.shared.exceptions.validation_error import ValidationError

T = TypeVar("T")


class CourseGenerationService:
    """Sync orchestrator that runs the generation pipeline.

    Despite the name "sync", the implementation is fully
    async. "Sync" here means "in-process" — the service is not a
    background worker. Stages execute sequentially within a
    single `run()` call; inside each stage, work is parallelized
    via `asyncio.gather` where the port supports batching.
    """

    def __init__(
        self,
        *,
        text_extraction: TextExtractionRepository,
        chunking: ChunkingService,
        concept_agent: ConceptExtractionAgent,
        relation_agent: RelationClassificationAgent,
        embedding_service: EmbeddingService,
        knowledge_graph: KnowledgeGraphRepository,
        job_repository: CourseGenerationJobRepository,
        concurrency: int = 4,
    ):
        self._text_extraction = text_extraction
        self._chunking = chunking
        self._concept_agent = concept_agent
        self._relation_agent = relation_agent
        self._embedding_service = embedding_service
        self._knowledge_graph = knowledge_graph
        self._job_repository = job_repository
        self._concurrency = max(1, concurrency)

    async def run(self, job: CourseGenerationJob) -> CourseGenerationJob:
        """Execute all pipeline stages for `job`.

        On success, the returned job is in `COMPLETED` state. On
        failure, the job is in `FAILED` state with the error
        message set; the exception is re-raised so the caller can
        decide what to do (e.g. return 500 to the HTTP layer).
        """
        if not isinstance(job, CourseGenerationJob):
            raise ValidationError(
                f"Expected CourseGenerationJob, got {type(job).__name__}."
            )
        if not job.sources:
            raise ValidationError("Job must have at least one source.")

        await self._safe_save(job)
        job.mark_running()
        await self._safe_save(job)

        try:
            sources_with_text = await self._stage_text_extraction(job.sources)
            chunks = await self._stage_chunking(sources_with_text)

            merged_concepts = await self._stage_concept_extraction(chunks)
            relations = await self._stage_relation_classification(
                chunks, merged_concepts
            )

            embeddings = await self._stage_embeddings(merged_concepts)
            await self._stage_persist(job, merged_concepts, relations, embeddings)

            job.mark_completed(
                concepts_extracted=len(merged_concepts),
                relations_extracted=len(relations),
            )
            await self._safe_save(job)
            return job

        except Exception as exc:
            job.mark_failed(str(exc))
            await self._safe_save(job)
            raise

    async def _safe_save(self, job: CourseGenerationJob) -> None:
        try:
            await self._job_repository.save(job)
        except Exception:
            pass

    async def _stage_text_extraction(
        self,
        sources: list[CourseSource],
    ) -> list[CourseSource]:
        return await self._text_extraction.extract_many(sources)

    async def _stage_chunking(
        self,
        sources: list[CourseSource],
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for source_index, source in enumerate(sources):
            text = source.effective_text
            if not text:
                continue
            chunks.extend(self._chunking.chunk(text, source_index=source_index))
        return chunks

    async def _stage_concept_extraction(
        self,
        chunks: list[TextChunk],
    ) -> list[ExtractedConcept]:
        if not chunks:
            return []
        results = await self._gather(
            self._concept_agent.extract_from_chunk(c) for c in chunks
        )
        merged: dict[str, ExtractedConcept] = {}
        for r in results:
            for c in r.concepts:
                merged.setdefault(c.name.lower(), c)
        return list(merged.values())

    async def _stage_relation_classification(
        self,
        chunks: list[TextChunk],
        concepts: list[ExtractedConcept],
    ) -> list[ExtractedRelation]:
        if not chunks or not concepts:
            return []
        concept_names = {c.name.lower(): c for c in concepts}
        chunk_concept_pairs: list[tuple[TextChunk, list[ExtractedConcept]]] = []
        for chunk in chunks:
            chunk_lower = chunk.text.lower()
            chunk_concepts = [
                c for name, c in concept_names.items() if name in chunk_lower
            ]
            if chunk_concepts:
                chunk_concept_pairs.append((chunk, chunk_concepts))

        if not chunk_concept_pairs:
            return []

        results = await self._gather(
            self._relation_agent.classify_relations(chunk, c_concepts)
            for chunk, c_concepts in chunk_concept_pairs
        )

        relations: dict[tuple[str, str, str], ExtractedRelation] = {}
        for r in results:
            for rel in r.relations:
                key = (
                    rel.source_name.lower(),
                    rel.target_name.lower(),
                    rel.relation_type.value,
                )
                if key not in relations or rel.weight > relations[key].weight:
                    relations[key] = rel
        return list(relations.values())

    async def _stage_embeddings(
        self,
        concepts: list[ExtractedConcept],
    ) -> dict[str, list[float]]:
        if not concepts:
            return {}
        texts = [c.name for c in concepts]
        vectors = await self._embedding_service.embed_many(texts)
        return {
            concept.name.lower(): vector
            for concept, vector in zip(concepts, vectors)
        }

    async def _stage_persist(
        self,
        job: CourseGenerationJob,
        concepts: list[ExtractedConcept],
        relations: list[ExtractedRelation],
        embeddings: dict[str, list[float]],
    ) -> None:
        concept_ids: dict[str, str] = {}
        graph_concepts: list[Concept] = []
        for c in concepts:
            concept = Concept(
                name=c.name,
                description=c.description,
                embedding=embeddings.get(c.name.lower()),
                source_course_id=job.course_id,
                metadata={
                    "job_id": job.id,
                    "confidence": c.confidence,
                },
            )
            concept_ids[c.name.lower()] = concept.id
            graph_concepts.append(concept)

        graph_relations: list[ConceptRelation] = []
        for r in relations:
            source_id = concept_ids.get(r.source_name.lower())
            target_id = concept_ids.get(r.target_name.lower())
            if source_id is None or target_id is None:
                continue
            graph_relations.append(
                ConceptRelation(
                    source_concept_id=source_id,
                    target_concept_id=target_id,
                    relation_type=r.relation_type,
                    weight=r.weight,
                    metadata={
                        "job_id": job.id,
                        "rationale": r.rationale or "",
                    },
                )
            )

        if graph_concepts:
            await self._knowledge_graph.upsert_concepts(graph_concepts)
        if graph_relations:
            await self._knowledge_graph.create_relations(graph_relations)

    async def _gather(
        self,
        coros,
    ) -> list:
        semaphore = asyncio.Semaphore(self._concurrency)

        async def _run(coro: Awaitable[T]) -> T:
            async with semaphore:
                return await coro

        return await asyncio.gather(*(_run(c) for c in coros))
