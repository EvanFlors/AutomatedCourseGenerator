from dataclasses import dataclass

from cogenai.agents.base import BaseAgent
from cogenai.agents.config import AgentConfig
from cogenai.agents.registry import prompt_registry
from cogenai.domain.ports.llm import LLMProvider
from cogenai.domain.value_objects.llm import CompletionRequest, CompletionResponse


# Define the input type
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


# Define the output type
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


# Register the prompt
CONTEXT_SYNTHESIZER_PROMPT = """
You are a ContextSynthesizer agent.

Your task is to normalize and merge all user inputs into a single GenerationContext.

Input fields:
- topic: The course topic
- audience: Target audience (beginner, professional, engineer, architect, manager, researcher, student)
- difficulty: Difficulty level (beginner, intermediate, advanced, expert)
- learning_outcomes: Measurable learning outcomes
- text_instructions: Free-form instructions
- documents: Reference documents
- reference_courses: Reference course structures
- domain_knowledge: Domain-specific knowledge

Output:
Return a normalized GenerationContext with all fields properly filled.

Be thorough - include all relevant information from the inputs.
"""

prompt_registry.register(
    "context_synthesizer",
    "1.0.0",
    CONTEXT_SYNTHESIZER_PROMPT,
)

class ContextSynthesizerAgent(
    BaseAgent[ContextSynthesizerInput, GenerationContext]
):

    def __init__(self, config: AgentConfig, llm_provider: LLMProvider):
        super().__init__(
            name="context_synthesizer",
            config=config,
            llm_provider=llm_provider,
        )

    def run(self, input_data: ContextSynthesizerInput) -> GenerationContext:
        context = GenerationContext(
            topic=input_data.topic,
            audience=input_data.audience or "beginner",
            difficulty=input_data.difficulty or "beginner",
            learning_outcomes=input_data.learning_outcomes,
            text_instructions=input_data.text_instructions,
            documents=input_data.documents,
            reference_courses=input_data.reference_courses,
            domain_knowledge=input_data.domain_knowledge,
        )

        self._log_execution(input_data, context)
        return context
