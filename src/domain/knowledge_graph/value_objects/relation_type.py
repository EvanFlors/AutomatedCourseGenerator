from enum import Enum


class RelationType(str, Enum):
    """Typed edges in the knowledge graph.

    Stored as the relationship type in Neo4j. Adding a new value here
    requires a corresponding Cypher constraint check and may need
    application-side handling.
    """

    BELONGS_TO = "BELONGS_TO"
    PREREQUISITE_OF = "PREREQUISITE_OF"
    RELATED_TO = "RELATED_TO"
    EXTENDS = "EXTENDS"
