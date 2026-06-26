from dataclasses import dataclass, field
import json
import re

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.context_synthesizer import GenerationContext
from cogenai.application.orchestrator.curriculum_planner import CourseSkeleton, SectionSpec
from cogenai.shared.logging import get_logger
from cogenai.domain.course import ContentBlock
from cogenai.domain.ports.llm import LLMProvider
from cogenai.domain.shared.value_objects import new_block_id

logger = get_logger(__name__)


@dataclass
class SectionAuthorInput:
    section_spec: SectionSpec
    context: GenerationContext
    skeleton: CourseSkeleton
    block_types: tuple[str, ...] = field(default_factory=lambda: ("concept", "example", "exercise", "key_points", "quiz"))


@dataclass
class SectionDraft:
    section_spec: SectionSpec
    blocks: tuple[ContentBlock, ...] = field(default_factory=tuple)
    generated_for: str = ""


class SectionAuthorAgent(BaseAgent[SectionAuthorInput, SectionDraft]):

    def __init__(self, config: AgentConfig, llm_provider: LLMProvider):
        super().__init__(name="section_author", config=config, llm_provider=llm_provider)

    def run(self, input_data: SectionAuthorInput) -> SectionDraft:
        section_spec = input_data.section_spec
        context = input_data.context
        block_types = input_data.block_types

        user_prompt = f"""
            Generate content for: {section_spec.title}
            Topic: {section_spec.topic}
            Audience: {context.audience}, Difficulty: {context.difficulty}
            Block types: {', '.join(block_types)}
            Return a JSON array of blocks with type and content fields.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        blocks = self._parse_blocks(response_text, block_types, context.difficulty)

        draft = SectionDraft(
            section_spec=section_spec,
            blocks=tuple(blocks),
            generated_for=section_spec.topic,
        )
        self._log_execution(input_data, draft)
        return draft

    def _parse_blocks(self, response: str, block_types: tuple[str, ...], difficulty: str) -> list[ContentBlock]:
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON array found in LLM response for {self.name}")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.warning("JSON parsing failed, attempting to fix", error=str(e))
            fixed = match.group().replace("\\", "\\\\").encode().decode("unicode_escape")
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                data = []

        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array for {self.name}")

        blocks = []
        for idx, block_data in enumerate(data):
            block_type = block_data.get("type", block_types[idx] if idx < len(block_types) else "concept")
            blocks.append(ContentBlock(
                id=new_block_id(),
                type=block_type,
                order=idx,
                content=block_data.get("content", {}),
                estimated_time_minutes=10,
                difficulty=difficulty,
            ))
        return blocks
