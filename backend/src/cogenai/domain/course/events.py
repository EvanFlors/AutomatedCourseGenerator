from dataclasses import dataclass, field
from datetime import datetime

from domain.shared.value_objects import BlockId, CourseId, ModuleId, SectionId


@dataclass(frozen=True)
class CourseEvent:
    course_id: CourseId
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class CourseCreated(CourseEvent):
    title: str


@dataclass(frozen=True)
class CourseUpdated(CourseEvent):
    old_version: int
    new_version: int


@dataclass(frozen=True)
class ModuleAdded(CourseEvent):
    module_id: ModuleId
    module_title: str


@dataclass(frozen=True)
class SectionRegenerated(CourseEvent):
    section_id: SectionId
    iteration: int


@dataclass(frozen=True)
class BlockRegenerated(CourseEvent):
    block_id: BlockId
    iteration: int
