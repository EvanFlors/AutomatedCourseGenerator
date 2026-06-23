from __future__ import annotations

from pydantic import BaseModel, Field


class AudienceDTO(BaseModel):
    profile: str = Field(default="beginner", description="A brief description of the target audience for the course.")
    prerequisites: list[str] = Field(default_factory=list, description="A list of prerequisites for the course.")


class BlockContentDTO(BaseModel):
    model_config = {"extra": "allow"}


class BlockDTO(BaseModel):
    id: str = Field(..., description="A unique identifier for the block.")
    type: str = Field(..., description="The type of the block, e.g., 'text', 'code', 'image'.")
    order: int = Field(..., description="The order of the block within the course.")
    content: BlockContentDTO = Field(..., description="The content of the block.")
    metadata: dict = Field(default_factory=dict, description="Additional metadata for the block.")


class SectionDTO(BaseModel):
    id: str = Field(..., description="A unique identifier for the section.")
    title: str = Field(..., description="The title of the section.")
    order: int = Field(..., description="The order of the section within the course.")
    learning_objectives: list[str] = Field(default_factory=list, description="A list of learning objectives for the section.")
    blocks: list[BlockDTO] = Field(default_factory=list, description="A list of blocks within the section.")


class ModuleDTO(BaseModel):
    id: str = Field(..., description="A unique identifier for the module.")
    title: str = Field(..., description="The title of the module.")
    order: int = Field(..., description="The order of the module within the course.")
    sections: list[SectionDTO] = Field(default_factory=list, description="A list of sections within the module.")


class CourseMetadataDTO(BaseModel):
    estimated_duration_minutes: int = 0
    difficulty: str = "beginner"
    tags: list[str] = Field(default_factory=list)


class CourseDTO(BaseModel):
    id: str = Field(..., description="A unique identifier for the course.")
    title: str = Field(..., description="The title of the course.")
    summary: str = Field(..., description="A brief summary of the course.")
    language: str = "en"
    version: int = 1
    audience: AudienceDTO | None = None
    learning_outcomes: list[str] = Field(default_factory=list, description="A list of learning outcomes for the course.")
    metadata: CourseMetadataDTO = Field(default_factory=CourseMetadataDTO)
    modules: list[ModuleDTO] = Field(default_factory=list, description="A list of modules within the course.")

    @classmethod
    def from_domain(cls, course) -> CourseDTO:
        return cls(
            id=str(course.id),
            title=course.title,
            summary=course.summary,
            language=course.language,
            version=course.version,
            audience=AudienceDTO(
                profile=course.audience.profile,
                prerequisites=[],
            ) if course.audience else None,
            learning_outcomes=list(course.learning_outcomes),
            metadata=CourseMetadataDTO(
                estimated_duration_minutes=course.metadata.estimated_duration_minutes,
                difficulty=course.difficulty.level if course.difficulty else "beginner",
                tags=list(course.tags),
            ),
            modules=[
                ModuleDTO(
                    id=str(module.id),
                    title=module.title,
                    order=module.order,
                    sections=[
                        SectionDTO(
                            id=str(section.id),
                            title=section.title,
                            order=section.order,
                            learning_objectives=list(section.learning_objectives),
                            blocks=[
                                BlockDTO(
                                    id=str(block.id),
                                    type=block.type,
                                    order=block.order,
                                    content=block.content,
                                    metadata={
                                        "estimated_time_minutes": block.estimated_time_minutes,
                                        "difficulty": block.difficulty,
                                    },
                                ) for block in section.blocks
                            ],
                        ) for section in module.sections
                    ],
                ) for module in course.modules
            ],
        )