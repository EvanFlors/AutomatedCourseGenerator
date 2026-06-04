"""Concrete LLM-backed adapters for the generation agents.

`GeminiConceptExtractionAgent` and
`GeminiRelationClassificationAgent` use the same underlying
`LLMClient` (a port) but different prompts and response
schemas. They are interchangeable with the `Fake*` variants via
the `ConceptExtractionAgent` / `RelationClassificationAgent`
ports.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.generation.entities.extracted_relation import ExtractedRelation
from src.domain.generation.entities.extraction_result import ExtractionResult
from src.domain.generation.repositories.chunking_service import TextChunk
from src.domain.generation.repositories.concept_extraction_agent import (
    ConceptExtractionAgent,
)
from src.domain.generation.repositories.relation_classification_agent import (
    RelationClassificationAgent,
)
from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.infrastructure.integrations.llm.llm_client import LLMClient


class _ConceptList(BaseModel):
    concepts: list[dict[str, Any]] = Field(default_factory=list)


class _RelationList(BaseModel):
    relations: list[dict[str, Any]] = Field(default_factory=list)


class GeminiConceptExtractionAgent(ConceptExtractionAgent):
    """First LLM pass: extract concept names from a chunk.

    The agent is intentionally conservative: it returns only the
    `name` and an optional `description` for each concept, not
    relations. Relations are classified in a second pass so the
    model can focus on one task at a time and produce higher
    quality output.
    """

    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def extract_from_chunk(self, chunk: TextChunk) -> ExtractionResult:
        prompt = _build_concept_prompt(chunk.text)
        schema = await self._llm.complete_json(prompt, _ConceptList)
        concepts = [
            ExtractedConcept(
                name=c["name"],
                description=c.get("description"),
                confidence=float(c.get("confidence", 1.0)),
            )
            for c in schema.concepts
            if c.get("name")
        ]
        return ExtractionResult(concepts=concepts)


class GeminiRelationClassificationAgent(RelationClassificationAgent):
    """Second LLM pass: classify relations among known concepts."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def classify_relations(
        self,
        chunk: TextChunk,
        concepts: list[ExtractedConcept],
    ) -> ExtractionResult:
        if not concepts:
            return ExtractionResult()
        prompt = _build_relation_prompt(chunk.text, concepts)
        schema = await self._llm.complete_json(prompt, _RelationList)
        valid_types = {rt.value for rt in RelationType}
        relations: list[ExtractedRelation] = []
        for r in schema.relations:
            rel_type_value = r.get("relation_type")
            if rel_type_value not in valid_types:
                continue
            try:
                relations.append(
                    ExtractedRelation(
                        source_name=r["source"],
                        target_name=r["target"],
                        relation_type=RelationType(rel_type_value),
                        weight=float(r.get("weight", 1.0)),
                        rationale=r.get("rationale"),
                    )
                )
            except Exception:
                continue
        return ExtractionResult(relations=relations)


def _build_concept_prompt(text: str) -> str:
    return f"""You are a knowledge extractor. Read the text below and list the
key concepts (terms, ideas, techniques) that a student would need
to learn. For each concept, give a short description in your own
words and a confidence score between 0 and 1.

Respond ONLY with a JSON object of the form:
{{"concepts": [{{"name": "...", "description": "...", "confidence": 0.9}}, ...]}}

Do not include any commentary, markdown, or preamble.

TEXT:
\"\"\"
{text}
\"\"\"
"""


def _build_relation_prompt(text: str, concepts: list[ExtractedConcept]) -> str:
    concept_list = "\n".join(
        f"- {c.name}" + (f": {c.description}" if c.description else "")
        for c in concepts
    )
    valid_types = ", ".join(rt.value for rt in RelationType)
    return f"""You are a knowledge graph builder. Given the text and a list of
concepts, identify the directed relations between them. Each
relation must be one of: {valid_types}.

Respond ONLY with a JSON object of the form:
{{"relations": [{{
  "source": "<concept name>",
  "target": "<concept name>",
  "relation_type": "<one of the allowed types>",
  "weight": 0.0-1.0,
  "rationale": "<short justification>"
}}, ...]}}

Do not invent concepts; only relate the ones listed. Do not include
any commentary, markdown, or preamble.

CONCEPTS:
{concept_list}

TEXT:
\"\"\"
{text}
\"\"\"
"""


def _parse_concepts_payload(payload: dict) -> list[ExtractedConcept]:
    """Helper used by FakeLLMClient test setups."""
    return [
        ExtractedConcept(
            name=c["name"],
            description=c.get("description"),
            confidence=float(c.get("confidence", 1.0)),
        )
        for c in payload.get("concepts", [])
        if c.get("name")
    ]


def _parse_relations_payload(payload: dict) -> list[ExtractedRelation]:
    """Helper used by FakeLLMClient test setups."""
    valid_types = {rt.value for rt in RelationType}
    result = []
    for r in payload.get("relations", []):
        if r.get("relation_type") not in valid_types:
            continue
        result.append(
            ExtractedRelation(
                source_name=r["source"],
                target_name=r["target"],
                relation_type=RelationType(r["relation_type"]),
                weight=float(r.get("weight", 1.0)),
                rationale=r.get("rationale"),
            )
        )
    return result


def _to_json(*, concepts=None, relations=None) -> str:
    """Helper used by FakeLLMClient test setups."""
    payload: dict = {}
    if concepts is not None:
        payload["concepts"] = [
            {
                "name": c.name,
                "description": c.description,
                "confidence": c.confidence,
            }
            for c in concepts
        ]
    if relations is not None:
        payload["relations"] = [
            {
                "source": r.source_name,
                "target": r.target_name,
                "relation_type": r.relation_type.value,
                "weight": r.weight,
                "rationale": r.rationale,
            }
            for r in relations
        ]
    return json.dumps(payload)
