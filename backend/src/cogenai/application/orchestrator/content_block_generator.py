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
    block_types: tuple[str, ...] = field(default_factory=lambda: ("concept", "example", "exercise", "key_points", "quiz"))


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

        user_prompt = f"""
            Generate detailed content blocks for this section:

            Section: {section_spec.title}
            Topic: {section_spec.topic}
            Audience: {context.audience}
            Difficulty: {context.difficulty}
            Learning Outcomes: {', '.join(section_spec.learning_objectives)}

            Generate {len(block_types)} blocks of these types: {', '.join(block_types)}

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


    def _parse_blocks(self, response: str, block_types: tuple[str, ...], difficulty: str) -> list[ContentBlock]:
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

        blocks = []
        for idx, block_data in enumerate(data):
            block_type = block_data.get("type", block_types[idx] if idx < len(block_types) else "concept")
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
