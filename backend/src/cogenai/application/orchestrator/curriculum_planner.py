from dataclasses import dataclass, field
import json
import re

from cogenai.agents.base import BaseAgent
from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.context_synthesizer import GenerationContext
from cogenai.bootstrap.logging import get_logger
from cogenai.domain.ports.llm import LLMProvider

logger = get_logger(__name__)


@dataclass
class CurriculumPlannerInput:
    context: GenerationContext
    num_modules: int | None = None
    sections_per_module: int | None = None


@dataclass
class ModuleSpec:
    title: str
    summary: str
    order: int
    topics: tuple[str, ...] = tuple()


@dataclass
class SectionSpec:
    title: str
    topic: str
    order: int
    learning_objectives: tuple[str, ...] = tuple()


@dataclass
class Prerequisite:
    from_topic: str
    to_topic: str
    type: str = "requires"


@dataclass
class CourseSkeleton:
    topic: str
    modules: tuple[ModuleSpec, ...] = field(default_factory=tuple)
    sections: tuple[SectionSpec, ...] = field(default_factory=tuple)
    prerequisites: tuple[Prerequisite, ...] = field(default_factory=tuple)
    learning_objectives_mapping: dict = field(default_factory=dict)


class CurriculumPlannerAgent(BaseAgent[CurriculumPlannerInput, CourseSkeleton]):

    def __init__(self, config: AgentConfig, llm_provider: LLMProvider):
        super().__init__(name="curriculum_planner", config=config, llm_provider=llm_provider)

    def run(self, input_data: CurriculumPlannerInput) -> CourseSkeleton:
        ctx = input_data.context

        constraint_lines = []
        if input_data.num_modules is not None:
            constraint_lines.append(
                f"Maximum modules: {input_data.num_modules} (do not exceed)"
            )
        if input_data.sections_per_module is not None:
            constraint_lines.append(
                f"Maximum sections per module: {input_data.sections_per_module} (do not exceed)"
            )
        if not constraint_lines:
            constraint_lines.append(
                "No hard limits on the number of modules or sections; "
                "design what fits the topic, outcomes, and audience."
            )
        constraints_text = "\n            ".join(constraint_lines)

        user_prompt = f"""
            Create a curriculum for: {ctx.topic}
            Audience: {ctx.audience}
            Difficulty: {ctx.difficulty}
            Outcomes: {', '.join(ctx.learning_outcomes)}
            {constraints_text}
            Return JSON with modules, sections, and prerequisites arrays.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        skeleton = self._parse_skeleton(response_text, ctx)

        self._log_execution(input_data, skeleton)
        return skeleton

    def _parse_skeleton(self, response: str, ctx: GenerationContext) -> CourseSkeleton:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in LLM response for {self.name}")

        data = json.loads(match.group())

        modules = tuple(
            ModuleSpec(
                title=m.get("title", f"Module {i}"),
                summary=m.get("summary", ""),
                order=m.get("order", i),
                topics=tuple(m.get("topics", [])),
            )
            for i, m in enumerate(data.get("modules", []))
        )

        sections = tuple(
            SectionSpec(
                title=s.get("title", f"Section {i}"),
                topic=s.get("topic", ""),
                order=s.get("order", i),
                learning_objectives=tuple(s.get("learning_objectives", ctx.learning_outcomes)),
            )
            for i, s in enumerate(data.get("sections", []))
        )

        prerequisites = tuple(
            Prerequisite(
                from_topic=p.get("from_topic", ""),
                to_topic=p.get("to_topic", ""),
                type=p.get("type", "requires"),
            )
            for p in data.get("prerequisites", [])
        )

        return CourseSkeleton(
            topic=ctx.topic,
            modules=modules,
            sections=sections,
            prerequisites=prerequisites,
            learning_objectives_mapping={outcome: list(range(len(sections))) for outcome in ctx.learning_outcomes},
        )
