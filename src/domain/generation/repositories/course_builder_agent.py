from abc import ABC, abstractmethod

from src.domain.generation.entities.course_draft import CourseDraft
from src.domain.generation.entities.evaluation_result import EvaluationResult
from src.domain.generation.entities.generation_request import GenerationRequest


class CourseBuilderAgent(ABC):
    """Port for the LLM pass that builds or refines a course draft.

    The builder receives the original `GenerationRequest` and optionally
    the previous `EvaluationResult` (if this is not the first pass).
    It produces a new or updated `CourseDraft`.

    Pluggable adapters allow swapping between a real Gemini-powered
    builder and a deterministic fake for testing.
    """

    @abstractmethod
    async def build(
        self,
        request: GenerationRequest,
        previous_evaluation: EvaluationResult | None = None,
    ) -> CourseDraft:
        """Return a new or revised course draft.

        On the first call (previous_evaluation is None), this should
        produce a complete course from scratch. On subsequent calls
        (previous_evaluation is not None), the builder should take
        the evaluator's feedback into account to improve the draft.
        """
