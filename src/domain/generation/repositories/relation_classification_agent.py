from abc import ABC, abstractmethod

from src.domain.generation.entities.extraction_result import ExtractionResult
from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.generation.repositories.chunking_service import TextChunk


class RelationClassificationAgent(ABC):
    """Port for the second LLM pass: classify relations among concepts.

    Given a chunk and the set of `ExtractedConcept` instances that
    were found in pass one, the agent decides which pairs of
    concepts are related and labels each relation with one of
    `RelationType` values.

    Pluggable agents allow iterative refinement: a follow-up
    sprint could chain a `RelationPolisherAgent` that prunes
    noisy edges, or a `ConsensusAgent` that runs multiple
    classifiers and only keeps relations where at least two agree.
    """

    @abstractmethod
    async def classify_relations(
        self,
        chunk: TextChunk,
        concepts: list[ExtractedConcept],
    ) -> ExtractionResult:
        """Return the relations among `concepts` justified by `chunk`.

        The returned `ExtractionResult` may include only relations
        (no concepts), since the concept set is already known from
        pass one.
        """
