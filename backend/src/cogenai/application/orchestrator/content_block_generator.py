import json
import re
from dataclasses import dataclass, field

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.context_synthesizer import GenerationContext
from cogenai.application.orchestrator.curriculum_planner import SectionSpec
from cogenai.application.orchestrator.persona_adapter import AdaptedSection
from cogenai.shared.logging import get_logger
from cogenai.domain.course import ContentBlock
from cogenai.domain.shared.value_objects import new_block_id

logger = get_logger(__name__)


@dataclass
class ContentBlockGeneratorInput:
    section_spec: SectionSpec
    adapted_section: AdaptedSection
    context: GenerationContext
    # When None, the LLM picks block types from the full taxonomy.
    block_types: tuple[str, ...] | None = None


@dataclass
class GeneratedSectionBlocks:
    section_spec: SectionSpec
    blocks: tuple[ContentBlock, ...] = field(default_factory=tuple)


class ContentBlockGeneratorAgent(BaseAgent[ContentBlockGeneratorInput, GeneratedSectionBlocks]):

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="content_block_generator", config=config, llm_provider=llm_provider)

    def run(self, input_data: ContentBlockGeneratorInput) -> GeneratedSectionBlocks:
        section_spec = input_data.section_spec
        context = input_data.context
        block_types = input_data.block_types

        if block_types is None:
            count_clause = (
                "Decide the number of blocks based on what the section needs "
                "(typically 3-7 blocks)."
            )
            type_clause = (
                "Choose block types from the full taxonomy: concept, example, "
                "code, exercise, solution, challenge, quiz, key_points, "
                "best_practices, common_mistakes, visual_explanation, analogy, "
                "reference."
            )
        else:
            count_clause = f"Generate exactly {len(block_types)} blocks."
            type_clause = f"Block types (in order): {', '.join(block_types)}"

        user_prompt = f"""
            Generate detailed content blocks for this section:

            Section: {section_spec.title}
            Topic: {section_spec.topic}
            Audience: {context.audience}
            Difficulty: {context.difficulty}
            Learning Outcomes: {', '.join(section_spec.learning_objectives)}

            {count_clause}
            {type_clause}

            Each block must be detailed and pedagogically sound.

            Output a JSON array.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        blocks = self._parse_blocks(response_text, block_types, context.difficulty)

        result = GeneratedSectionBlocks(
            section_spec=section_spec,
            blocks=tuple(blocks),
        )

        self._log_execution(input_data, result)
        return result


    def _parse_blocks(
        self,
        response: str,
        block_types: tuple[str, ...] | None,
        difficulty: str,
    ) -> list[ContentBlock]:
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON array found in LLM response for {self.name}")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', match.group())
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                data = []

        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array for {self.name}")

        # If the LLM was constrained to specific types, fall back to the
        # i-th entry. Otherwise, the LLM is free to choose and should
        # always emit the `type` field explicitly.
        fallback_types = block_types if block_types is not None else ("concept",)

        blocks = []
        for idx, block_data in enumerate(data):
            block_type = block_data.get(
                "type",
                fallback_types[idx % len(fallback_types)] if fallback_types else "concept",
            )
            content = block_data.get("content", {})
            blocks.append(ContentBlock(
                id=new_block_id(),
                type=block_type,
                order=idx,
                content=content,
                estimated_time_minutes=self._estimate_time(block_type),
                difficulty=difficulty,
            ))
        return blocks

    def _estimate_time(self, block_type: str) -> int:
        return {
            "concept": 10,
            "example": 10,
            "code": 15,
            "exercise": 15,
            "quiz": 10,
            "key_points": 5,
            "best_practices": 5,
            "common_mistakes": 5,
        }.get(block_type, 5)
