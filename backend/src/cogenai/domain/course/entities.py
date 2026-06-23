from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from cogenai.domain.shared.value_objects import (
    CourseId,
    ModuleId,
    SectionId,
    BlockId,
    JobId,
    new_course_id,
    new_module_id,
    new_section_id,
    new_block_id,
    new_job_id,
    Audience,
    Difficulty,
    InstructionStrategy
)

if TYPE_CHECKING:
    from cogenai.agents_implementations.context_synthesizer import GenerationContext

BLOCK_TYPES = frozenset({
    "concept", "example", "code", "exercise", "solution",
    "challenge", "quiz", "key_points", "best_practices",
    "common_mistakes", "visual_explanation", "analogy",
    "reference",
})


_AUDIENCE_ENUM = {"beginner", "professional", "engineer", "architect", "manager", "researcher", "student"}
_DIFFICULTY_ENUM = {"beginner", "intermediate", "advanced", "expert"}


def _build_audience(profile: str | None) -> Audience | None:
    if not profile:
        return None
    try:
        return Audience(profile=profile)
    except ValueError:
        return None


def _build_difficulty(level: str | None) -> Difficulty | None:
    if not level:
        return None
    try:
        return Difficulty(level=level)
    except ValueError:
        return None

@dataclass(frozen=True)
class ContentBlock:
    id: BlockId
    type: str = "concept"
    order: int = 0
    content: dict = field(default_factory=dict)
    estimated_time_minutes: int = 5
    difficulty: str = "beginner"
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    parent_section_id: SectionId | None = None
    parent_module_id: ModuleId | None = None
    block_index: int = 0

    def __post_init__(self):
        if self.type not in BLOCK_TYPES:
            raise ValueError(f"Invalid block type: {self.type}. Must be one of {BLOCK_TYPES}.")
        if self.order < 0:
            raise ValueError("Order must be a non-negative integer.")

    def with_content(self, content: dict, new_version: int) -> ContentBlock:
        return ContentBlock(
            id=self.id,
            type=self.type,
            order=self.order,
            content=content,
            estimated_time_minutes=self.estimated_time_minutes,
            difficulty=self.difficulty,
            created_at=self.created_at,
            version=new_version,
            parent_section_id=self.parent_section_id,
            parent_module_id=self.parent_module_id,
            block_index=self.block_index,
        )

@dataclass(frozen=True)
class Section:

    id: SectionId
    title: str
    order: int = 0
    blocks: tuple[ContentBlock, ...] = field(default_factory=tuple)
    learning_objectives: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    parent_module_id: ModuleId | None = None
    section_index: int = 0
    blocks_count: int = 0

    def __post_init__(self):
        if not self.title:
            raise ValueError("Title must be a non-empty string.")
        if self.order < 0:
            raise ValueError("Order must be a non-negative integer.")
        if not self.learning_objectives:
            raise ValueError("At least one learning objective is required.")

    def with_blocks(self, blocks: list[ContentBlock], new_version: int) -> Section:
        return Section(
            id=self.id,
            title=self.title,
            order=self.order,
            blocks=tuple(blocks),
            learning_objectives=self.learning_objectives,
            created_at=self.created_at,
            version=new_version,
            parent_module_id=self.parent_module_id,
            section_index=self.section_index,
            blocks_count=len(blocks),
        )

@dataclass(frozen=True)
class Module:
    id: ModuleId = field(default_factory=new_module_id)
    title: str = ""
    summary: str = ""
    order: int = 0
    sections: tuple[Section, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    parent_course_id: CourseId | None = None
    module_index: int = 0
    sections_count: int = 0
    blocks_count: int = 0

    def __post_init__(self):
        if not self.title:
            raise ValueError("Module title cannot be empty")
        if self.order < 0:
            raise ValueError("Order must be non-negative")

    def with_sections(self, sections: tuple[Section, ...], new_version: int) -> Module:
        return Module(
            id=self.id,
            title=self.title,
            summary=self.summary,
            order=self.order,
            sections=sections,
            created_at=self.created_at,
            version=new_version,
            parent_course_id=self.parent_course_id,
            module_index=self.module_index,
            sections_count=len(sections),
            blocks_count=sum(len(s.blocks) for s in sections),
        )

@dataclass(frozen=True)
class Course:
    id: CourseId = field(default_factory=new_course_id)
    title: str = ""
    summary: str = ""
    language: str = "en"
    audience: Audience | None = None
    difficulty: Difficulty | None = None
    learning_outcomes: tuple[str, ...] = field(default_factory=tuple)
    modules: tuple[Module, ...] = field(default_factory=tuple)
    estimated_duration_minutes: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    generation_iteration: int = 0
    source_topic: str = ""

    def __post_init__(self):
        if not self.title:
            raise ValueError("Course title cannot be empty")
        if not self.learning_outcomes:
            raise ValueError("At least one learning outcome required")
        if self.language not in {"en", "es", "fr", "de", "ja", "zh"}:
            raise ValueError(f"Unsupported language: {self.language}")

    def total_blocks(self) -> int:
        return sum(
            len(section.blocks)
            for module in self.modules
            for section in module.sections
        )

    def total_sections(self) -> int:
        return sum(len(module.sections) for module in self.modules)

    def with_modules(self, modules: tuple[Module, ...], new_version: int) -> Course:
        return Course(
            id=self.id,
            title=self.title,
            summary=self.summary,
            language=self.language,
            audience=self.audience,
            difficulty=self.difficulty,
            learning_outcomes=self.learning_outcomes,
            modules=modules,
            estimated_duration_minutes=self.estimated_duration_minutes,
            tags=self.tags,
            created_at=self.created_at,
            updated_at=datetime.now(),
            version=new_version,
            generation_iteration=self.generation_iteration,
            source_topic=self.source_topic,
        )

    @classmethod
    def from_context(
        cls,
        context: "GenerationContext",
        modules: tuple[Module, ...] = (),
        *,
        title_template: str = "{topic} for {audience}",
        summary_template: str = "A {difficulty} course on {topic} for {audience}, covering {outcomes}",
        estimated_duration_minutes: int = 0,
        tags: tuple[str, ...] = (),
        language: str = "en",
    ) -> "Course":
        """Build a Course with metadata derived from a GenerationContext.

        Used by the orchestrator to keep Course.title/summary/audience/difficulty/
        learning_outcomes in sync when the context is refined.
        """
        outcomes = list(context.learning_outcomes) or [context.topic]
        outcomes_text = ", ".join(outcomes) if outcomes else context.topic
        audience = _build_audience(context.audience)
        difficulty = _build_difficulty(context.difficulty)
        return cls(
            title=title_template.format(
                topic=context.topic,
                audience=context.audience,
            ),
            summary=summary_template.format(
                difficulty=context.difficulty,
                topic=context.topic,
                audience=context.audience,
                outcomes=outcomes_text,
            ),
            language=language,
            audience=audience,
            difficulty=difficulty,
            learning_outcomes=tuple(outcomes),
            modules=tuple(modules),
            estimated_duration_minutes=estimated_duration_minutes,
            tags=tags,
            source_topic=context.topic,
        )

    def total_blocks(self) -> int:
        return sum(
            len(section.blocks)
            for module in self.modules
            for section in module.sections
        )

    def total_sections(self) -> int:
        return sum(len(module.sections) for module in self.modules)