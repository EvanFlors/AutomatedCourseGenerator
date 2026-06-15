from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.shared.value_objects import (
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

BLOCK_TYPES = frozenset({
    "concept", "example", "code", "exercise", "solution",
    "challenge", "quiz", "key_points", "best_practices",
    "common_mistakes", "visual_explanation", "analogy",
    "reference",
})

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
            blocks=blocks,
            learning_objectives=self.learning_objectives,
            created_at=self.created_at,
            version=new_version,
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

    def __post_init__(self):
        if not self.title:
            raise ValueError("Module title cannot be empty")
        if self.order < 0:
            raise ValueError("Order must be non-negative")

    def with_sections(self, sections: tuple[Section, ...], new_version: int) -> "Module":
        return Module(
            id=self.id,
            title=self.title,
            summary=self.summary,
            order=self.order,
            sections=sections,
            created_at=self.created_at,
            version=new_version,
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

    def __post_init__(self):
        if not self.title:
            raise ValueError("Course title cannot be empty")
        if not self.learning_outcomes:
            raise ValueError("At least one learning outcome required")
        if self.language not in {"en", "es", "fr", "de", "ja", "zh"}:
            raise ValueError(f"Unsupported language: {self.language}")

    def with_modules(self, modules: tuple[Module, ...], new_version: int) -> "Course":
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
        )

    def total_blocks(self) -> int:
        return sum(
            len(section.blocks)
            for module in self.modules
            for section in module.sections
        )

    def total_sections(self) -> int:
        return sum(len(module.sections) for module in self.modules)