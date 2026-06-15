from pydantic import BaseModel, Field


class IssueDTO(BaseModel):
    id: str
    severity: str = Field(..., description="info, warning, error, blocker")
    scope: str = Field(..., description="course, module, section, block")
    target_id: str = ""
    category: str = Field(..., description="factual, pedagogical, structural, style, completeness, consistency")
    message: str
    suggestion: str = ""
    auto_fixable: bool = False


class NextActionDTO(BaseModel):
    type: str = Field(..., description="regenerate_block, regenerate_section, etc.")
    target_id: str = ""
    label: str = ""
    description: str = ""
