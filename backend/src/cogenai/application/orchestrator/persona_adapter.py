from dataclasses import dataclass, field
import json
import re

from cogenai.agents.base import BaseAgent
from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.section_author import SectionDraft
from cogenai.bootstrap.logging import get_logger
from cogenai.domain.course import ContentBlock
from cogenai.domain.shared.value_objects import new_block_id

logger = get_logger(__name__)


@dataclass
class PersonaAdapterInput:
    draft: SectionDraft
    audience: str = "beginner"
    strategy: str = "example_driven"


@dataclass
class AdaptedSection:
    original_draft: SectionDraft
    adapted_blocks: tuple[ContentBlock, ...] = field(default_factory=tuple)
    audience: str = ""
    strategy: str = ""


class PersonaAdapterAgent(BaseAgent[PersonaAdapterInput, AdaptedSection]):

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="persona_adapter", config=config, llm_provider=llm_provider)

    def run(self, input_data: PersonaAdapterInput) -> AdaptedSection:
        draft = input_data.draft
        audience = input_data.audience
        strategy = input_data.strategy

        blocks_json = [{"id": str(b.id), "type": b.type, "content": b.content} for b in draft.blocks]
        user_prompt = f"""
            Adapt these blocks for {audience} audience using {strategy} strategy:
            {json.dumps(blocks_json)}
            Return a JSON array of blocks with same IDs and adapted content.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        adapted_blocks = self._parse_blocks(response_text, draft.blocks, audience)

        adapted_section = AdaptedSection(
            original_draft=draft,
            adapted_blocks=tuple(adapted_blocks),
            audience=audience,
            strategy=strategy,
        )
        self._log_execution(input_data, adapted_section)
        return adapted_section

    def _parse_blocks(self, response: str, originals: tuple[ContentBlock, ...], audience: str) -> list[ContentBlock]:
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
        for block_data in data:
            content = block_data.get("content", {})
            original = next((b for b in originals if str(b.id) == block_data.get("id")), None)
            blocks.append(ContentBlock(
                id=original.id if original else new_block_id(),
                type=block_data.get("type", "concept"),
                order=original.order if original else len(blocks),
                content=content,
                estimated_time_minutes=original.estimated_time_minutes if original else 10,
                difficulty=audience,
            ))
        return blocks
