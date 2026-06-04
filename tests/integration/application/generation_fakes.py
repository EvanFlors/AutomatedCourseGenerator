"""Fake ports for testing CourseGenerationService end-to-end.

The fakes live in tests/ so they cannot be accidentally imported
by the production code. They are intentionally lightweight:
no persistence, no network — they just record calls and return
programmed responses.
"""
from __future__ import annotations

import json
from typing import Any

from src.domain.generation.entities.course_generation_job import CourseGenerationJob
from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.generation.entities.extracted_relation import ExtractedRelation
from src.domain.generation.entities.extraction_result import ExtractionResult
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
from src.domain.knowledge_graph.value_objects.relation_type import RelationType


class FakeTextExtractionRepository(TextExtractionRepository):
    def __init__(self):
        self.calls: list[CourseSource] = []

    async def extract_text(self, source: CourseSource) -> str:
        self.calls.append(source)
        if source.source_type.value == "text":
            return source.content or ""
        return f"<extracted text from {source.url}>"

    async def extract_many(
        self,
        sources: list[CourseSource],
    ) -> list[CourseSource]:
        for s in sources:
            text = await self.extract_text(s)
            s.set_extracted_text(text)
        return sources


class FakeChunkingService(ChunkingService):
    def __init__(self, chunk_size: int = 100, overlap: int = 20):
        self._chunk_size = chunk_size
        self._overlap = overlap
        self.calls: list[tuple[str, int]] = []

    def chunk(self, text: str, source_index: int = 0) -> list[TextChunk]:
        self.calls.append((text, source_index))
        if not text:
            return []
        if len(text) <= self._chunk_size:
            return [
                TextChunk(
                    text=text,
                    index=0,
                    start_char=0,
                    end_char=len(text),
                    source_index=source_index,
                )
            ]
        chunks: list[TextChunk] = []
        start = 0
        idx = 0
        step = self._chunk_size - self._overlap
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            chunks.append(
                TextChunk(
                    text=text[start:end],
                    index=idx,
                    start_char=start,
                    end_char=end,
                    source_index=source_index,
                )
            )
            idx += 1
            if end >= len(text):
                break
            start = end - self._overlap
        return chunks


class FakeConceptAgent(ConceptExtractionAgent):
    def __init__(self, concepts_per_chunk: list[list[ExtractedConcept]] | None = None):
        self._queue = list(concepts_per_chunk or [])
        self.calls: list[TextChunk] = []

    async def extract_from_chunk(self, chunk: TextChunk) -> ExtractionResult:
        self.calls.append(chunk)
        if self._queue:
            return ExtractionResult(concepts=self._queue.pop(0))
        return ExtractionResult(concepts=[
            ExtractedConcept(name=f"Concept from chunk {chunk.index}"),
        ])


class FakeRelationAgent(RelationClassificationAgent):
    def __init__(self, relations_per_call: list[list[ExtractedRelation]] | None = None):
        self._queue = list(relations_per_call or [])
        self.calls: list[tuple[TextChunk, list[ExtractedConcept]]] = []

    async def classify_relations(
        self,
        chunk: TextChunk,
        concepts: list[ExtractedConcept],
    ) -> ExtractionResult:
        self.calls.append((chunk, concepts))
        relations = self._queue.pop(0) if self._queue else []
        return ExtractionResult._unsafe(
            concepts=list(concepts),
            relations=relations,
        )


class FakeEmbeddingService(EmbeddingService):
    def __init__(self, dim: int = 4):
        self._dim = dim
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1] * self._dim

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        self.calls.extend(texts)
        return [[0.1] * self._dim for _ in texts]


class FakeKnowledgeGraphRepository(KnowledgeGraphRepository):
    def __init__(self):
        self.upserted_concepts: list[Concept] = []
        self.created_relations: list[ConceptRelation] = []

    async def upsert_concept(self, concept: Concept) -> None:
        await self.upsert_concepts([concept])

    async def upsert_concepts(self, concepts: list[Concept]) -> None:
        self.upserted_concepts.extend(concepts)

    async def find_concept_by_id(self, concept_id: str) -> Concept | None:
        for c in self.upserted_concepts:
            if c.id == concept_id:
                return c
        return None

    async def list_concepts_by_course(self, course_id: str) -> list[Concept]:
        return [c for c in self.upserted_concepts if c.source_course_id == course_id]

    async def delete_concept(self, concept_id: str) -> None:
        self.upserted_concepts = [
            c for c in self.upserted_concepts if c.id != concept_id
        ]

    async def create_relation(self, relation: ConceptRelation) -> None:
        await self.create_relations([relation])

    async def create_relations(self, relations: list[ConceptRelation]) -> None:
        self.created_relations.extend(relations)

    async def delete_relations_for_concept(self, concept_id: str) -> None:
        self.created_relations = [
            r for r in self.created_relations
            if r.source_concept_id != concept_id and r.target_concept_id != concept_id
        ]

    async def get_graph_for_course(
        self,
        course_id: str,
        *,
        skip: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Concept], list[ConceptRelation]]:
        return (
            [c for c in self.upserted_concepts if c.source_course_id == course_id],
            [
                r for r in self.created_relations
                if r.source_concept_id in {c.id for c in self.upserted_concepts}
            ],
        )


class InMemoryJobRepository(CourseGenerationJobRepository):
    def __init__(self):
        self.jobs: dict[str, CourseGenerationJob] = {}
        self.history: list[CourseGenerationJob] = []

    async def save(self, job: CourseGenerationJob) -> None:
        snapshot = self._snapshot(job)
        self.jobs[job.id] = snapshot
        self.history.append(snapshot)

    async def find_by_id(self, job_id: str) -> CourseGenerationJob | None:
        return self.jobs.get(job_id)

    async def list_by_course(self, course_id: str) -> list[CourseGenerationJob]:
        return [
            j for j in self.jobs.values()
            if j.course_id == course_id
        ]

    @staticmethod
    def _snapshot(job: CourseGenerationJob) -> CourseGenerationJob:
        """Build a new aggregate that mirrors `job` at this instant.

        The repository snapshots the job on each save so the
        `history` list captures the state transitions, not just
        the final state.
        """
        sources = [
            CourseSource(
                source_type=s.source_type,
                content=s.content,
                url=s.url,
                title=s.title,
            )
            for s in job.sources
        ]
        for original, copy in zip(job.sources, sources):
            if original.extracted_text:
                copy.set_extracted_text(original.extracted_text)
        return CourseGenerationJob(
            id=job.id,
            course_id=job.course_id,
            sources=sources,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            concepts_extracted=job.concepts_extracted,
            relations_extracted=job.relations_extracted,
            error_message=job.error_message,
        )


def make_extraction_result_json(
    *,
    concepts: list[dict] | None = None,
    relations: list[dict] | None = None,
) -> str:
    return json.dumps(
        {"concepts": concepts or [], "relations": relations or []}
    )


def make_concept_payload(name: str, **kwargs) -> dict[str, Any]:
    return {"name": name, **kwargs}


def make_relation_payload(
    source: str,
    target: str,
    relation_type: str,
    weight: float = 1.0,
    **kwargs,
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "relation_type": relation_type,
        "weight": weight,
        **kwargs,
    }


__all__ = [
    "FakeChunkingService",
    "FakeConceptAgent",
    "FakeEmbeddingService",
    "FakeKnowledgeGraphRepository",
    "FakeRelationAgent",
    "FakeTextExtractionRepository",
    "InMemoryJobRepository",
    "make_concept_payload",
    "make_extraction_result_json",
    "make_relation_payload",
]
