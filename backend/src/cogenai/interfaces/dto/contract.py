from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from cogenai.interfaces.dto.course import CourseDTO
from cogenai.interfaces.dto.evaluation import EvaluationDTO
from cogenai.interfaces.dto.generation import GenerationMetadataDTO
from cogenai.interfaces.dto.issue import IssueDTO, NextActionDTO


class JSONOutputContract(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "JSON Output Contract per BRD §11"}
    )
    
    schema_version: str = Field(
        default="1.0.0",
        description="Schema version for compatibility"
    )
    course: CourseDTO | None = None
    generation: GenerationMetadataDTO | None = None
    evaluation: EvaluationDTO | None = None
    issues: list[IssueDTO] = Field(default_factory=list)
    next_actions: list[NextActionDTO] = Field(default_factory=list)