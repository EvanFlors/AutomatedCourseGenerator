from dataclasses import dataclass
import json
import re

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentConfig
from cogenai.shared.logging import get_logger
from cogenai.domain.ports.llm import LLMProvider

logger = get_logger(__name__)


@dataclass
class ContextSynthesizerInput:
    topic: str
    audience: str | None = None
    difficulty: str | None = None
    learning_outcomes: tuple[str, ...] = tuple()
    text_instructions: str = ""
    documents: tuple[str, ...] = tuple()
    reference_courses: tuple[str, ...] = tuple()
    domain_knowledge: tuple[str, ...] = tuple()


@dataclass
class GenerationContext:
    topic: str
    audience: str = "beginner"
    difficulty: str = "beginner"
    learning_outcomes: tuple[str, ...] = tuple()
    text_instructions: str = ""
    documents: tuple[str, ...] = tuple()
    reference_courses: tuple[str, ...] = tuple()
    domain_knowledge: tuple[str, ...] = tuple()


class ContextSynthesizerAgent(BaseAgent[ContextSynthesizerInput, GenerationContext]):

    def __init__(self, config: AgentConfig, llm_provider: LLMProvider):
        super().__init__(name="context_synthesizer", config=config, llm_provider=llm_provider)

    def run(self, input_data: ContextSynthesizerInput) -> GenerationContext:
        user_prompt = f"""
            Synthesize this course request:
            Topic: {input_data.topic}
            Audience: {input_data.audience or 'beginner'}
            Difficulty: {input_data.difficulty or 'beginner'}
            Outcomes: {', '.join(input_data.learning_outcomes)}
            Instructions: {input_data.text_instructions}
            Return JSON with all fields.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        context = self._parse_context(response_text, input_data)

        self._log_execution(input_data, context)
        return context

    def _parse_context(self, response: str, input_data: ContextSynthesizerInput) -> GenerationContext:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in LLM response for {self.name}")

        data = json.loads(match.group())

        def to_tuple(value):
            if value is None:
                return input_data.learning_outcomes if not value else tuple()
            if isinstance(value, list):
                return tuple(value)
            return tuple([value])

        return GenerationContext(
            topic=data.get("topic", input_data.topic),
            audience=data.get("audience", input_data.audience or "beginner"),
            difficulty=data.get("difficulty", input_data.difficulty or "beginner"),
            learning_outcomes=to_tuple(data.get("learning_outcomes")) or input_data.learning_outcomes,
            text_instructions=data.get("text_instructions", input_data.text_instructions) or input_data.text_instructions,
            documents=to_tuple(data.get("documents", input_data.documents)),
            reference_courses=to_tuple(data.get("reference_courses", input_data.reference_courses)),
            domain_knowledge=to_tuple(data.get("domain_knowledge", input_data.domain_knowledge)),
        )
