from pydantic import BaseModel, Field


class RubricScoresDTO(BaseModel):
    accuracy: float = 0.0
    pedagogical_clarity: float = 0.0
    structure_compliance: float = 0.0
    depth_appropriateness: float = 0.0
    audience_alignment: float = 0.0
    consistency: float = 0.0
    completeness: float = 0.0


class RubricThresholdsDTO(BaseModel):
    overall: float = 0.8
    per_dimension: dict = Field(default_factory=dict)


class EvaluationDTO(BaseModel):
    overall_score: float = 0.0
    passed: bool = False
    rubric: RubricScoresDTO = Field(default_factory=RubricScoresDTO)
    thresholds: RubricThresholdsDTO = Field(default_factory=RubricThresholdsDTO)
    iteration_scores: list[float] = Field(default_factory=list)