from typing import Optional

from pydantic import BaseModel, Field

from interfaces.dto.course import CourseDTO
from interfaces.dto.evaluation import EvaluationDTO
from interfaces.dto.generation import GenerationMetadataDTO
from interfaces.dto.issue import IssueDTO, NextActionDTO


class JSONOutputContract(BaseModel):
    schema_version: str = Field(
        default="1.0.0",
        description="Schema version for compatibility"
    )
    course: CourseDTO | None = None
    generation: GenerationMetadataDTO | None = None
    evaluation: EvaluationDTO | None = None
    issues: list[IssueDTO] = Field(default_factory=list)
    next_actions: list[NextActionDTO] = Field(default_factory=list)

    class Config:
        json_schema_extra = {  # noqa: RUF012
            "description": "JSON Output Contract per BRD §11"
        }