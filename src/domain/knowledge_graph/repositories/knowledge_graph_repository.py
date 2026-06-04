from abc import ABC, abstractmethod

from src.domain.knowledge_graph.entities.concept import Concept
from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation


class KnowledgeGraphRepository(ABC):
    """Persistence port for the knowledge graph bounded context.

    This port is implemented by infrastructure adapters (e.g. Neo4j).
    The domain layer depends only on this interface.
    """

    @abstractmethod
    async def upsert_concept(self, concept: Concept) -> None:
        """Insert or update a single concept node."""

    @abstractmethod
    async def upsert_concepts(self, concepts: list[Concept]) -> None:
        """Insert or update many concept nodes in a single round-trip.

        Implementations should use batched Cypher (e.g. `UNWIND`) so
        that generating a course with hundreds of concepts does not
        result in hundreds of round-trips.
        """

    @abstractmethod
    async def find_concept_by_id(self, concept_id: str) -> Concept | None:
        """Return a concept by id, or None if not found."""

    @abstractmethod
    async def list_concepts_by_course(
        self,
        course_id: str,
    ) -> list[Concept]:
        """List all concepts that belong to a given course."""

    @abstractmethod
    async def delete_concept(self, concept_id: str) -> None:
        """Delete a concept node and all its incoming/outgoing relations."""

    @abstractmethod
    async def create_relation(self, relation: ConceptRelation) -> None:
        """Create a directed relation between two existing concepts."""

    @abstractmethod
    async def create_relations(self, relations: list[ConceptRelation]) -> None:
        """Create many relations in a single round-trip.

        Implementations should use batched Cypher (e.g. `UNWIND`) so
        that bulk-loading a course's relation graph is fast.
        """

    @abstractmethod
    async def delete_relations_for_concept(self, concept_id: str) -> None:
        """Delete all relations touching a concept, in any direction."""

    @abstractmethod
    async def get_graph_for_course(
        self,
        course_id: str,
        *,
        skip: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Concept], list[ConceptRelation]]:
        """Return concepts and relations for a course, with optional pagination.

        Parameters
        ----------
        course_id:
            Identifier of the course whose graph is requested.
        skip:
            Number of concepts to skip (default 0). Useful for
            paginating through very large graphs.
        limit:
            Maximum number of concepts to return (default: no
            limit). Relations returned are only those that connect
            concepts that survived pagination.
        """
