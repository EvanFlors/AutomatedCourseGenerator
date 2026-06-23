from dataclasses import dataclass
from typing import NewType
from uuid import UUID, uuid4

CourseId = NewType("CourseId", UUID)
ModuleId = NewType("ModuleId", UUID)
SectionId = NewType("SectionId", UUID)
BlockId = NewType("BlockId", UUID)
JobId = NewType("JobId", UUID)


def new_course_id() -> CourseId:
    return CourseId(uuid4())

def new_module_id() -> ModuleId:
    return ModuleId(uuid4())

def new_section_id() -> SectionId:
    return SectionId(uuid4())

def new_block_id() -> BlockId:
    return BlockId(uuid4())

def new_job_id() -> JobId:
    return JobId(uuid4())


@dataclass(frozen=True)
class Audience:
    profile: str

    def __post_init__(self):
        valid = {"beginner", "professional", "engineer", "architect", "manager", "researcher", "student"}
        normalized = self.profile.lower()
        if normalized not in valid:
            raise ValueError(f"Invalid audience profile: {self.profile}. Must be one of {valid}.")
        object.__setattr__(self, "profile", normalized)


@dataclass(frozen=True)
class Difficulty:
    level: str

    def __post_init__(self):
        valid = {"beginner", "intermediate", "advanced", "expert"}
        normalized = self.level.lower()
        if normalized not in valid:
            raise ValueError(f"Invalid difficulty level: {self.level}. Must be one of {valid}.")
        object.__setattr__(self, "level", normalized)

@dataclass(frozen=True)
class InstructionStrategy:
    strategy: str

    def __post_init__(self):
        valid = {"example_driven", "theory_first", "project_based"}
        self.strategy = self.strategy.lower()

        if self.strategy not in valid:
            raise ValueError(f"Invalid instruction strategy: {self.strategy}. Must be one of {valid}.")